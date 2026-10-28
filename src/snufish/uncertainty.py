"""Uncertainty propagation from the inputs of each step to the final rates.

Two kinds of input uncertainty are kept apart:

- sampled (Monte Carlo): solar fluxes (each B1 model's published fractional
  errors, with its correlation matrix where published, i.e. B23) and the
  oscillation parameters of a parameter set (split-normal for asymmetric
  errors; sin^2 theta12 and Delta m^2_21 sampled independently, as the
  sources publish no correlation). Reported as a standard deviation.
- model choices: the nu_e-40Ar nuclear model (B4 variants), ES radiative
  corrections (tree level vs SNOwGLoBES's tables) and the Earth model (B3
  variants). Reported as the spread of the alternatives around the
  nominal, never folded into a sigma: the spread depends on which models
  exist, not on a probability.

Quantities are daytime 8B rates per kton-year (true neutrino energy, recoil
threshold for ES, no detector response) and the ES day-night asymmetry.
"""

import functools

import numpy as np
import pandas as pd

from .build import _write_frame
from .fluxes import components
from .paths import build_dir
from .reference.xsec import es_above
from .scan import day_fractions, night_probabilities, oscillation, parameter_sets, site_latitude
from .solar import COMPONENTS, models
from .spec import load_spec, pmns

QUANTITIES = {
    # name: detector, channel, recoil threshold (ES), site for asymmetries
    "argon_cc_b8": dict(detector="argon", channel="cc_nue_ar40", label="8B CC on 40Ar"),
    "argon_es_b8_t5": dict(detector="argon", channel="es", recoil=5.0, label="8B ES in argon, T > 5 MeV"),
    "water_es_b8_t349": dict(detector="water", channel="es", recoil=3.49, label="8B ES in water, T > 3.49 MeV"),
    "kamioka_adn_es": dict(detector="water", channel="es", recoil=3.49, site="Kamioka",
                           label="ES day-night asymmetry at Kamioka"),
}
NOMINAL = {"ar40_model": "default", "es_model": "tree", "earth_model": "prem_full"}
ALTERNATIVES = {"ar40_model": ["default", "ar40_klmv", "ar40_marley", "ar40_marley1"],
                "es_model": ["tree", "snowglobes"], "earth_model": ["prem_prob3", "prem_four", "prem_full"]}


@functools.lru_cache(maxsize=1)
def _sigma_tables():
    return pd.read_parquet(build_dir() / "B4_Sigma.parquet")


def _ar40_sigma(model, energy):
    t = _sigma_tables()
    row = t[(t.Tool == "snowglobes") & (t.Channel == "cc_nue_ar40") & (t.Variant == model)].iloc[0]
    s = np.interp(energy, row.Energy, row.Sigma, left=np.nan, right=np.nan)
    return np.where(energy < 1.504, 0.0, np.nan_to_num(s))  # NaN outside a table: not provided (lower bound)


def _es_sigma(flavour, energy, recoil, es_model, constants):
    s = es_above(energy, flavour, constants, recoil)
    if es_model == "snowglobes":  # radiative corrections as the ratio of SNOwGLoBES's total to tree level
        t = _sigma_tables()
        rows = {r.Tool: r for r in t[(t.Channel == f"es_{flavour}") & (t.Variant == "default")].itertuples()}
        ratio = np.interp(energy, rows["snowglobes"].Energy,
                          rows["snowglobes"].Sigma / rows["snufish-reference"].Sigma)
        s = s * np.nan_to_num(ratio, nan=1.0)
    return s


def _component_rates(osc, solar_model, quantity, choices, night=None):
    """Day (and, with ``night``, night) rate of 8B per kton-year, for flux scale 1."""
    q = QUANTITIES[quantity]
    spec, constants = load_spec("B5_rates"), load_spec("B4_xsec")["constants"]
    flux, energy, shape = components(spec, solar_model)["B8"]
    keep = energy > 0  # the table starts at E = 0, where the shape vanishes
    energy, shape = energy[keep], shape[keep]
    targets = spec["detectors"][q["detector"]]["targets"]
    seconds = spec["exposure"]["seconds_per_year"]
    U2 = np.abs(pmns(osc)) ** 2
    F = day_fractions(osc, solar_model, energy)
    pee_day = F @ U2[0]
    if q["channel"] == "cc_nue_ar40":
        sigma_e, sigma_x, n = _ar40_sigma(choices["ar40_model"], energy), 0.0 * energy, targets["ar40"]
    else:
        sigma_e = _es_sigma("nue", energy, q["recoil"], choices["es_model"], constants)
        sigma_x = _es_sigma("numu", energy, q["recoil"], choices["es_model"], constants)
        n = targets["electron"]

    def fold(pee):
        return n * flux * seconds * np.trapezoid(shape * (pee * sigma_e + (1 - pee) * sigma_x), energy)

    day = fold(pee_day)
    if night is None:
        return day, None
    night_e, night_p = night
    P = np.stack([np.interp(energy, night_e, night_p[:, i], left=U2[0, i]) for i in range(3)], axis=-1)
    return day, fold(np.sum(F * P, axis=1))


def _value(quantity, osc, solar_model, choices, b8_scale=1.0):
    q = QUANTITIES[quantity]
    if "site" in q:
        night = night_probabilities(osc, choices["earth_model"], site_latitude(q["site"]))
        day, nite = _component_rates(osc, solar_model, quantity, choices, night)
        return 2 * (nite - day) / (nite + day)
    day, _ = _component_rates(osc, solar_model, quantity, choices)
    return b8_scale * day


def _split_normal(rng, value, error, n):
    minus, plus = error
    z = rng.standard_normal(n)
    return value + np.where(z < 0, z * minus, z * plus)


def sample_oscillation(rng, set_name, n):
    registry = parameter_sets()
    params = {k: v for k, v in registry["defaults"].items() if isinstance(v, dict)}
    params.update({k: v for k, v in registry["sets"][set_name].items() if isinstance(v, dict)})
    draws = {k: _split_normal(rng, v["value"], v["error"], n) for k, v in params.items()}
    return [oscillation(set_name, **{k: draws[k][i] for k in draws}) for i in range(n)]


# Measured total 8B flux (SNO neutral current, all flavours), the constraint
# Super-Kamiokande applies: 5.25e6 cm^-2 s^-1 +- 3.81% (arXiv:2312.12907, fig. 42).
B8_MEASURED = {"flux": 5.25e6, "error": 0.0381, "source": "SNO NC, as applied in arXiv:2312.12907"}


def sample_b8_scale(rng, solar_model, n, b8_constraint=False):
    """8B flux multipliers: the solar model's error, or the measured flux
    (rescaling the model's 8B flux to 5.25e6 with a 3.81% error)."""
    if b8_constraint:
        scale = B8_MEASURED["flux"] / models()[solar_model]["fluxes"]["B8"]
        return scale * (1 + B8_MEASURED["error"] * rng.standard_normal(n))
    error = (models()[solar_model].get("flux_uncertainty") or {}).get("B8")
    if error is None:
        return None
    return 1 + error * rng.standard_normal(n)


def sample_flux_scales(rng, solar_model, n):
    """Array [n, 8] of multipliers of every component, with the model's correlation."""
    model = models()[solar_model]
    errors = model.get("flux_uncertainty")
    if errors is None:
        return None
    sigma = np.array([errors[c] for c in COMPONENTS])
    corr = np.array(model.get("flux_correlation") or np.eye(len(COMPONENTS)))
    return 1 + rng.multivariate_normal(np.zeros(len(COMPONENTS)), corr * np.outer(sigma, sigma), n)


def budget(set_name="juno_2025", solar_model="b23_gs98", n=300, seed=1, quantities=None, b8_constraint=False):
    """Error budget frames: one row per quantity and source, and the samples."""
    rng = np.random.default_rng(seed)
    quantities = quantities or list(QUANTITIES)
    osc0 = oscillation(set_name)
    rows, samples = [], []
    osc_draws = sample_oscillation(rng, set_name, n)
    b8_draws = sample_b8_scale(rng, solar_model, n, b8_constraint)
    flux_label = "8B flux (SNO NC)" if b8_constraint else "8B flux (solar model)"
    for quantity in quantities:
        label = QUANTITIES[quantity]["label"]
        is_ratio = "site" in QUANTITIES[quantity]
        central = _value(quantity, osc0, solar_model, NOMINAL)
        if b8_constraint and not is_ratio:
            central *= B8_MEASURED["flux"] / models()[solar_model]["fluxes"]["B8"]
        base = dict(Quantity=quantity, Label=label, Set=set_name, SolarModel=solar_model,
                    Flux="SNO NC" if b8_constraint else "solar model", Central=central)

        def add(source, kind, values=None, spread=None):
            if values is not None:
                values = np.asarray(values)
                sigma = float(np.std(values, ddof=1))
                rows.append(dict(base, Source=source, Kind=kind, Sigma=sigma,
                                 Relative=sigma / abs(central), Low=np.nan, High=np.nan))
                samples.append(dict(base, Source=source, Values=values))
            else:
                low, high = spread
                rows.append(dict(base, Source=source, Kind=kind, Sigma=np.nan,
                                 Relative=max(high - central, central - low) / abs(central), Low=low, High=high))

        osc_values = np.array([_value(quantity, o, solar_model, NOMINAL) for o in osc_draws])
        if b8_constraint and not is_ratio:
            osc_values = osc_values * B8_MEASURED["flux"] / models()[solar_model]["fluxes"]["B8"]
        add("oscillation parameters", "sampled", osc_values)
        if b8_draws is not None and not is_ratio:
            unit = b8_draws / np.mean(b8_draws)
            add(flux_label, "sampled", central * unit)
            add("total sampled", "sampled", osc_values * unit)
        else:
            add("total sampled", "sampled", osc_values)
        for choice in ("ar40_model", "es_model", "earth_model"):
            relevant = ((choice == "ar40_model" and QUANTITIES[quantity]["channel"] == "cc_nue_ar40")
                        or (choice == "es_model" and QUANTITIES[quantity]["channel"] == "es")
                        or (choice == "earth_model" and is_ratio))
            if not relevant:
                continue
            alts = [_value(quantity, osc0, solar_model, dict(NOMINAL, **{choice: a})) for a in ALTERNATIVES[choice]]
            if b8_constraint and not is_ratio:
                alts = [a * B8_MEASURED["flux"] / models()[solar_model]["fluxes"]["B8"] for a in alts]
            add({"ar40_model": "40Ar nuclear model", "es_model": "ES radiative corrections",
                 "earth_model": "Earth model"}[choice], "model spread", spread=(min(alts), max(alts)))
    return {"Budget": pd.DataFrame(rows), "Budget_Samples": pd.DataFrame(samples)}


def write_budget(sets, solar_model="b23_gs98", n=300, seed=1, b8_constraint=(False, True)):
    """Budgets for several parameter sets and both 8B flux treatments, in one frame each."""
    out = build_dir()
    out.mkdir(parents=True, exist_ok=True)
    parts = {"Budget": [], "Budget_Samples": []}
    for set_name in sets:
        for constrained in b8_constraint:
            quantities = None if not constrained else [q for q in QUANTITIES if "site" not in QUANTITIES[q]]
            frames = budget(set_name, solar_model, n, seed, quantities, constrained)
            for name, frame in frames.items():
                parts[name].append(frame)
    frames = {name: pd.concat(frame_list, ignore_index=True) for name, frame_list in parts.items()}
    for name, frame in frames.items():
        _write_frame(frame, out / f"{name}.parquet")
    return frames


def predictions(frame):
    """Per quantity, parameter set and flux treatment: the central value with
    two separate error bars, the sampled 1 sigma and the model-choice range
    (kept apart on purpose)."""
    rows = []
    for (quantity, set_name, flux), group in frame.groupby(["Quantity", "Set", "Flux"]):
        g = group.set_index("Source")
        central = g.Central.iloc[0]
        base = dict(Quantity=quantity, Label=g.Label.iloc[0], Set=set_name, Flux=flux, Value=central)
        sigma = g.loc["total sampled", "Sigma"]
        rows.append(dict(base, Series="sampled 1 sigma", **{"ValueError-": sigma, "ValueError+": sigma}))
        for source in g.index[g.Kind == "model spread"]:
            low, high = g.loc[source, "Low"], g.loc[source, "High"]
            rows.append(dict(base, Series=f"{source} range", **{"ValueError-": central - low, "ValueError+": high - central}))
    frame = pd.DataFrame(rows)
    # numeric x for plotting side by side: one slot per parameter set, series offset within it
    slots = {name: k for k, name in enumerate(dict.fromkeys(frame.Set))}
    position = []
    for quantity, set_name, series in zip(frame.Quantity, frame.Set, frame.Series):
        names = list(dict.fromkeys(frame.Series[frame.Quantity == quantity]))
        position.append(slots[set_name] + 0.12 * (names.index(series) - (len(names) - 1) / 2))
    frame["Position"] = position
    return frame
