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
from math import erf
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
        """Selectable models of a channel ("#" marks internal tables, e.g. B(GT)-shifted ones)."""
        return [m for m in self.xsec.get(channel, {"default": None}) if "#" not in m]


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

@dataclass(frozen=True, eq=False)
class Table:
    """An imported detector response, compared by ``id`` (so setups stay cheap to
    hash). Efficiency: ``x`` energies (MeV) and ``y`` efficiencies (0-1). Smearing:
    ``x`` true-bin edges, ``y`` observed-bin edges (MeV) and ``matrix`` [true][observed]
    probabilities (rows may sum to less than 1); ``true_axis`` "observed" (the
    true value of the observed energy) or "neutrino" (CC: E_nu, shifted by -Q)."""
    id: str
    x: tuple
    y: tuple
    matrix: tuple = ()
    true_axis: str = "observed"

    def __eq__(self, other):
        return isinstance(other, Table) and self.id == other.id

    def __hash__(self):
        return hash(self.id)


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
    period: str = "day"             # "day", "night" or "annual"
    # detector response, in observed energy (ES: electron kinetic energy T; CC: visible energy E_nu - Q)
    threshold: float = 0.0          # MeV
    resolution_a: float = 0.0       # sigma = sqrt((a sqrt(E))^2 + (b E)^2), a in MeV^1/2
    resolution_b: float = 0.0       # b: constant term, a fraction
    efficiency: float = 1.0         # plateau
    efficiency_e50: float = 0.0     # MeV where the efficiency reaches half its plateau (0: flat)
    efficiency_width: float = 0.5   # MeV, width of the logistic turn-on
    resolution_poly: tuple = ()     # (c0, c1, c2): sigma = c0 + c1 sqrt(E) + c2 E in place of a, b, with E the
                                    # total electron energy for ES (T + m_e), as Super-K publishes it
    energy_scale: float = 1.0       # observed energy = scale x true (for the energy-scale uncertainty)
    resolution_scale: float = 1.0   # sigma multiplied by this (for the resolution uncertainty)
    efficiency_table: Table = None  # imported efficiency curve, in place of efficiency and its turn-on
    smearing_table: Table = None    # imported smearing matrix, in place of the resolution
    energy_scale_error: float = 0.0     # detector uncertainties (fractions, 1 sigma), sampled in the budget:
    resolution_error: float = 0.0       # on the energy scale, on sigma,
    normalisation_error: float = 0.0    # and on the rate (efficiencies, fiducial volume, cuts...)
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

    def within(what, value, low, high):
        if not low <= value <= high:
            raise ValueError(f"{what} must be between {low:g} and {high:g} (got {value:g})")

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
    within("the threshold (MeV)", setup.threshold, 0.0, OBSERVED_MAX)
    within("the resolution a (MeV^1/2)", setup.resolution_a, 0.0, 2.0)
    within("the resolution b", setup.resolution_b, 0.0, 1.0)
    within("the efficiency", setup.efficiency, 0.0, 1.0)
    within("the efficiency turn-on (MeV)", setup.efficiency_e50, 0.0, OBSERVED_MAX)
    within("the turn-on width (MeV)", setup.efficiency_width, 1e-3, 10.0)
    if len(setup.resolution_poly) not in (0, 3):
        raise ValueError("resolution_poly takes three coefficients (c0, c1, c2)")
    within("the energy scale", setup.energy_scale, 0.5, 1.5)
    within("the resolution scale", setup.resolution_scale, 0.0, 3.0)
    within("the energy-scale uncertainty", setup.energy_scale_error, 0.0, 0.2)
    within("the resolution uncertainty", setup.resolution_error, 0.0, 1.0)
    within("the normalisation uncertainty", setup.normalisation_error, 0.0, 1.0)
    for name, table in (("efficiency", setup.efficiency_table), ("smearing", setup.smearing_table)):
        if table is not None and (len(table.x) < 2 or np.any(np.diff(table.x) <= 0)):
            raise ValueError(f"the imported {name} needs increasing energies")
    t = setup.smearing_table
    if t is not None:
        if len(t.matrix) != len(t.x) - 1 or any(len(row) != len(t.y) - 1 for row in t.matrix):
            raise ValueError("the imported smearing matrix needs one row per true bin and one column per observed bin")
        if t.true_axis == "neutrino" and setup.channel == "es":
            raise ValueError("a smearing matrix in neutrino energy applies to CC channels only")
    allowed("site", setup.site, list(inputs["sites"]))
    allowed("Earth model", setup.earth_model, list(inputs["earth_models"]))
    if setup.exposure is not None and setup.exposure <= 0:
        raise ValueError("the exposure must be > 0 (or None for no statistical uncertainty)")


# ---------------------------------------------------------------- observed energy

OBSERVED_MIN, OBSERVED_MAX = 0.01, 25.0   # MeV; a first bin [0, 0.01] collects everything below
PER_DECADE, FINE = 16, 4                  # display bins per decade, fine bins per display bin


def observed_edges(threshold=0.0):
    """(fine, display) bin edges in observed energy: 0, then log-spaced from
    0.01 to 25 MeV; the threshold is a fine edge, so the cut is exact."""
    n = int(round(np.log10(OBSERVED_MAX / OBSERVED_MIN) * PER_DECADE))
    display = np.concatenate([[0.0], np.logspace(np.log10(OBSERVED_MIN), np.log10(OBSERVED_MAX), n + 1)])
    fine = np.concatenate([[0.0], np.logspace(np.log10(OBSERVED_MIN), np.log10(OBSERVED_MAX), n * FINE + 1)])
    if threshold > 0 and not np.any(np.isclose(fine, threshold, rtol=0, atol=1e-9)):
        fine = np.sort(np.append(fine, threshold))
    return fine, display


def observable(channel):
    return "Electron kinetic energy T (MeV)" if channel == "es" else "Visible energy E_nu - Q (MeV)"


def _quadrature(kind, energy, weight):
    """Weights q_k with sum_k q_k f(E_k) = the trapezoid integral of shape * f (continuum),
    or sum of branching * f (lines)."""
    if kind == "line":
        return weight
    q = np.zeros_like(energy)
    q[:-1] += 0.5 * np.diff(energy)
    q[1:] += 0.5 * np.diff(energy)
    return q * weight


def _targets(inputs, setup):
    detector = inputs["detectors"][setup.detector]
    return detector["targets"][detector["channels"][setup.channel]]


def _kernels(inputs, setup, component, edges):
    """Cached, oscillation-independent pieces of one component: ES: per neutrino
    energy, the cross section into each recoil bin [E, bins] for nu_e and nu_x;
    CC: the cross section sigma(E)."""
    key = (component, setup.detector, setup.channel, setup.es_model, setup.xsec_model, setup.threshold)
    cache = inputs.__dict__.setdefault("_kernels", {})
    if key not in cache:
        kind, energy, weight = inputs.components[component]
        if setup.channel == "es":
            out = []
            for flavour in ("nue", "numu"):
                above = np.stack([es_above(energy, flavour, inputs["constants"], t) for t in edges], axis=1)
                k = above[:, :-1] - above[:, 1:]  # sigma(E; T in bin), exact for the tree-level formula
                if setup.es_model == "snowglobes":
                    e, ratio = inputs.es_ratio[flavour]
                    k = k * np.interp(energy, e, ratio, left=1.0, right=1.0)[:, None]
                out.append(k)
            cache[key] = tuple(out)
        else:
            e, sigma = inputs.xsec[setup.channel][setup.xsec_model]
            s = np.interp(energy, e, sigma, left=0.0, right=0.0)  # zero outside the table
            cache[key] = np.where(energy < inputs["xsec_thresholds_MeV"].get(setup.channel, 0.0), 0.0, s)
    return cache[key]


def resolution(inputs, setup, energy):
    """sigma (MeV) at observed energies: sqrt((a sqrt(E))^2 + (b E)^2), or Super-K's
    c0 + c1 sqrt(E) + c2 E in total electron energy (ES); times resolution_scale."""
    energy = np.asarray(energy, dtype=float)
    if setup.resolution_poly:
        c0, c1, c2 = setup.resolution_poly
        total = energy + (inputs["constants"]["m_e_MeV"] if setup.channel == "es" else 0.0)
        sigma = np.maximum(c0 + c1 * np.sqrt(total) + c2 * total, 0.0)
    else:
        sigma = np.hypot(setup.resolution_a * np.sqrt(energy), setup.resolution_b * energy)
    return setup.resolution_scale * sigma


def _response_key(setup):
    return (setup.channel, setup.threshold, setup.resolution_a, setup.resolution_b, tuple(setup.resolution_poly),
            setup.energy_scale, setup.resolution_scale, setup.efficiency, setup.efficiency_e50, setup.efficiency_width,
            setup.efficiency_table and setup.efficiency_table.id, setup.smearing_table and setup.smearing_table.id)


def _imported_matrix(inputs, setup, edges):
    """[fine true bin, fine observed bin] from an imported smearing matrix: each fine bin
    takes the row of the imported true bin holding its centre (none outside: kept as
    is), each imported observed bin spread over the fine bins it overlaps."""
    t = setup.smearing_table
    true_edges = np.asarray(t.x, float)
    if t.true_axis == "neutrino":
        true_edges = true_edges - inputs["visible_offset_MeV"][setup.channel]
    obs = setup.energy_scale * np.asarray(t.y, float)
    probs = np.asarray(t.matrix, float)
    spread = np.clip(np.minimum(obs[1:, None], edges[None, 1:]) - np.maximum(obs[:-1, None], edges[None, :-1]), 0, None)
    spread = spread / np.diff(obs)[:, None]   # [imported observed bin, fine observed bin]
    centres = 0.5 * (edges[1:] + edges[:-1])
    matrix = np.eye(len(centres))
    inside = (centres >= true_edges[0]) & (centres < true_edges[-1])
    rows = np.searchsorted(true_edges, centres[inside], side="right") - 1
    matrix[inside] = probs[rows] @ spread
    return matrix


def _response(inputs, setup, edges):
    """(matrix [true bin, observed bin], acceptance per observed bin): energy scale,
    Gaussian resolution, efficiency and threshold. Identity and ones for a perfect detector."""
    key = _response_key(setup)
    cache = inputs.__dict__.setdefault("_responses", {})
    if key not in cache:
        centres = 0.5 * (edges[1:] + edges[:-1])
        sigma = np.zeros_like(centres) if setup.smearing_table is not None else resolution(inputs, setup, centres)
        scale = setup.energy_scale
        matrix = np.eye(len(centres))
        if setup.smearing_table is not None:
            matrix = _imported_matrix(inputs, setup, edges)
        elif scale != 1.0:  # without resolution: each bin's content spread uniformly over its scaled width
            low, high = scale * edges[:-1], scale * edges[1:]
            overlap = np.clip(np.minimum(high[:, None], edges[None, 1:]) - np.maximum(low[:, None], edges[None, :-1]), 0, None)
            matrix = overlap / (high - low)[:, None]
            matrix[:, -1] += 1 - matrix.sum(axis=1)  # scaled beyond the last edge: kept in the last bin
        smeared = sigma > 0
        if np.any(smeared):
            cdf = np.vectorize(lambda z: 0.5 * (1 + erf(z / np.sqrt(2))))
            z = (edges[None, :] - scale * centres[smeared, None]) / sigma[smeared, None]
            rows = np.diff(cdf(z), axis=1)
            rows[:, 0] += cdf(z[:, 0])         # smeared below 0: the first bin (below any threshold)
            rows[:, -1] += 1 - cdf(z[:, -1])   # above the last edge: the last bin
            matrix[smeared] = rows
        acceptance = np.full(len(centres), setup.efficiency)
        if setup.efficiency_table is not None:
            t = setup.efficiency_table
            acceptance = np.interp(centres, t.x, t.y, left=0.0, right=t.y[-1])
        elif setup.efficiency_e50 > 0:
            acceptance = acceptance / (1 + np.exp(-(centres - setup.efficiency_e50) / setup.efficiency_width))
        acceptance = np.where(edges[:-1] >= setup.threshold - 1e-12, acceptance, 0.0)
        cache[key] = (matrix, acceptance)
    return cache[key]


def survival(inputs, probabilities, setup, osc, night=True):
    """{component: (P_ee by day, P_ee by night or None)} at the component's energies."""
    U2 = np.abs(pmns(osc)) ** 2
    night_e = night_p = None
    if night:
        night_e, night_p = probabilities.night(osc, setup.earth_model, setup.site)
    out = {}
    for c in setup.components:
        energy = inputs.components[c][1]
        F = probabilities.day(osc, setup.profile_model or setup.solar_model, c, energy)
        pee_night = None
        if night:
            P = np.stack([np.interp(energy, night_e, night_p[:, i], left=U2[0, i]) for i in range(3)], axis=-1)
            pee_night = np.sum(F * P, axis=1)
        out[c] = (F @ U2[0], pee_night)
    return out


def _visible(inputs, setup, kind, energy, density, edges):
    """CC: the rate in each fine bin of visible energy E - Q (a continuum's density
    integrated over the bin, lines in the bin holding them; below the first edge: first bin)."""
    shifted = edges + inputs["visible_offset_MeV"][setup.channel]
    shifted[0], shifted[-1] = -np.inf, np.inf
    if kind == "line":
        return np.histogram(energy, shifted, weights=density)[0].astype(float)
    cumulative = np.concatenate([[0.0], np.cumsum(0.5 * (density[1:] + density[:-1]) * np.diff(energy))])
    return np.diff(np.interp(shifted, energy, cumulative, left=0.0, right=cumulative[-1]))


def observed_rates(inputs, probabilities, setup, osc, night=True):
    """{component: {"day", "night"}}: interactions per kton-year in each fine
    bin of observed energy (``observed_edges``), after the detector response.
    The reference path: ``component_totals`` and ``component_spectra`` give the
    same numbers faster."""
    edges, _ = observed_edges(setup.threshold)
    matrix, acceptance = _response(inputs, setup, edges)
    seconds, targets = inputs["seconds_per_year"], _targets(inputs, setup)
    out = {}
    for c, (pee_day, pee_night) in survival(inputs, probabilities, setup, osc, night).items():
        kind, energy, weight = inputs.components[c]
        scale = targets * inputs.flux(setup.solar_model, c, setup.b8_flux) * seconds
        kernels = _kernels(inputs, setup, c, edges)

        def spectrum(pee):
            if pee is None:
                return None
            if setup.channel == "es":
                q = scale * _quadrature(kind, energy, weight)
                true = (q * pee) @ kernels[0] + (q * (1 - pee)) @ kernels[1]
            else:
                true = _visible(inputs, setup, kind, energy, scale * weight * pee * kernels, edges)
            return (true @ matrix) * acceptance

        out[c] = {"day": spectrum(pee_day), "night": spectrum(pee_night)}
    return out


def _prepared(inputs, setup, component):
    """Cached products of the kernels with the detector response, so that a draw
    costs one short product per component: for each true bin, the accepted
    fraction g = R a; ES also the kernels times g (totals) and times R, a and the
    display re-binning (spectra)."""
    key = (component, setup.detector, setup.channel, setup.es_model, setup.xsec_model) + _response_key(setup)
    cache = inputs.__dict__.setdefault("_prepared", {})
    if key not in cache:
        edges, display = observed_edges(setup.threshold)
        matrix, acceptance = _response(inputs, setup, edges)
        identity = bool(np.array_equal(matrix, np.eye(len(matrix))))

        def observe(rows):  # true bins (last axis) -> accepted, display-binned observed bins
            smeared = rows if identity else rows @ matrix
            return np.apply_along_axis(rebin, -1, smeared * acceptance, edges, display)

        kind, energy, weight = inputs.components[component]
        prep = dict(edges=edges, display=display, matrix=matrix, acceptance=acceptance, identity=identity,
                    accepted=acceptance if identity else matrix @ acceptance)
        kernels = _kernels(inputs, setup, component, edges)
        if setup.channel == "es":
            q = _quadrature(kind, energy, weight)
            diff, base = kernels[0] - kernels[1], q @ kernels[1]  # true = (q P) @ (K_e - K_x) + q @ K_x
            prep.update(q=q, diff_total=diff @ prep["accepted"], base_total=float(base @ prep["accepted"]),
                        diff_display=observe(diff), base_display=observe(base))
        else:
            prep.update(sigma=kernels)
        cache[key] = prep
    return cache[key]


def _fast(inputs, probabilities, setup, osc, night, spectra):
    out = {}
    for c, peeses in survival(inputs, probabilities, setup, osc, night).items():
        kind, energy, weight = inputs.components[c]
        prep = _prepared(inputs, setup, c)
        scale = inputs["seconds_per_year"] * _targets(inputs, setup) * inputs.flux(setup.solar_model, c, setup.b8_flux)

        def value(pee):
            if pee is None:
                return None if spectra else np.nan
            if setup.channel == "es":
                w = prep["q"] * pee
                if spectra:
                    return scale * (w @ prep["diff_display"] + prep["base_display"])
                return float(scale * (w @ prep["diff_total"] + prep["base_total"]))
            true = _visible(inputs, setup, kind, energy, scale * weight * pee * prep["sigma"], prep["edges"])
            if not spectra:
                return float(true @ prep["accepted"])
            smeared = true if prep["identity"] else true @ prep["matrix"]
            return rebin(smeared * prep["acceptance"], prep["edges"], prep["display"])

        out[c] = {"day": value(peeses[0]), "night": value(peeses[1])}
    return out


def component_totals(inputs, probabilities, setup, osc, night=True):
    """{component: {"day", "night"}} of observed rates per kton-year (= totals of observed_rates)."""
    return _fast(inputs, probabilities, setup, osc, night, spectra=False)


def component_spectra(inputs, probabilities, setup, osc, night=True):
    """{component: {"day", "night"}} per display bin of observed energy (= observed_rates re-binned)."""
    return _fast(inputs, probabilities, setup, osc, night, spectra=True)


def flux_summary(inputs, probabilities, setup, osc):
    """Flux at Earth of the selected components (cm^-2 s^-1) and the flux-weighted
    nu_e fraction by day: dict(total, nue_day, components={c: (flux, mean P_ee by day)})."""
    out = {}
    for c, (pee, _) in survival(inputs, probabilities, setup, osc, night=False).items():
        kind, energy, weight = inputs.components[c]
        out[c] = (inputs.flux(setup.solar_model, c, setup.b8_flux), float(_quadrature(kind, energy, weight) @ pee))
    total = sum(f for f, _ in out.values())
    return dict(total=total, nue_day=sum(f * p for f, p in out.values()) / total, components=out)


def totals(rates):
    """{component: {"day", "night"}} of total rates per kton-year."""
    return {c: {p: (float(np.sum(r[p])) if r[p] is not None else np.nan) for p in ("day", "night")}
            for c, r in rates.items()}


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


def rebin(values, fine, display):
    """Fine-bin values summed into the display bins (each fine bin goes where its centre falls)."""
    index = np.clip(np.searchsorted(display, 0.5 * (fine[1:] + fine[:-1])) - 1, 0, len(display) - 2)
    return np.bincount(index, weights=values, minlength=len(display) - 1)


# ---------------------------------------------------------------- budget

RANGE_LABELS = {"xsec_model": "cross-section model", "es_model": "ES radiative corrections",
                "earth_model": "Earth model", "solar_model": "solar model"}


def alternatives(inputs, setup, choice):
    if choice == "xsec_model":  # without the tables that are incomplete (zero below 5 MeV)
        incomplete = inputs.data.get("xsec_incomplete", {}).get(setup.channel, [])
        return [m for m in inputs.xsec_models(setup.channel) if m not in incomplete] if setup.channel != "es" else []
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
        per = component_totals(inputs, probabilities, s, osc or oscillation(params), night)
        return quantity_value(quantity, s.period, *combine(per, comps, multipliers))

    rng, osc_draws, flux_draws = _draws(inputs, setup, params, n, seed)
    nominal = component_totals(inputs, probabilities, setup, oscillation(params), night)
    day0, night0 = combine(nominal, comps)
    central = quantity_value(quantity, setup.period, day0, night0)

    rows, samples = [], {}

    def sampled(source, values):
        values = np.asarray(values, dtype=float)
        sigma = float(np.std(values, ddof=1))
        rows.append(dict(Source=source, Kind="sampled", Central=central, Sigma=sigma,
                         Relative=_relative(sigma, central), Low=np.nan, High=np.nan))
        samples[source] = values

    per_draw = [component_totals(inputs, probabilities, setup, o, night) for o in osc_draws]
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
    for source, sigma in (detector_sigmas(inputs, probabilities, setup, params, quantity, central, night)
                          + level_sigmas(inputs, probabilities, setup, params, quantity, central, night)):
        z = rng.standard_normal(n)  # one Gaussian draw per source: its row and its share of the total
        sampled(source, central + sigma * z)
        total = total + sigma * z
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


DETECTOR_SOURCES = ("energy_scale_error", "resolution_error", "normalisation_error")


def detector_sigmas(inputs, probabilities, setup, params, quantity, central, night):
    """[(source, sigma)] of the detector uncertainties that are set: the quantity at
    the energy scale (or resolution) shifted by +-1 sigma, half the difference; the
    normalisation scales a rate (and cancels in A_DN)."""
    def value(s):
        per = component_totals(inputs, probabilities, s, oscillation(params), night)
        return quantity_value(quantity, s.period, *combine(per, list(s.components)))

    out = []
    if setup.energy_scale_error > 0:
        e = setup.energy_scale_error
        up, down = (value(setup.replace(energy_scale=setup.energy_scale * (1 + k * e))) for k in (1, -1))
        out.append((f"energy scale (±{100 * e:g} %)", abs(up - down) / 2))
    if setup.resolution_error > 0 and setup.smearing_table is None:  # an imported matrix has no sigma to scale
        r = setup.resolution_error
        up, down = (value(setup.replace(resolution_scale=setup.resolution_scale * (1 + k * r))) for k in (1, -1))
        out.append((f"energy resolution (±{100 * r:g} %)", abs(up - down) / 2))
    if setup.normalisation_error > 0 and quantity == "rate":
        out.append((f"detector normalisation (±{100 * setup.normalisation_error:g} %)",
                    abs(central) * setup.normalisation_error))
    return out


def level_sigmas(inputs, probabilities, setup, params, quantity, central, night):
    """[(source, sigma)] of measured nuclear strengths, when the cross-section model has
    them: one table per level with its B(GT) raised by 1 sigma (sigma is linear in each),
    levels independent, so sigma^2 = sum of the squared shifts of the quantity."""
    if setup.channel == "es":
        return []
    levels = inputs.data.get("xsec_levels", {}).get(setup.channel, {}).get(setup.xsec_model)
    if not levels:
        return []
    def value(s):
        per = component_totals(inputs, probabilities, s, oscillation(params), night)
        return quantity_value(quantity, s.period, *combine(per, list(s.components)))
    variance = sum((value(setup.replace(xsec_model=level["name"])) - central) ** 2 for level in levels)
    return [(f"measured B(GT) ({len(levels)} levels)", float(np.sqrt(variance)))]


def _relative(error, central):
    return error / abs(central) if central != 0 else np.nan


def _draws(inputs, setup, params, n, seed):
    """(rng, oscillation draws, flux multipliers): the same for a budget and
    the spectra of one seed."""
    rng = np.random.default_rng(seed)
    osc_draws = sample_oscillation(params, rng, n)
    return rng, osc_draws, sample_fluxes(inputs, rng, setup.solar_model, list(setup.components), n, setup.b8_flux)


def spectra(inputs, probabilities, setup, params, n=400, seed=1, night=True):
    """Rates per kton-year in display bins of observed energy: dict(edges,
    observable, components={c: {"day", "night"}} at the central parameters,
    day/night totals, and draws_day/draws_night [n, bins] of the totals for the
    sampled oscillation parameters and fluxes (the draws of ``budget`` with the
    same seed)."""
    check(inputs, setup)
    _, display = observed_edges(setup.threshold)
    comps = list(setup.components)
    _, osc_draws, flux_draws = _draws(inputs, setup, params, n, seed)

    def total(per, multipliers=None):
        m = np.ones(len(comps)) if multipliers is None else multipliers
        day = sum(m[k] * per[c]["day"] for k, c in enumerate(comps))
        return day, (sum(m[k] * per[c]["night"] for k, c in enumerate(comps)) if night else None)

    nominal = component_spectra(inputs, probabilities, setup, oscillation(params), night)
    draws = [total(component_spectra(inputs, probabilities, setup, o, night),
                   None if flux_draws is None else flux_draws[i]) for i, o in enumerate(osc_draws)]
    day, nite = total(nominal)
    return dict(edges=display, observable=observable(setup.channel), components=nominal, day=day, night=nite,
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
