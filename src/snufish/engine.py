"""Solar neutrino rates and their uncertainty budgets, from one set of inputs
and a provider of oscillation probabilities.

The inputs are a plain dict (fluxes, spectral shapes, cross-section tables,
detector targets, sites, parameter sets): ``snufish.export.collect_inputs``
builds it from the repository and an app bundle stores it as
``inputs.json``. Everything here is NumPy, so the same code runs in the
command line and, ported to JavaScript (web/engine.js, checked against this
module by tests/test_web_engine.py), in the web page.

A probability provider has two methods:

- ``day(osc, solar_model, component, energies)``: array [E, 3] of the
  mass-eigenstate fractions F_i(E) leaving the Sun, averaged over the
  component's production region;
- ``night(osc, earth_model, site)``: (energies, array [E, 3] of
  P(nu_i -> nu_e) through the Earth averaged over the site's nights).

:class:`TableProbabilities` interpolates the tables of an app bundle;
``snufish.export.ExactProbabilities`` runs the B2 and B3 solvers.

Uncertainties are kept in two kinds, as in ``snufish budget``: sampled
(oscillation parameters, solar fluxes with their correlations, statistics
for an exposure), reported as a standard deviation; and model choices
(cross-section model, ES radiative corrections, Earth model, solar model),
reported as the range of the alternatives and never folded into a sigma.
"""

import json
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from .reference.xsec import es_above
from .spec import pmns

PARAMETERS = ("sin2_theta12", "sin2_theta13", "sin2_theta23", "delta_cp_deg", "dm2_21_eV2", "dm2_31_eV2")
DISPLAY = {"pp": "pp", "pep": "pep", "hep": "hep", "Be7": "7Be", "B8": "8B", "N13": "13N", "O15": "15O",
           "F17": "17F"}


class Inputs:
    """The inputs dict, with its arrays converted once."""

    def __init__(self, data):
        self.data = data
        self.components = {}
        for name, info in data["components"].items():
            if "lines" in info:
                lines = np.array(info["lines"], dtype=float)
                self.components[name] = ("line", lines[:, 0], lines[:, 1])
            else:
                energy, shape = np.array(info["energy"]), np.array(info["shape"])
                keep = energy > 0  # tables start at E = 0, where the shape vanishes
                self.components[name] = ("continuum", energy[keep], shape[keep])
        self.xsec = {channel: {variant: (np.array(t["energy"]), np.array(t["sigma"])) for variant, t in table.items()}
                     for channel, table in data["xsec"].items()}
        self.es_ratio = {flavour: (np.array(t["energy"]), np.array(t["ratio"]))
                         for flavour, t in data["es_radiative_ratio"].items()}

    @classmethod
    def load(cls, path):
        with Path(path).open() as handle:
            return cls(json.load(handle))

    def __getitem__(self, key):
        return self.data[key]

    def flux(self, solar_model, component, b8_flux="model"):
        if component == "B8" and b8_flux == "sno_nc":
            return self.data["b8_measured"]["flux"]
        return self.data["solar_models"][solar_model]["fluxes"][component]

    def xsec_models(self, channel):
        return list(self.xsec.get(channel, {"default": None}))


# ---------------------------------------------------------------- parameters

def parameters(inputs, set_name=None, custom=None):
    """{parameter: {"value", "error": [minus, plus]}}: the defaults, then a
    parameter set, then ``custom`` (same form; a bare number fixes a value
    with no error)."""
    registry = inputs["parameter_sets"]
    out = {k: dict(v) for k, v in registry["defaults"].items() if isinstance(v, dict)}
    if set_name is not None:
        out.update({k: dict(v) for k, v in registry["sets"][set_name].items() if isinstance(v, dict)})
    for k, v in (custom or {}).items():
        out[k] = dict(v) if isinstance(v, dict) else {"value": float(v), "error": [0.0, 0.0]}
    return out


def oscillation(params):
    """Oscillation block (B2/B3 spec format) at the central values."""
    return dict({k: params[k]["value"] for k in PARAMETERS}, ordering="normal")


def split_normal(rng, value, error, n):
    """Draws with a different sigma below and above ``value`` (asymmetric errors)."""
    minus, plus = error
    z = rng.standard_normal(n)
    return value + np.where(z < 0, z * minus, z * plus)


def sample_oscillation(params, rng, n):
    """n oscillation blocks; parameters independent (no source publishes their correlation)."""
    draws = {k: split_normal(rng, params[k]["value"], params[k]["error"], n) for k in PARAMETERS}
    return [dict({k: float(draws[k][i]) for k in PARAMETERS}, ordering="normal") for i in range(n)]


def sample_fluxes(inputs, rng, solar_model, components, n, b8_flux="model"):
    """Array [n, len(components)] of flux multipliers (1 = the nominal flux),
    with the solar model's correlations; the measured 8B flux, when used, is
    independent of the rest. None if the model publishes no uncertainties."""
    model = inputs["solar_models"][solar_model]
    errors = model.get("flux_uncertainty")
    out = np.ones((n, len(components)))
    sampled = [c for c in components if not (c == "B8" and b8_flux == "sno_nc")]
    if sampled:
        if errors is None:
            return None
        order = inputs["component_order"]
        index = [order.index(c) for c in sampled]
        sigma = np.array([errors[c] for c in sampled])
        corr = np.array(model.get("flux_correlation") or np.eye(len(order)))[np.ix_(index, index)]
        draws = 1 + rng.multivariate_normal(np.zeros(len(sampled)), corr * np.outer(sigma, sigma), n)
        for k, c in enumerate(sampled):
            out[:, components.index(c)] = draws[:, k]
    if "B8" in components and b8_flux == "sno_nc":
        out[:, components.index("B8")] = 1 + inputs["b8_measured"]["error"] * rng.standard_normal(n)
    return out


# ---------------------------------------------------------------- rates

@dataclass(frozen=True)
class Setup:
    """Everything but the oscillation parameters."""
    solar_model: str = "b23_gs98"
    components: tuple = ("B8",)
    b8_flux: str = "model"          # "model" or "sno_nc" (measured total 8B flux)
    earth_model: str = "prem_full"
    site: str = "Kamioka"
    detector: str = "water"
    channel: str = "es"
    xsec_model: str = "default"     # nuclear model of a CC channel (B4 variants)
    es_model: str = "tree"          # "tree" or "snowglobes" (radiative corrections)
    recoil_threshold: float = 0.0   # MeV of electron kinetic energy, ES only
    period: str = "day"             # "day", "night" or "annual"
    exposure: float = None          # kton-years, for the statistical uncertainty
    profile_model: str = None       # solar model of the day fractions, if not solar_model

    def replace(self, **changes):
        return replace(self, **changes)


QUANTITY_NAMES = ("rate", "adn")
PERIODS = ("day", "night", "annual")


def check(inputs, setup, quantity="rate"):
    """Raise ValueError, with what is allowed, if ``setup`` mixes options that
    do not go together (e.g. a channel the detector does not have)."""
    def allowed(what, value, options):
        if value not in options:
            raise ValueError(f"{what} {value!r} is not available; choose one of: {', '.join(map(str, options))}")

    allowed("quantity", quantity, QUANTITY_NAMES)
    allowed("period", setup.period, PERIODS)
    allowed("solar model", setup.solar_model, list(inputs["solar_models"]))
    if not setup.components:
        raise ValueError("select at least one flux component")
    for c in setup.components:
        allowed("flux component", c, list(inputs.components))
    allowed("8B flux", setup.b8_flux, ["model", "sno_nc"])
    allowed("detector", setup.detector, list(inputs["detectors"]))
    channels = list(inputs["detectors"][setup.detector]["channels"])
    if setup.channel not in channels:
        raise ValueError(f"channel {setup.channel!r} is not available in {setup.detector}; "
                         f"choose one of: {', '.join(channels)}")
    if setup.channel == "es":
        allowed("ES model", setup.es_model, ["tree", "snowglobes"])
    else:
        allowed(f"cross-section model of {setup.channel}", setup.xsec_model, inputs.xsec_models(setup.channel))
    if setup.recoil_threshold < 0:
        raise ValueError("the recoil threshold must be >= 0")
    allowed("site", setup.site, list(inputs["sites"]))
    allowed("Earth model", setup.earth_model, list(inputs["earth_models"]))
    if setup.exposure is not None and setup.exposure <= 0:
        raise ValueError("the exposure must be > 0 (or None for no statistical uncertainty)")


def cross_sections(inputs, setup, energy):
    """(sigma nu_e, sigma nu_mu/tau) in cm^2 per target, and targets per kton."""
    detector = inputs["detectors"][setup.detector]
    targets = detector["targets"][detector["channels"][setup.channel]]
    if setup.channel == "es":
        sigmas = []
        for flavour in ("nue", "numu"):
            s = es_above(energy, flavour, inputs["constants"], setup.recoil_threshold)
            if setup.es_model == "snowglobes":
                e, ratio = inputs.es_ratio[flavour]
                s = s * np.interp(energy, e, ratio, left=1.0, right=1.0)
            sigmas.append(s)
        return sigmas[0], sigmas[1], targets
    e, sigma = inputs.xsec[setup.channel][setup.xsec_model]
    s = np.interp(energy, e, sigma, left=0.0, right=0.0)  # zero outside the table
    threshold = inputs["xsec_thresholds_MeV"].get(setup.channel, 0.0)
    return np.where(energy < threshold, 0.0, s), np.zeros_like(energy), targets


def component_rates(inputs, probabilities, setup, osc, night=True):
    """{component: dict(kind, energy, day, night)}, per kton-year: a
    continuum's differential rate per MeV of neutrino energy, or a line's
    rate per line. ``night`` False skips the Earth (night = None)."""
    U2 = np.abs(pmns(osc)) ** 2
    seconds = inputs["seconds_per_year"]
    night_e = night_p = None
    if night:
        night_e, night_p = probabilities.night(osc, setup.earth_model, setup.site)
    out = {}
    for c in setup.components:
        kind, energy, weight = inputs.components[c]
        F = probabilities.day(osc, setup.profile_model or setup.solar_model, c, energy)
        sigma_e, sigma_x, targets = cross_sections(inputs, setup, energy)
        scale = targets * inputs.flux(setup.solar_model, c, setup.b8_flux) * seconds * weight

        def rate(pee):
            return scale * (pee * sigma_e + (1 - pee) * sigma_x)

        entry = dict(kind=kind, energy=energy, day=rate(F @ U2[0]), night=None)
        if night:
            P = np.stack([np.interp(energy, night_e, night_p[:, i], left=U2[0, i]) for i in range(3)], axis=-1)
            entry["night"] = rate(np.sum(F * P, axis=1))
        out[c] = entry
    return out


def totals(rates):
    """{component: {"day", "night"}} of total rates per kton-year."""
    def total(kind, energy, values):
        if values is None:
            return np.nan
        return float(np.trapezoid(values, energy)) if kind == "continuum" else float(np.sum(values))

    return {c: {p: total(r["kind"], r["energy"], r[p]) for p in ("day", "night")} for c, r in rates.items()}


def combine(per_component, components, multipliers=None):
    """(day, night) summed over components, each scaled by its flux multiplier."""
    m = np.ones(len(components)) if multipliers is None else multipliers
    day = sum(m[k] * per_component[c]["day"] for k, c in enumerate(components))
    night = sum(m[k] * per_component[c]["night"] for k, c in enumerate(components))
    return day, night


def quantity_value(quantity, period, day, night):
    if quantity == "adn":
        return 2 * (night - day) / (night + day)
    return {"day": day, "night": night, "annual": 0.5 * (day + night)}[period]


def statistical_sigma(quantity, period, day, night, exposure):
    """Poisson error for ``exposure`` kton-years, half of it by night
    (annual average; no backgrounds)."""
    if not exposure:
        return None
    if quantity == "adn":
        D, N = day * exposure / 2, night * exposure / 2
        S = D + N
        return float(np.sqrt((4 * D / S**2) ** 2 * N + (4 * N / S**2) ** 2 * D))
    rate = quantity_value(quantity, period, day, night)
    live = exposure / 2 if period in ("day", "night") else exposure
    return float(np.sqrt(rate * live) / live)


def needs_night(quantity, period):
    return quantity == "adn" or period != "day"


def binned(rates, edges):
    """{component: {"day", "night"}} of rates per kton-year in each energy bin
    (continua integrated over the bin, lines put in the bin holding them)."""
    def counts(kind, energy, values):
        if values is None:
            return None
        if kind == "line":
            return np.histogram(energy, edges, weights=values)[0]
        cumulative = np.concatenate([[0.0], np.cumsum(0.5 * (values[1:] + values[:-1]) * np.diff(energy))])
        return np.diff(np.interp(edges, energy, cumulative))

    return {c: {p: counts(r["kind"], r["energy"], r[p]) for p in ("day", "night")} for c, r in rates.items()}


def energy_edges(inputs, components, per_decade=16):
    """Log-spaced bin edges covering the components' energies."""
    low, high = [], []
    for c in components:
        _, energy, _ = inputs.components[c]
        low.append(energy.min())
        high.append(energy.max())
    lo, hi = np.log10(max(min(low) * 0.9, 0.05)), np.log10(max(high) * 1.05)
    return np.logspace(lo, hi, max(int(np.ceil((hi - lo) * per_decade)), 4) + 1)


# ---------------------------------------------------------------- budget

RANGE_LABELS = {"xsec_model": "cross-section model", "es_model": "ES radiative corrections",
                "earth_model": "Earth model", "solar_model": "solar model"}


def alternatives(inputs, setup, choice):
    if choice == "xsec_model":
        return inputs.xsec_models(setup.channel) if setup.channel != "es" else []
    if choice == "es_model":
        return ["tree", "snowglobes"] if setup.channel == "es" else []
    if choice == "earth_model":
        return list(inputs["earth_models"])
    if choice == "solar_model":
        return list(inputs["solar_models"])
    raise KeyError(choice)


def flux_label(setup):
    measured = setup.b8_flux == "sno_nc" and "B8" in setup.components
    if len(setup.components) == 1:
        return f"{DISPLAY[setup.components[0]]} flux ({'SNO NC' if measured else 'solar model'})"
    return "solar fluxes" + (" (8B from SNO NC)" if measured else "")


def budget(inputs, probabilities, setup, params, quantity="rate", n=400, seed=1,
           ranges=("xsec_model", "es_model", "earth_model", "solar_model"), solar_range="full"):
    """(rows, samples) of the error budget of one quantity ("rate" in
    ``setup.period``, or "adn"). Rows: dict(Source, Kind, Central, Sigma,
    Relative, Low, High); samples: {source: array}. ``solar_range``
    "fluxes" takes the solar-model range from the fluxes alone, with the
    day fractions of ``setup.solar_model`` (one table instead of all; the
    density profile moves F_i by ~1e-3, the fluxes by ~10%)."""
    check(inputs, setup, quantity)
    night = needs_night(quantity, setup.period)
    comps = list(setup.components)

    def value(osc=None, s=setup, multipliers=None):
        per = totals(component_rates(inputs, probabilities, s, osc or oscillation(params), night))
        return quantity_value(quantity, s.period, *combine(per, comps, multipliers))

    rng, osc_draws, flux_draws = _draws(inputs, setup, params, n, seed)
    nominal = totals(component_rates(inputs, probabilities, setup, oscillation(params), night))
    day0, night0 = combine(nominal, comps)
    central = quantity_value(quantity, setup.period, day0, night0)

    rows, samples = [], {}

    def sampled(source, values):
        values = np.asarray(values, dtype=float)
        sigma = float(np.std(values, ddof=1))
        rows.append(dict(Source=source, Kind="sampled", Central=central, Sigma=sigma,
                         Relative=_relative(sigma, central), Low=np.nan, High=np.nan))
        samples[source] = values

    per_draw = [totals(component_rates(inputs, probabilities, setup, o, night)) for o in osc_draws]
    sampled("oscillation parameters",
            [quantity_value(quantity, setup.period, *combine(p, comps)) for p in per_draw])
    total = np.array([quantity_value(quantity, setup.period, *combine(p, comps, flux_draws[i]
                                                                       if flux_draws is not None else None))
                      for i, p in enumerate(per_draw)])
    if flux_draws is not None and not (quantity == "adn" and len(comps) == 1):  # one flux cancels in a ratio
        sampled(flux_label(setup), [quantity_value(quantity, setup.period, *combine(nominal, comps, m))
                                    for m in flux_draws])
    stat = statistical_sigma(quantity, setup.period, day0, night0, setup.exposure)
    if stat is not None:
        sampled(f"statistics ({setup.exposure:g} kt yr)", central + stat * rng.standard_normal(n))
        total = total + stat * rng.standard_normal(n)
    sampled("total sampled", total)

    for choice in ranges:
        options = alternatives(inputs, setup, choice)
        if choice == "earth_model" and not night:
            options = []
        if len(options) < 2:
            continue
        fixed = {"profile_model": setup.solar_model} if choice == "solar_model" and solar_range == "fluxes" else {}
        values = [value(s=setup.replace(**{choice: o}, **fixed)) for o in options]
        low, high = min(values), max(values)
        if high - low <= 1e-12 * abs(central):
            continue  # e.g. the solar model, when the only component's flux is measured
        label = "40Ar nuclear model" if choice == "xsec_model" and setup.channel == "cc_nue_ar40" \
            else RANGE_LABELS[choice]
        rows.append(dict(Source=label, Kind="model range", Central=central, Sigma=np.nan,
                         Relative=_relative(max(high - central, central - low), central), Low=low, High=high))
    return rows, samples


def _relative(error, central):
    return error / abs(central) if central != 0 else np.nan


def _draws(inputs, setup, params, n, seed):
    """(rng, oscillation draws, flux multipliers): the same for a budget and
    the spectra of one seed."""
    rng = np.random.default_rng(seed)
    osc_draws = sample_oscillation(params, rng, n)
    return rng, osc_draws, sample_fluxes(inputs, rng, setup.solar_model, list(setup.components), n, setup.b8_flux)


def spectra(inputs, probabilities, setup, params, edges=None, n=400, seed=1, night=True):
    """Binned rates per kton-year: dict(edges, components={c: {"day", "night"}}
    at the central parameters, day/night totals, and draws_day/draws_night
    [n, bins] of the totals for the sampled oscillation parameters and fluxes
    (the draws of ``budget`` with the same seed)."""
    check(inputs, setup)
    edges = energy_edges(inputs, setup.components) if edges is None else np.asarray(edges)
    comps = list(setup.components)
    _, osc_draws, flux_draws = _draws(inputs, setup, params, n, seed)

    def total(per, multipliers=None):
        m = np.ones(len(comps)) if multipliers is None else multipliers
        day = sum(m[k] * per[c]["day"] for k, c in enumerate(comps))
        nite = sum(m[k] * per[c]["night"] for k, c in enumerate(comps)) if night else None
        return day, nite

    nominal = binned(component_rates(inputs, probabilities, setup, oscillation(params), night), edges)
    draws = [total(binned(component_rates(inputs, probabilities, setup, o, night), edges),
                   None if flux_draws is None else flux_draws[i]) for i, o in enumerate(osc_draws)]
    day, nite = total(nominal)
    return dict(edges=edges, components=nominal, day=day, night=nite,
                draws_day=np.array([d for d, _ in draws]),
                draws_night=np.array([x for _, x in draws]) if night else None)


# ---------------------------------------------------------------- tables

def _cell(axis, x):
    """Index of the lower grid point and fraction to the next; clamped to the grid."""
    x = min(max(x, axis[0]), axis[-1])
    i = int(np.clip(np.searchsorted(axis, x, side="right") - 1, 0, len(axis) - 2))
    return i, (x - axis[i]) / (axis[i + 1] - axis[i])


def _bilinear(x_axis, y_axis, values, x, y):
    i, tx = _cell(x_axis, x)
    j, ty = _cell(y_axis, y)
    return ((1 - tx) * (1 - ty) * values[i, j] + tx * (1 - ty) * values[i + 1, j]
            + (1 - tx) * ty * values[i, j + 1] + tx * ty * values[i + 1, j + 1])


def read_table(directory, name):
    """{key: array} of a table written by ``snufish.export.write_table``."""
    directory = Path(directory)
    with (directory / f"{name}.json").open() as handle:
        meta = json.load(handle)
    out = {k: np.array(v) for k, v in meta["values"].items()}
    data = np.fromfile(directory / meta["bin"], dtype="<f4")
    for key, entry in meta["arrays"].items():
        start = entry["offset"] // 4
        out[key] = data[start:start + int(np.prod(entry["shape"]))].reshape(entry["shape"])
    return out


class TableProbabilities:
    """Probabilities interpolated from an app bundle: bilinear in
    (sin^2 theta12, Delta m^2_21), linear in log E (day) or E (night). The
    tables are computed at the default theta13, theta23, delta and Delta m^2_31;
    those enter here only through |U_ei|^2. Points outside the grid are
    clamped to its edge and counted in ``clamped``."""

    def __init__(self, directory):
        self.directory = Path(directory)
        self._tables = {}
        self.clamped = 0

    def _load(self, name):
        if name not in self._tables:
            self._tables[name] = read_table(self.directory, name)
        return self._tables[name]

    def _point(self, table, osc):
        s12, dm21 = osc["sin2_theta12"], osc["dm2_21_eV2"] * 1e5
        if not (table["s12"][0] <= s12 <= table["s12"][-1] and table["dm21"][0] <= dm21 <= table["dm21"][-1]):
            self.clamped += 1
        return s12, dm21

    def day(self, osc, solar_model, component, energies):
        t = self._load(f"day_{solar_model}")
        table_e = t[f"energy_{component}"]
        F12 = _bilinear(t["s12"], t["dm21"], t[f"F_{component}"], *self._point(t, osc))  # [E, 2]
        log_e = np.log(np.clip(energies, table_e[0], table_e[-1]))
        F1, F2 = (np.interp(log_e, np.log(table_e), F12[:, i]) for i in (0, 1))
        return np.stack([F1, F2, 1 - F1 - F2], axis=-1)

    def night(self, osc, earth_model, site):
        t = self._load(f"night_{earth_model}")
        s = list(t["sites"]).index(site)
        return t["energy"], _bilinear(t["s12"], t["dm21"], t["P"][s], *self._point(t, osc))
