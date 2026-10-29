"""Inputs and probability tables of the SNUfish app, from the repository.

    snufish export-app --out build/app

writes ``inputs.json`` (see :mod:`snufish.engine`), ``day_<solar model>``
(F_1, F_2 per flux component on a (sin^2 theta12, Delta m^2_21, E) grid,
over the component's own energies) and ``night_<Earth model>``
(P(nu_i -> nu_e) for every site on the same parameter grid). Each table is
``<name>.json`` (small arrays, exact, and an index) with ``<name>.bin``
(large arrays, little-endian float32): read the same way by
:func:`snufish.engine.read_table` and by the web page. Needs ``snufish build`` (B4 cross sections) and the
NuFast-Earth driver (night tables).
"""

import datetime
import json
import multiprocessing
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .exposure import cell_weights
from .fluxes import components
from .paths import build_dir, repo_root
from .reference.sun import adiabatic_fractions
from .scan import _with_oscillation, day_fractions, night_grid, night_probabilities, site_latitude
from .solar import COMPONENTS, models, production_weights
from .spec import load_spec

# Measured total 8B flux (SNO neutral current, all flavours), the constraint
# Super-Kamiokande applies: 5.25e6 cm^-2 s^-1 +- 3.81% (arXiv:2312.12907, fig. 42).
B8_MEASURED = {"flux": 5.25e6, "error": 0.0381, "source": "SNO NC, as applied in arXiv:2312.12907"}
# Below its table nu_e-40Ar CC is zero: the 40K* threshold.
XSEC_THRESHOLDS = {"cc_nue_ar40": 1.504}
# Visible energy of a CC interaction, E_nu - Q (the electron plus the de-excitation gammas, no losses):
# Q = the reaction threshold, 40Ar -> 40K* 1.504 MeV, 16O -> 16F 15.42 MeV.
VISIBLE_OFFSET = {"cc_nue_ar40": 1.504, "cc_nue_o16": 15.42}

S12_GRID = (0.24, 0.38, 0.01)
DM21_GRID = (3.0, 11.0, 0.2)   # 1e-5 eV^2; 0.1 is no closer to the exact solvers
DAY_ENERGIES = np.geomspace(0.1, 20.0, 72)


def component_energies(inputs):
    """{component: energies of its day table}: a continuum's part of
    DAY_ENERGIES (one point beyond each end), a line's own energies."""
    out = {}
    for name, info in inputs["components"].items():
        if "lines" in info:
            out[name] = np.array(sorted(line[0] for line in info["lines"]))
            continue
        energy = np.array(info["energy"])
        low, high = energy[energy > 0].min(), energy.max()
        i = max(np.searchsorted(DAY_ENERGIES, low) - 1, 0)
        j = min(np.searchsorted(DAY_ENERGIES, high) + 1, len(DAY_ENERGIES))
        out[name] = DAY_ENERGIES[i:j]
    return out


def _yaml(path):
    with (repo_root() / path).open() as handle:
        return yaml.safe_load(handle)


def collect_inputs():
    """The engine's inputs dict (JSON-serialisable)."""
    b5, b3 = load_spec("B5_rates"), load_spec("B3_earth")
    comps = {}
    for name, entry in components(b5).items():
        if len(entry) == 2:
            comps[name] = {"lines": [list(line) for line in entry[1]]}
        else:
            comps[name] = {"energy": entry[1].tolist(), "shape": entry[2].tolist()}
    solar = {name: {"label": f"{m['family']} {m['composition'].split(':')[0]}", "family": m["family"],
                    "composition": m["composition"], "reference": m["reference"], "fluxes": m["fluxes"],
                    "flux_uncertainty": m.get("flux_uncertainty"), "flux_correlation": m.get("flux_correlation")}
             for name, m in models().items()}
    sigma = pd.read_parquet(build_dir() / "B4_Sigma.parquet")
    xsec = {}
    for row in sigma[(sigma.Tool == "snowglobes") & sigma.Channel.str.startswith("cc_")].itertuples():
        # NaN: not provided by the model at that energy; counted as zero (a lower bound)
        xsec.setdefault(row.Channel, {})[row.Variant] = {"energy": np.asarray(row.Energy).tolist(),
                                                         "sigma": np.nan_to_num(np.asarray(row.Sigma)).tolist()}
    ratio = {}
    for flavour in ("nue", "numu"):
        rows = {r.Tool: r for r in sigma[(sigma.Channel == f"es_{flavour}") & (sigma.Variant == "default")].itertuples()}
        sg, ref = rows["snowglobes"], rows["snufish-reference"]
        assert np.allclose(sg.Energy, ref.Energy)
        ratio[flavour] = {"energy": np.asarray(sg.Energy).tolist(),
                          "ratio": np.nan_to_num(np.asarray(sg.Sigma) / np.asarray(ref.Sigma), nan=1.0).tolist()}
    return {
        "component_order": list(COMPONENTS),
        "components": comps,
        "solar_models": solar,
        "b8_measured": B8_MEASURED,
        "constants": load_spec("B4_xsec")["constants"],
        "detectors": b5["detectors"],
        "seconds_per_year": b5["exposure"]["seconds_per_year"],
        "xsec": xsec,
        "xsec_thresholds_MeV": XSEC_THRESHOLDS,
        "visible_offset_MeV": VISIBLE_OFFSET,
        "es_radiative_ratio": ratio,
        "earth_models": list(b3["earth_models"]),
        "sites": b3["sites"],
        "parameter_sets": _yaml("reference/oscillation/parameter_sets.yaml"),
        "measurements": _yaml("reference/measurements/solar.yaml"),
    }


class ExactProbabilities:
    """The B2 and B3 solvers (NuFast-Earth for the night), as an engine provider."""

    def day(self, osc, solar_model, component, energies):
        return day_fractions(osc, solar_model, energies, component)

    def night(self, osc, earth_model, site):
        return night_probabilities(osc, earth_model, site_latitude(site))


def write_table(directory, name, values):
    """``<name>.json`` + ``<name>.bin``: arrays of more than 1000 numbers go to
    the .bin as float32, the rest (and strings) to the .json as they are."""
    index, small, chunks, offset = {}, {}, [], 0
    for key, value in values.items():
        value = np.asarray(value)
        if value.dtype.kind in "US" or value.size <= 1000:
            small[key] = value.tolist()
            continue
        data = np.ascontiguousarray(value, dtype="<f4")
        index[key] = {"offset": offset, "shape": list(value.shape)}
        chunks.append(data.tobytes())
        offset += data.nbytes
    with (Path(directory) / f"{name}.bin").open("wb") as handle:
        handle.write(b"".join(chunks))
    with (Path(directory) / f"{name}.json").open("w") as handle:
        json.dump({"values": small, "arrays": index, "bin": f"{name}.bin"}, handle)
    return [f"{name}.json", f"{name}.bin"]


def _axis(start, stop, step):
    return np.round(np.linspace(start, stop, int(round((stop - start) / step)) + 1), 6)


_SHARED = {}  # set before the worker pool forks


def _point(args):
    """Day fractions of every solar model and night probabilities of every
    Earth model and site, at one (sin^2 theta12, Delta m^2_21)."""
    from .engine import oscillation, parameters

    s12, dm21 = args
    inputs, solar_models, earth_models, sites = (_SHARED[k] for k in ("inputs", "solar_models", "earth_models",
                                                                      "sites"))
    osc = oscillation(parameters(inputs, custom={"sin2_theta12": s12, "dm2_21_eV2": dm21 * 1e-5}))
    spec = _with_oscillation(load_spec("B2_sun"), osc)
    radii = spec.axis("radius")
    energies = component_energies(inputs)
    union = np.unique(np.concatenate(list(energies.values())))
    day = []
    for model in solar_models:
        F = adiabatic_fractions(spec, model, union, radii)
        weights = production_weights(model, radii, spec)
        day.append({c: np.einsum("r,rei->ei", weights[c], F[:, np.searchsorted(union, energies[c])])[:, :2]
                    for c in COMPONENTS})
    night = []
    for earth in earth_models:
        energies, cosines, P = night_grid(osc, earth)
        night.append([np.einsum("eci,c->ei", P, cell_weights(cosines, np.radians(sites[s]["latitude_deg"])))
                      for s in sites])
    return day, np.array(night), energies


def export_app(out, s12=S12_GRID, dm21=DM21_GRID, jobs=None, solar_models=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    inputs = collect_inputs()
    with (out / "inputs.json").open("w") as handle:
        json.dump(inputs, handle, allow_nan=False)  # read by JavaScript too
    s12_axis, dm21_axis = _axis(*s12), _axis(*dm21)
    solar_models = list(solar_models or inputs["solar_models"])
    earth_models, sites = inputs["earth_models"], inputs["sites"]
    _SHARED.update(inputs=inputs, solar_models=solar_models, earth_models=earth_models, sites=sites)
    points = [(a, b) for a in s12_axis for b in dm21_axis]
    workers = jobs or multiprocessing.cpu_count()
    print(f"{len(points)} grid points x ({len(solar_models)} solar models, {len(earth_models)} Earth models) "
          f"on {workers} processes", file=sys.stderr, flush=True)
    start, results = time.monotonic(), []
    with multiprocessing.get_context("fork").Pool(workers) as pool:
        for k, result in enumerate(pool.imap(_point, points, chunksize=4), 1):
            results.append(result)
            if k % 50 == 0 or k == len(points):
                elapsed = time.monotonic() - start
                print(f"\r  {k}/{len(points)} points, {elapsed:.0f} s elapsed, "
                      f"~{elapsed * (len(points) - k) / k:.0f} s left ", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    shape = (len(s12_axis), len(dm21_axis))
    night = np.array([r[1] for r in results]).reshape(*shape, *results[0][1].shape)      # s12, dm21, earth, site, E, 3
    common = dict(s12=s12_axis, dm21=dm21_axis)
    files = []
    energies = component_energies(inputs)
    for m, model in enumerate(solar_models):
        tables = {f"F_{c}": np.array([r[0][m][c] for r in results]).reshape(*shape, len(energies[c]), 2)
                  for c in COMPONENTS}  # s12, dm21, E, (F1, F2)
        files += write_table(out, f"day_{model}", {**common, **{f"energy_{c}": energies[c] for c in COMPONENTS},
                                                   **tables})
    for e, earth in enumerate(earth_models):
        files += write_table(out, f"night_{earth}", {**common, "energy": results[0][2], "sites": np.array(list(sites)),
                                                     "P": np.moveaxis(night[:, :, e], 2, 0)})
    manifest = {"date": datetime.date.today().isoformat(), "s12": list(s12), "dm21_1e-5eV2": list(dm21),
                "files": ["inputs.json", *files]}
    with (out / "manifest.json").open("w") as handle:
        json.dump(manifest, handle, indent=1)
    return manifest
