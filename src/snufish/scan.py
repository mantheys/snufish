"""Solar observables as a function of the oscillation parameters.

For a parameter point (sin^2 theta12, Delta m^2_21, the rest from the
defaults of reference/oscillation/parameter_sets.yaml) this computes, for
8B neutrinos at a detector site:

- the daytime survival probability P_ee(E) (B2 reference, adiabatic, the
  solar model's own production profile) and its quadratic coefficients
  around 10 MeV, compared with the SK + SNO measurement;
- the night P_ee(E), from P(nu_i -> nu_e) through the Earth (NuFast-Earth,
  validated against the B3 reference) averaged over the site's annual
  exposure;
- the day-night asymmetry 2 (N - D) / (N + D) of P_ee (5-15 MeV, flux
  weighted) and of the elastic-scattering rate above an electron recoil
  threshold (the quantity Super-Kamiokande measures).

Everything is computed directly (no contributions): the solvers are the
ones the B2 and B3 benchmarks validate.
"""

import copy
import functools
import subprocess

import numpy as np
import yaml

from . import crust
from .exposure import cell_weights
from .fluxes import components
from .paths import repo_root
from .reference.sun import adiabatic_fractions
from .reference.xsec import es_above
from .solar import production_weights
from .spec import load_spec, pmns

COMPONENT = "B8"


@functools.lru_cache(maxsize=1)
def parameter_sets():
    with (repo_root() / "reference" / "oscillation" / "parameter_sets.yaml").open() as handle:
        return yaml.safe_load(handle)


@functools.lru_cache(maxsize=1)
def measurements():
    with (repo_root() / "reference" / "measurements" / "solar.yaml").open() as handle:
        return yaml.safe_load(handle)


def oscillation(set_name=None, **override):
    """Oscillation block (B2/B3 spec format) of a parameter set, with overrides."""
    registry = parameter_sets()
    values = {k: v["value"] for k, v in registry["defaults"].items() if isinstance(v, dict)}
    if set_name is not None:
        values.update({k: v["value"] for k, v in registry["sets"][set_name].items() if isinstance(v, dict)})
    values.update(override)
    return {"sin2_theta12": values["sin2_theta12"], "sin2_theta13": values["sin2_theta13"],
            "sin2_theta23": values["sin2_theta23"], "delta_cp_deg": values["delta_cp_deg"],
            "dm2_21_eV2": values["dm2_21_eV2"], "dm2_31_eV2": values["dm2_31_eV2"], "ordering": "normal"}


def _with_oscillation(spec, osc):
    out = copy.copy(spec)
    out.data = dict(spec.data, oscillation=osc)
    return out


def day_fractions(osc, solar_model, energies, component=COMPONENT):
    """F_i(E) averaged over the component's production profile: array [E, 3]."""
    spec = _with_oscillation(load_spec("B2_sun"), osc)
    radii = spec.axis("radius")
    F = adiabatic_fractions(spec, solar_model, energies, radii)
    w = production_weights(solar_model, radii, spec)[component]
    return np.einsum("r,rei->ei", w, F)


def _nufast_driver():
    path = repo_root() / "contributions" / "nufast-earth" / "scripts" / "b3_driver"
    if not path.exists():
        raise FileNotFoundError(f"{path} not built: cd {path.parent} && make")
    return path


def night_probabilities(osc, earth_model, latitude_deg, site=None):
    """(energies MeV, array [E, 3] of P(nu_i -> nu_e) averaged over the night at
    the given latitude), on the B3 exposure grid. ``site``: for the site-dependent
    Earth models (:mod:`snufish.crust`)."""
    energies, cosines, P = night_grid(osc, earth_model, site)
    return energies, np.einsum("eci,c->ei", P, cell_weights(cosines, np.radians(latitude_deg)))


def night_grid(osc, earth_model, site=None, depth_km=None, cos_grid=None):
    """(energies MeV, cos nadir, array [E, cos, 3] of P(nu_i -> nu_e)) on the
    B3 exposure grid, before averaging over a site's night. ``depth_km``: the
    detector depth (default B3's, 0); ``cos_grid``: (start, stop, step) of cos nadir
    in place of B3's."""
    spec = load_spec("B3_earth")
    grid = {a: dict(v) for a, v in spec["grids"]["exposure"].items()}
    if cos_grid is not None:
        grid["cos_nadir"].update(zip(("start", "stop", "step"), map(float, cos_grid)))
    if earth_model in crust.SITE_MODELS:
        if site is None:
            raise ValueError(f"{earth_model} depends on the site")
        earth_model = f"regions:{crust.regions_file(earth_model, site)}"
    argv = [earth_model, *(str(osc[k]) for k in ("sin2_theta12", "sin2_theta13", "sin2_theta23", "delta_cp_deg",
                                                 "dm2_21_eV2", "dm2_31_eV2")),
            str(spec["earth"]["detector_depth_km"] if depth_km is None else float(depth_km)),
            *(str(grid[a][k]) for a in ("energy", "cos_nadir") for k in ("start", "stop", "step"))]
    out = subprocess.run([str(_nufast_driver()), *argv], capture_output=True, text=True, check=True).stdout
    table = np.loadtxt(out.splitlines())
    energies = spec.axis("energy", "exposure")
    c = grid["cos_nadir"]
    cosines = (spec.axis("cos_nadir", "exposure") if cos_grid is None
               else c["start"] + c["step"] * np.arange(int(round((c["stop"] - c["start"]) / c["step"])) + 1))
    P = table[:, [2, 5, 8]].reshape(len(energies), len(cosines), 3)  # m[i][e], rows E-major
    return energies, cosines, P


def site_latitude(site):
    return load_spec("B3_earth")["sites"][site]["latitude_deg"]


def observables(osc, solar_model="b16_gs98", earth_model="prem_full", site="Kamioka",
                recoil_threshold=None):
    """Dict of the 8B observables for one parameter point."""
    measured = measurements()
    if recoil_threshold is None:
        recoil_threshold = measured["sk_day_night"]["recoil_kinetic_threshold_MeV"]
    U2 = np.abs(pmns(osc)) ** 2
    constants = load_spec("B4_xsec")["constants"]
    _, energy, shape = components(load_spec("B5_rates"), solar_model)[COMPONENT]
    energy, shape = energy[energy > 0.2], shape[energy > 0.2]

    F = day_fractions(osc, solar_model, energy)
    pee_day = F @ U2[0]
    night_e, night_p = night_probabilities(osc, earth_model, site_latitude(site), site)
    P_night = np.stack([np.interp(energy, night_e, night_p[:, i], left=U2[0, i]) for i in range(3)], axis=-1)
    pee_night = np.sum(F * P_night, axis=1)

    window = (energy >= 5) & (energy <= 15)
    day_avg = np.trapezoid((shape * pee_day)[window], energy[window])
    night_avg = np.trapezoid((shape * pee_night)[window], energy[window])

    s_e = es_above(energy, "nue", constants, recoil_threshold)
    s_x = es_above(energy, "numu", constants, recoil_threshold)
    rate_day = np.trapezoid(shape * (pee_day * s_e + (1 - pee_day) * s_x), energy)
    rate_night = np.trapezoid(shape * (pee_night * s_e + (1 - pee_night) * s_x), energy)

    quad = measured["sk_sno_pee_quadratic"]
    lo, hi = quad["valid_MeV"]
    fit = (energy >= lo) & (energy <= hi)
    x = energy[fit] - 10.0
    c2, c1, c0 = np.polyfit(x, pee_day[fit], 2)
    c = np.array([c0, c1, c2])
    sigma = np.array(quad["errors"])
    cov = np.array(quad["correlation"]) * np.outer(sigma, sigma)
    resid = c - np.array(quad["c"])
    return {
        "energy": energy, "pee_day": pee_day, "pee_night": pee_night,
        "adn_pee": 2 * (night_avg - day_avg) / (night_avg + day_avg),
        "adn_es": 2 * (rate_night - rate_day) / (rate_night + rate_day),
        "pee_10": c0, "slope_10": c1, "curvature_10": c2,
        "upturn": float(np.interp(4.0, energy, pee_day) - np.interp(10.0, energy, pee_day)),
        "chi2_quadratic": float(resid @ np.linalg.solve(cov, resid)),
    }


def sk_day_night():
    """Super-Kamiokande A_DN in the SNUfish convention (value, total error)."""
    m = measurements()["sk_day_night"]
    return -m["value"], float(np.hypot(m["stat"], m["syst"]))


SCAN_OBSERVABLES = ("adn_es", "adn_pee", "pee_10", "slope_10", "upturn", "chi2_quadratic")


def scan(dm2_values, earth_models=("prem_prob3", "prem_four", "prem_full"), site="Kamioka",
         solar_model="b16_gs98", sin2_theta12=None):
    """Frames for plotipus: the observables against Delta m^2_21 (one row per
    Earth model and observable) and at every parameter set."""
    import pandas as pd

    s12 = sin2_theta12 or parameter_sets()["sets"]["nufit60_global"]["sin2_theta12"]["value"]
    rows = []
    for earth_model in earth_models:
        values = {k: [] for k in SCAN_OBSERVABLES}
        for dm2 in dm2_values:
            o = observables(oscillation("nufit60_global", dm2_21_eV2=dm2 * 1e-5, sin2_theta12=s12),
                            solar_model, earth_model, site)
            for k in SCAN_OBSERVABLES:
                values[k].append(o[k])
        for k in SCAN_OBSERVABLES:
            rows.append(dict(EarthModel=earth_model, Site=site, SolarModel=solar_model, Observable=k,
                             DM21=np.asarray(dm2_values, dtype=float), Value=np.asarray(values[k])))
    sets = []
    for name, info in parameter_sets()["sets"].items():
        for earth_model in earth_models:
            o = observables(oscillation(name), solar_model, earth_model, site)
            sets.append(dict(Set=name, Label=info["label"], Kind=info["kind"], EarthModel=earth_model, Site=site,
                             DM21=info["dm2_21_eV2"]["value"] * 1e5,
                             **{k: o[k] for k in SCAN_OBSERVABLES}))
    return {"Scan_DM21": pd.DataFrame(rows), "Scan_Sets": pd.DataFrame(sets)}
