"""Inputs and probability tables of the SNUfish app, from the repository.

    snufish export-app --out build/app

writes ``inputs.json`` (see :mod:`snufish.engine`), ``day_<solar model>``
(F_1, F_2 per flux component on a (sin^2 theta12, Delta m^2_21, E) grid,
over the component's own energies) and ``night_<Earth model>``
(P(nu_i -> nu_e) for every site on the same parameter grid; the continuous Earth regions cut into
scan.SPLIT_KM shells, prem_crust1_3d along one chord per nadir: snufish.earth3d). Each table is
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

from . import crust, earth3d
from .exposure import cell_weights, orbital_factors, solar_weight
from .fluxes import components
from .paths import build_dir, repo_root
from .reference.radiative import ratio_table
from .reference.sun import adiabatic_fractions
from .scan import SPLIT_KM, _with_oscillation, day_fractions, night_grid, night_probabilities, site_latitude
from .solar import COMPONENTS, models, production_weights
from .spec import load_spec

# Measured total 8B flux (SNO neutral current, all flavours), the constraint
# Super-Kamiokande applies: 5.25e6 cm^-2 s^-1 +- 3.81% (arXiv:2312.12907, fig. 42).
B8_MEASURED = {"flux": 5.25e6, "error": 0.0381, "source": "SNO NC, as applied in arXiv:2312.12907"}
# Below its table nu_e-40Ar CC is zero: the 40K* threshold.
XSEC_THRESHOLDS = {"cc_nue_ar40": 1.504, "cc_nue_d": 1.442, "nc_d": 2.224}
# Visible energy of a CC interaction, E_nu - Q (the electron plus the de-excitation gammas, no losses):
# Q = the reaction threshold, 40Ar -> 40K* 1.504 MeV, 16O -> 16F 15.42 MeV, d(nu_e, e-)pp 1.442 MeV; the B5
# spec's (part 2, response.visible_offset_MeV).
VISIBLE_OFFSET = dict(load_spec("B5_rates")["response"]["visible_offset_MeV"])
# NC on 40Ar has no visible-energy model (its de-excitation gammas are not modelled): its observed axis is the
# neutrino energy itself (offset 0), so a threshold there is a cut in E_nu (engine.NEUTRINO_AXIS).
VISIBLE_OFFSET["nc_ar40"] = 0.0
# NC: the energy is the neutron's capture gamma, whatever the neutrino's: 6.25 MeV on the deuteron (pure D2O)
VISIBLE_FIXED = {"nc_d": 6.25}
# Tables that are zero below 5 MeV (SNOwGLoBES's MARLEY tables): selectable, but kept out of the model range.
XSEC_INCOMPLETE = {"cc_nue_ar40": ["ar40_marley", "ar40_marley1"]}
MARLEY_DEFAULT = "ar40_marley2_bhattacharya2009"
# Targets of the web page beyond the B5 spec's detectors, with the electron densities their experiments quote.
APP_DETECTORS = {
    "scintillator_lab": {
        "description": "linear alkylbenzene (JUNO): 3.38 x 10^32 electrons per kt, arXiv:2006.11760",
        "targets": {"electron": 3.38e32}, "channels": {"es": "electron"}},
}

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
    sigma_path = build_dir() / "B4_Sigma.parquet"
    if not sigma_path.exists():
        from .build import build
        build("B4_xsec", out_dir=build_dir(), echo=lambda *_: None)
    sigma = pd.read_parquet(sigma_path)
    xsec = {}
    for row in sigma[(sigma.Tool == "snowglobes") & sigma.Channel.str.startswith("cc_")].itertuples():
        # NaN: not provided by the model at that energy; counted as zero (a lower bound)
        xsec.setdefault(row.Channel, {})[row.Variant] = {"energy": np.asarray(row.Energy).tolist(),
                                                         "sigma": np.nan_to_num(np.asarray(row.Sigma)).tolist()}
    # MARLEY's own tables (its `default` is one of its named variants), and its per-level B(GT) shifts
    for row in sigma[(sigma.Tool == "marley") & (sigma.Variant != "default")].itertuples():
        xsec.setdefault(row.Channel, {})[row.Variant] = {"energy": np.asarray(row.Energy).tolist(),
                                                         "sigma": np.nan_to_num(np.asarray(row.Sigma)).tolist()}
    levels = {}
    shifts = sorted((repo_root() / "contributions" / "marley" / "B4_xsec").glob("*/bgt_levels.parquet"))
    if shifts and MARLEY_DEFAULT in xsec.get("cc_nue_ar40", {}):
        table = pd.read_parquet(shifts[-1])
        if "Variant" not in table:  # one variant only, before ar40_marley1_allowed had levels
            table["Variant"] = MARLEY_DEFAULT
        levels = {"cc_nue_ar40": {}}
        for variant, rows in table.groupby("Variant", sort=False):
            entries = []
            for n, row in enumerate(rows.itertuples(), 1):
                name = f"{variant}#bgt{n}"
                xsec["cc_nue_ar40"][name] = {"energy": np.asarray(row.Energy).tolist(),
                                             "sigma": np.nan_to_num(np.asarray(row.Sigma)).tolist()}
                entries.append({"name": name, "level_MeV": row.Level, "kind": row.Kind, "strength": row.Strength,
                                "error": row.Error})
            levels["cc_nue_ar40"][variant] = entries
    # 40Ar: the shell model of Kostensalo, Suhonen & Zuber 2018, a published table, on the B4 grid
    if "cc_nue_ar40" in xsec:
        grid = np.asarray(next(iter(xsec["cc_nue_ar40"].values()))["energy"])
        xsec["cc_nue_ar40"]["ar40_ksz2018"] = {"energy": grid.tolist(), "sigma": kostensalo2018(grid).tolist()}
    # deuteron: Nakamura et al. 2002 down to threshold (SNOwGLoBES has the same table from 5 MeV), and NC
    nakamura = _yaml("reference/xsec/nakamura2002.yaml")
    for channel in ("cc_nue_d", "nc_d"):
        xsec.setdefault(channel, {})["default"] = {"energy": nakamura["energy_MeV"], "sigma": nakamura[channel]}
    # NC on 40Ar: SNOwGLoBES's table (QRPA, unpublished; see the file), its small negative values set to zero
    nc_ar40 = _yaml("reference/xsec/snowglobes_nc_ar40.yaml")
    xsec["nc_ar40"] = {"default": {"energy": nc_ar40["energy_MeV"],
                                   "sigma": np.clip(nc_ar40["sigma_cm2"], 0.0, None).tolist()}}
    detectors = {**b5["detectors"], **APP_DETECTORS}
    # NC channels have no B4 benchmark: the page adds them to the spec's detectors
    detectors["argon"] = {**detectors["argon"], "channels": {**detectors["argon"]["channels"], "nc_ar40": "ar40"}}
    detectors["heavy_water"] = {**detectors["heavy_water"],
                                "channels": {**detectors["heavy_water"]["channels"], "nc_d": "deuteron"}}
    ratio = {}
    for flavour in ("nue", "numu"):
        rows = {r.Tool: r for r in sigma[(sigma.Channel == f"es_{flavour}") & (sigma.Variant == "default")].itertuples()}
        sg, ref = rows["snowglobes"], rows["snufish-reference"]
        assert np.allclose(sg.Energy, ref.Energy)
        r = np.asarray(sg.Sigma) / np.asarray(ref.Sigma)
        keep = np.isfinite(r)  # where SNOwGLoBES has a table (from 0.5 MeV); the engines use BKS below
        ratio[flavour] = {"energy": np.asarray(sg.Energy)[keep].tolist(), "ratio": r[keep].tolist()}
    return {
        "component_order": list(COMPONENTS),
        "components": comps,
        "solar_models": solar,
        "b8_measured": B8_MEASURED,
        "constants": load_spec("B4_xsec")["constants"],
        "detectors": detectors,
        "seconds_per_year": b5["exposure"]["seconds_per_year"],
        "xsec": xsec,
        "xsec_thresholds_MeV": XSEC_THRESHOLDS,
        "visible_offset_MeV": VISIBLE_OFFSET,
        "visible_fixed_MeV": VISIBLE_FIXED,
        "xsec_incomplete": XSEC_INCOMPLETE,
        "xsec_levels": levels,
        "es_radiative_ratio": ratio,
        "es_bks": ratio_table(load_spec("B4_xsec")["constants"]),
        "earth_models": list(b3["earth_models"]) + crust.available(),  # + site-dependent models (crust.py)
        "sites": {site: {**info, **dict(zip(("orbit_day", "orbit_night"),
                                            orbital_factors(np.radians(info["latitude_deg"]))))}
                  for site, info in b3["sites"].items()},
        "parameter_sets": _yaml("reference/oscillation/parameter_sets.yaml"),
        "measurements": _yaml("reference/measurements/solar.yaml"),
        "efficiency_curves": efficiency_curves(),
        "responses": b5["response"]["detectors"],  # B5 part 2: the published response of each detector
        "status": status_table(),
    }


def kostensalo2018(energy):
    """nu_e 40Ar CC cross section (cm^2) of Kostensalo, Suhonen & Zuber 2018 (reference/xsec/kostensalo2018.yaml):
    log(sigma) linear in log(E - Q) between the table's points, the first segment continued to the threshold,
    the last beyond the table."""
    table = _yaml("reference/xsec/kostensalo2018.yaml")
    q, e = table["threshold_MeV"], np.asarray(energy, dtype=float)
    x, y = np.log(np.asarray(table["energy_MeV"]) - q), np.log(np.asarray(table["total_1e-42cm2"]) * 1e-42)
    u = np.log(np.clip(e - q, 1e-12, None))
    slope_low, slope_high = (y[1] - y[0]) / (x[1] - x[0]), (y[-1] - y[-2]) / (x[-1] - x[-2])
    log_sigma = np.where(u < x[0], y[0] + slope_low * (u - x[0]),
                         np.where(u > x[-1], y[-1] + slope_high * (u - x[-1]), np.interp(u, x, y)))
    return np.where(e > q, np.exp(log_sigma), 0.0)


def status_table():
    """reference/status.yaml: which solar models, parameter sets, Earth models and cross sections are the
    state of the art, which are legacy and which are approximations (see docs/status-of-inputs.md)."""
    return _yaml("reference/status.yaml")


def efficiency_curves():
    """{name: dict(label, source, note, x, y)}: the published (binned) efficiency curves as
    step tables for the engine's linear interpolation, each bin flat from its low edge to 1 keV
    below its high edge."""
    out = {}
    for name, c in _yaml("reference/detectors/efficiency_curves.yaml").items():
        edges, eff = c["edges_MeV"], c["efficiency"]
        x = [v for lo, hi in zip(edges[:-1], edges[1:]) for v in (lo, round(hi - 1e-3, 6))]
        out[name] = dict(label=c["label"], source=c["source"], note=c["note"], method=c["method"].strip(),
                         x=x, y=[v for v in eff for _ in (0, 1)])
    return out


class ExactProbabilities:
    """The B2 and B3 solvers (NuFast-Earth for the night), as an engine provider.

    By default the night is B3's: detector at the surface, the exposure W(eta) of Lisi & Montanino
    integrated over each cell of a 1001-point cos-nadir grid, at the site's latitude. ``night_mode="solar"``
    takes the conventions of the SOLAR analysis (lib/oscillation_backends.py, physics.json): ``nadir_bins``
    uniform bins in cos nadir over [-1, 1] (40 x 4 oversampling: 80 by night), W sampled at the bin centres
    and normalised over them, ``depth_km`` 1.478 and ``latitude_deg`` 44.35. SOLAR's Earth density model
    (set in its NuFast-Earth binding, not in its repository) is not known: pass the ``earth_model`` as usual.
    ``split_km``: the continuous Earth regions cut into shells of at most this (scan.SPLIT_KM, as the app
    tables); None: NuFast-Earth's mean density per region crossing."""

    def __init__(self, night_mode="b3", depth_km=None, latitude_deg=None, nadir_bins=160, split_km=SPLIT_KM):
        if night_mode not in ("b3", "solar"):
            raise ValueError("night_mode is 'b3' or 'solar'")
        self.night_mode, self.nadir_bins, self.split_km = night_mode, int(nadir_bins), split_km
        self.depth_km = 1.478 if depth_km is None and night_mode == "solar" else depth_km
        self.latitude_deg = 44.35 if latitude_deg is None and night_mode == "solar" else latitude_deg

    def day(self, osc, solar_model, component, energies):
        return day_fractions(osc, solar_model, energies, component)

    def night(self, osc, earth_model, site):
        latitude = site_latitude(site) if self.latitude_deg is None else self.latitude_deg
        if self.night_mode == "b3" and self.depth_km is None:
            return night_probabilities(osc, earth_model, latitude, site, split_km=self.split_km)
        if self.night_mode == "b3":
            energies, cosines, P = night_grid(osc, earth_model, site, split_km=self.split_km, depth_km=self.depth_km)
            return energies, np.einsum("eci,c->ei", P, cell_weights(cosines, np.radians(latitude)))
        half = self.nadir_bins // 2   # bins in cos nadir over [0, 1], by night
        step = 1.0 / half
        energies, cosines, P = night_grid(osc, earth_model, site, split_km=self.split_km, depth_km=self.depth_km,
                                          cos_grid=(0.5 * step, 1.0 - 0.5 * step, step))
        w = solar_weight(np.arccos(cosines), np.radians(latitude))
        return energies, np.einsum("eci,c->ei", P, w / w.sum())


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
        grids = {s: night_grid(osc, earth, s) for s in sites} if earth in crust.SITE_MODELS \
            else dict.fromkeys(sites, night_grid(osc, earth))
        night.append([np.einsum("eci,c->ei", grids[s][2], cell_weights(grids[s][1], np.radians(sites[s]["latitude_deg"])))
                      for s in sites])
        energies = grids[next(iter(sites))][0]
    return day, np.array(night), energies


def export_app(out, s12=S12_GRID, dm21=DM21_GRID, jobs=None, solar_models=None, inputs_only=False):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    inputs = collect_inputs()
    with (out / "inputs.json").open("w") as handle:
        json.dump(inputs, handle, allow_nan=False)  # read by JavaScript too
    if inputs_only:  # new cross sections, parameter sets, ...: the probability tables do not change
        return {"files": ["inputs.json"]}
    s12_axis, dm21_axis = _axis(*s12), _axis(*dm21)
    solar_models = list(solar_models or inputs["solar_models"])
    earth_models, sites = inputs["earth_models"], inputs["sites"]
    _SHARED.update(inputs=inputs, solar_models=solar_models, earth_models=earth_models, sites=sites)
    points = [(a, b) for a in s12_axis for b in dm21_axis]
    workers = jobs or multiprocessing.cpu_count()
    if earth3d.MODEL in earth_models:  # the chords of every site (independent of the oscillation parameters)
        start = time.monotonic()
        with multiprocessing.get_context("fork").Pool(min(workers, len(sites))) as pool:
            files = dict(zip(sites, pool.map(earth3d.trajectories_file, list(sites))))
        earth3d.trajectories_file.cache_clear()
        for site, path in files.items():  # the workers below fork from here
            earth3d.TRAJECTORY_FILES[site] = path
        print(f"{earth3d.MODEL}: chords of {len(sites)} sites in {time.monotonic() - start:.0f} s", file=sys.stderr)
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
