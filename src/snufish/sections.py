"""What each benchmark contributes to the uncertainty of a result (``snufish
export-sections``): ``sections.json`` for the web page's benchmark pages.

    snufish export-app --out build/app          # the tables first
    snufish export-sections --tables build/app  # writes build/app/sections.json

For a few reference observables (``OBSERVABLES``), the engine's error budget
on the app tables, each source assigned to the benchmark it comes from
(``SECTION_OF``), the benchmarks being the calculator's steps: B1 the
oscillation parameters, B2 the Sun (the solar fluxes, and the density and
production profiles), B3 the Earth model, B4 the cross sections, B5 the
statistics of a reference exposure (``EXPOSURE``) and the published detector
uncertainties of each observable's detector (its response from the B5 spec,
part 2: ``RESPONSE``). B2 adds the
approximations some solvers make about where neutrinos are produced
(``TREATMENTS``): signed shifts of the observable, computed with the exact
B2 solver (the tables hold each component's own profile only). B3's model
range is the engine's, over the current Earth models (the local crust under
the detector, radial, and the crust along each night chord, earth3d.py); B3
adds the Earth models that approximate the state of the art
(reference/status.yaml), as signed shifts from it, and the solver's
approximation, NuFast-Earth's mean density per region crossing, against the
thin shells (scan.SPLIT_KM) the tables and the exact solvers use. With them,
per benchmark, the curves its pages plot (solar profiles, P_ee per
component, regeneration per Earth model) and the agreement between tools.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import engine
from . import export
from .export import MARLEY_DEFAULT
from .reference import nc_ar40 as nc_ar40_reference
from .paths import build_dir, contributions_dir, repo_root
from .reference.sun import adiabatic_fractions, fractions_at_density
from .scan import _with_oscillation
from .solar import COMPONENTS, electron_density, production_weights, table
from .spec import load_spec, pmns

SET, SOLAR_MODEL = "juno_2025", "b23_mb22m"  # state of the art (reference/status.yaml)
N_DRAWS, SEED = 1000, 1  # a sampled sigma to about 2 % (1/sqrt(2n))
EXPOSURE = 100.0  # kt yr: B5's statistics, e.g. 10 kt for 10 years
# Each observable is seen through its detector's published response (B5 spec, part 2): threshold, resolution,
# efficiency and detector uncertainties of Super-K IV (water), DUNE (argon) and Borexino Phase-II (scintillator).
OBSERVABLES = {
    "water_es_b8": dict(label="8B + hep ES in water, Super-K IV response (T > 3.49 MeV), Kamioka", quantity="rate",
                        setup=dict(detector="water", channel="es", components=("B8", "hep"), site="Kamioka",
                                   period="annual")),
    "argon_cc_b8": dict(label="8B CC on 40Ar, DUNE response (visible energy > 5 MeV, 20 %), SURF", quantity="rate",
                        setup=dict(detector="argon", channel="cc_nue_ar40", components=("B8",), site="SURF",
                                   xsec_model=MARLEY_DEFAULT, period="annual")),
    "argon_cc_hep": dict(label="hep CC on 40Ar, DUNE response, SURF", quantity="rate",
                         setup=dict(detector="argon", channel="cc_nue_ar40", components=("hep",), site="SURF",
                                    xsec_model=MARLEY_DEFAULT, period="annual")),
    "scint_es_be7": dict(label="7Be ES in scintillator, Borexino Phase-II response (T > 0.05 MeV), LNGS", quantity="rate",
                         setup=dict(detector="scintillator_pc", channel="es", components=("Be7",), site="LNGS",
                                    period="annual")),
    "water_es_adn": dict(label="8B + hep ES day-night asymmetry, Super-K IV response, Kamioka", quantity="adn",
                         setup=dict(detector="water", channel="es", components=("B8", "hep"), site="Kamioka")),
    # NC has no visible-energy model (a cut in E_nu only) and no published DUNE response: a perfect detector
    "argon_nc_b8": dict(label="8B + hep NC on 40Ar, E_nu > 5 MeV, no detector response, SURF", quantity="rate",
                        response=False,
                        setup=dict(detector="argon", channel="nc_ar40", components=("B8", "hep"), site="SURF",
                                   xsec_model="default", period="annual", nu_threshold=5.0)),
}
NC_READING = "NC continuum read from its figure (Van Dessel 2019, fig. 8)"
NC_LEGACY = "SNOwGLoBES's NC table (unpublished)"
NC_STRENGTH = "measured B(M1) of the 1⁺ levels (Tornow 2025, ±14 %)"
NC_STRENGTH_ERROR = 0.18 / 1.31
RESPONSE = True  # False: a perfect detector (the threshold of the response only)
SECTION_OF = {"oscillation parameters": "B1", "solar model": "B2", "Earth model": "B3",
              "40Ar nuclear model": "B4", "cross-section model": "B4", "ES radiative corrections": "B4",
              NC_READING: "B4", NC_LEGACY: "B4", NC_STRENGTH: "B4"}
# NuFast-Earth's examples set one solar density for every component: rhoYe = 100 x 2/3 g/cm^3
SINGLE_DENSITY = 100 * 2 / 3
TREATMENTS = {"B8": "every component on the 8B production profile",
              "centre": "every component produced at the centre",
              "single": f"one density for every component, n_e = {SINGLE_DENSITY:.1f} N_A/cm³ (NuFast-Earth's examples)"}
EARTH_LABELS = {"prem_full": "PREM's average crust and ocean (prem_full)",
                "prem_four": "no crust, PREM's four main regions (prem_four)",
                "prem_prob3": "four shells of constant density (prem_prob3)"}
# the solver's approximation: NuFast-Earth takes each region crossing's mean density; the tables and the exact
# solvers cut the continuous regions into scan.SPLIT_KM shells, which removes it
SOLVER_APPROXIMATION = "mean density per region crossing (NuFast-Earth's own PREM treatment)"
ENERGIES = np.geomspace(0.1, 20.0, 120)
RADII = np.round(np.arange(0.0, 0.4001, 0.0025), 6)


class ProductionTreatment:
    """Day fractions from the exact B2 solver with every component produced
    as ``treatment`` says ("own": its own profile, or a key of TREATMENTS);
    the night from ``night`` (an engine provider)."""

    def __init__(self, treatment, night):
        self.treatment, self._night = treatment, night

    def day(self, osc, solar_model, component, energies):
        spec = _with_oscillation(load_spec("B2_sun"), osc)
        if self.treatment == "single":
            return fractions_at_density(spec, SINGLE_DENSITY, energies)
        if self.treatment == "centre":
            return fractions_at_density(spec, electron_density(solar_model, 0.0, spec), energies)
        radii = spec.axis("radius")
        w = production_weights(solar_model, radii, spec)[component if self.treatment == "own" else self.treatment]
        return np.einsum("r,rei->ei", w, adiabatic_fractions(spec, solar_model, energies, radii))

    def night(self, osc, earth_model, site):
        return self._night.night(osc, earth_model, site)


def _section(source):
    if "flux" in source:
        return "B2"
    if source.startswith("measured B(GT)"):
        return "B4"
    if source.startswith(("statistics", "energy scale", "energy resolution", "detector normalisation")):
        return "B5"
    return SECTION_OF.get(source)


def impacts(inputs, tables, params):
    """{observable: dict(label, quantity, central, rows)}; rows: dict(section, source, kind, sigma | low, high |
    shift), in the observable's units."""
    out = {}
    osc = engine.oscillation(params)
    models = list(inputs["solar_models"])
    for name, o in OBSERVABLES.items():
        response = engine.published_response(inputs, o["setup"]["detector"]) if o.get("response", True) else {}
        if not RESPONSE:
            response = dict(threshold=response.get("threshold", 0.0))
        setup = engine.Setup(solar_model=SOLAR_MODEL, exposure=EXPOSURE, **response, **o["setup"])
        q, night = o["quantity"], engine.needs_night(o["quantity"], setup.period)
        found, _ = engine.budget(inputs, tables, setup, params, q, N_DRAWS, SEED, solar_range="fluxes")
        central = found[0]["Central"]
        rows = []
        for r in found:
            section = _section(r["Source"])
            if section is None:
                continue
            row = dict(section=section, source=r["Source"], kind=r["Kind"])
            if r["Kind"] == "sampled":
                row["sigma"] = r["Sigma"]
            else:
                row.update(low=r["Low"], high=r["High"])
            if r["Source"] == "solar model":
                row["source"] = "solar model fluxes (production profiles fixed)"
            rows.append(row)

        def value(probabilities, s=setup, data=inputs):
            per = engine.component_totals(data, probabilities, s, osc, night)
            return engine.quantity_value(q, s.period, *engine.combine(per, list(s.components)),
                                         night_fraction=s.night_fraction)

        if setup.channel == "nc_ar40":
            # flavour-blind: no B2 profiles or production treatments; B4 is the figure reading of the default's
            # continuum (nc_reading_variants) and, for context, SNOwGLoBES's table
            nc_inputs, variants = _nc_inputs(inputs)
            reading = [value(tables, setup.replace(xsec_model=v), nc_inputs) for v in variants]
            rows.append(dict(section="B4", source=NC_READING, kind="model range", low=min(reading), high=max(reading)))
            # the measured strength of the discrete levels, 1.31(18) mu_N^2: their part of the rate scales with it
            levels = value(tables, setup.replace(xsec_model="tornow2025"), nc_inputs)
            rows.append(dict(section="B4", source=NC_STRENGTH, kind="sampled", sigma=levels * NC_STRENGTH_ERROR))
            rows.append(dict(section="B4", source=NC_LEGACY, kind="legacy",
                             shift=value(tables, setup.replace(xsec_model="snowglobes"), nc_inputs) - central))
            out[name] = dict(label=o["label"], quantity=q, central=central, rows=rows)
            continue

        # the solar model's density and production profiles, its fluxes fixed
        profiles = [value(tables, setup.replace(profile_model=m)) for m in models if engine.is_current(inputs, "solar_model", m)]
        rows.append(dict(section="B2", source="density and production profiles (solar models, fluxes fixed)",
                         kind="model range", low=min(profiles), high=max(profiles)))
        own = value(ProductionTreatment("own", tables))
        for treatment, label in TREATMENTS.items():
            rows.append(dict(section="B2", source=label, kind="approximation",
                             shift=value(ProductionTreatment(treatment, tables)) - own))
        # B3: the Earth models that approximate the state of the art, as shifts from it
        if night:
            for m in inputs["earth_models"]:
                kind = engine.status(inputs, "earth_model", m)["status"]
                if kind == "current":
                    continue
                rows.append(dict(section="B3", source=EARTH_LABELS.get(m, m), kind=kind,
                                 shift=value(tables, setup.replace(earth_model=m)) - central))
            if _has_driver():  # what the tables would carry with NuFast-Earth's own treatment
                from .export import ExactProbabilities

                rows.append(dict(section="B3", source=SOLVER_APPROXIMATION, kind="approximation",
                                 shift=value(ExactProbabilities(split_km=None)) - value(ExactProbabilities())))
        out[name] = dict(label=o["label"], quantity=q, central=central, rows=rows)
    return out


def sun_profiles(inputs):
    """B2, part 1: log10 n_e and normalised production per unit r/R_sun of every model on RADII."""
    out = {}
    for model in inputs["solar_models"]:
        data = table(model)
        r = data[:, 0]
        production = {}
        for k, c in enumerate(COMPONENTS):
            f = np.interp(RADII, r, data[:, 2 + k], left=data[0, 2 + k], right=0.0)
            production[c] = (f / np.trapezoid(f, RADII)).tolist()
        out[model] = dict(log_ne=np.log10(electron_density(model, RADII)).tolist(), production=production)
    return dict(radius=RADII.tolist(), models=out)


def survival_curves(inputs, osc):
    """B2, part 2: daytime P_ee(E) of every component for every solar model (own profiles), and for SOLAR_MODEL under
    each production treatment."""
    ue2 = np.abs(pmns(osc)[0]) ** 2
    pee = lambda provider, model, c: (provider.day(osc, model, c, ENERGIES) @ ue2).tolist()
    own = ProductionTreatment("own", None)
    by_model = {m: {c: pee(own, m, c) for c in COMPONENTS} for m in inputs["solar_models"]}
    treatments = {t: {c: pee(ProductionTreatment(t, None), SOLAR_MODEL, c) for c in COMPONENTS}
                  for t in ("own", *TREATMENTS)}
    return dict(energy=ENERGIES.tolist(), models=by_model, treatments=treatments,
                treatment_labels=dict(own="each component on its own profile", **TREATMENTS))


def regeneration(inputs, tables, osc):
    """B3: 8B night minus day P_ee(E), averaged over each site's night, for every Earth model."""
    ue2 = np.abs(pmns(osc)[0]) ** 2
    out, energy = {}, None
    for earth in inputs["earth_models"]:
        out[earth] = {}
        for site in inputs["sites"]:
            energy, P = tables.night(osc, earth, site)
            F = tables.day(osc, SOLAR_MODEL, "B8", energy)
            out[earth][site] = (np.sum(F * P, axis=1) - F @ ue2).tolist()
    return dict(energy=np.asarray(energy).tolist(), models=out)


def _has_driver():
    from .scan import _nufast_driver

    try:
        _nufast_driver()
    except FileNotFoundError:
        return False
    return True


def observed(solar_model="b16_gs98"):
    """B5 part 2 (build/data/B5_Observed, the B5 benchmark's inputs): per detector and channel, the observed spectrum
    of every component through the published response, in 0.25 MeV bins, the rates above the preset threshold with
    and without the response, and the interactions before it."""
    path = build_dir() / "B5_Observed.parquet"
    if not path.exists():
        return {}
    frame = pd.read_parquet(path)
    frame = frame[frame.SolarModel == solar_model]
    responses = load_spec("B5_rates")["response"]["detectors"]
    out = []
    for (detector, channel), group in frame.groupby(["Detector", "Channel"], sort=False):
        first = group.iloc[0]
        low = np.asarray(first.EnergyLow)
        edges = np.round(np.arange(0.0, 20.0001, 0.25), 6)
        index = np.clip(np.searchsorted(edges, low + 1e-9, side="right") - 1, 0, len(edges) - 2)
        spectra, totals = {}, {}
        for r in group.itertuples():
            if r.Interactions <= 0:
                continue  # a component that does not reach this detector (e.g. pp in CC): no spectrum, no row
            content = np.asarray(r.Rate) * (np.asarray(r.EnergyHigh) - low)
            # 4 significant digits: the plot needs no more, and sections.json stays small
            spectra[r.Component] = [float(f"{v:.4g}") for v in np.bincount(index, weights=content,
                                                                             minlength=len(edges) - 1) / 0.25]
            totals[r.Component] = dict(interactions=r.Interactions, true_above=r.TrueAboveThreshold,
                                       above=r.AboveThreshold)
        out.append(dict(detector=detector, channel=channel, preset=first.Preset, threshold=first.Threshold,
                        source=responses[detector]["source"], edges=edges.tolist(), spectra=spectra, totals=totals))
    return dict(solar_model=solar_model, cases=out)


def _contribution(tool, benchmark):
    paths = sorted((contributions_dir() / tool / benchmark).glob("*/data.parquet"))
    return pd.read_parquet(paths[-1]) if paths else None


def _tool_name(tool):
    path = repo_root() / "catalogue" / "tools" / f"{tool}.yaml"
    return yaml.safe_load(path.read_text()).get("name", tool) if path.exists() else tool


def tool_agreement():
    """Largest difference of each tool from the SNUfish reference on the cases both computed (B2, B3; B4's ES
    with radiative corrections, relative), and B5's
    full-chain rates over SNUfish's folding of the same inputs. ``comparison`` marks the spec's required variant
    (B2 b16_gs98, B3 prem_prob3), the one every tool solves on identical inputs."""
    out = {}
    for benchmark, axis in (("B2_sun", "radius"), ("B3_earth", "cos_nadir")):
        ref, spec = _contribution("snufish-reference", benchmark), load_spec(benchmark)
        required = {name for name, v in spec.variants.items() if v.get("required")}
        tools = sorted({p.parents[2].name for p in contributions_dir().glob(f"*/{benchmark}/*/data.parquet")} - {"snufish-reference"})
        rows = []
        for tool in tools:
            other = _contribution(tool, benchmark)
            if ref is None or other is None:
                continue
            keys = ["grid", "variant", "quantity", "energy", axis]
            both = ref.merge(other, on=keys, suffixes=("_ref", "_tool"))
            diff = (both.value_tool - both.value_ref).abs()
            for variant, d in diff.groupby(both.variant):
                rows.append(dict(tool=tool, name=_tool_name(tool), variant=variant, comparison=variant in required,
                                 points=int(d.size), max_abs=float(d.max())))
        out[benchmark] = rows
    # B4: the radiatively corrected nu-e cross sections, SNOwGLoBES's tables (Marciano & Parsa) against the
    # reference's BKS, relative, where both have a value (SNOwGLoBES's ES tables start at 0.5 MeV)
    ref, rows = _contribution("snufish-reference", "B4_xsec"), []
    for tool in ("snowglobes",):
        other = _contribution(tool, "B4_xsec")
        if ref is None or other is None:
            continue
        both = ref[ref.variant == "es_bks"].merge(other[other.variant == "default"], on=["grid", "quantity", "energy"],
                                                  suffixes=("_ref", "_tool")).dropna(subset=["value_ref", "value_tool"])
        both = both[(both.value_ref > 0) & (both.value_tool > 0)]
        for quantity, b in both.groupby("quantity"):
            rel = b.value_tool / b.value_ref - 1
            rows.append(dict(tool=tool, name=_tool_name(tool), variant="es_bks", quantity=quantity, points=int(len(b)),
                             energy_min=float(b.energy.min()), max_rel=float(rel.abs().max()), min_rel=float(rel.min()),
                             max_rel_signed=float(rel.max())))
    out["B4_xsec"] = rows
    chain = build_dir() / "B5_Chain.parquet"
    if chain.exists():
        frame = pd.read_parquet(chain)
        frame = frame[(frame.Rate > 0) & frame.Ratio.notna() & (frame.Component != "all")]
        out["B5_rates"] = [dict(tool=r.Tool, variant=r.Variant, solar_model=r.SolarModel, detector=r.Detector, channel=r.Channel,
                                component=r.Component, threshold=r.Threshold, rate=r.Rate, folded=r.Folded,
                                ratio=r.Ratio) for r in frame.itertuples()]
    return out


# NC on 40Ar (B4's NC card). The default model is the measured 1+ levels (Tornow et al. 2025) plus the HF+CRPA
# continuum of Van Dessel et al. 2019, read from their fig. 8. NC is flavour-blind, so its rate needs no oscillation;
# the rates are those of DUNE's solar Phase I settings (B16-GS98 8B + hep, E_nu > 5 MeV) and of this page's solar model.
NC_MODELS = ("default", "tornow2025", "vandessel2019", "snowglobes")
NC_SOLAR_MODELS = ("b16_gs98", SOLAR_MODEL)
NC_HALF_STEP = 1.9e-43  # cm^2: half a plotting step of the figure (reference/xsec/vandessel2019_nc_ar40.yaml)


def nc_reading_variants():
    """{name: sigma(E) of the continuum} for the figure-reading variants of the default NC model: every digitised
    point, or only the first nonzero one (12 MeV, which sets the 10-12 MeV onset), moved by half a plotting step, and
    the continuum started at 11 MeV instead of 10 (its last zero)."""
    table = export._yaml("reference/xsec/vandessel2019_nc_ar40.yaml")
    nodes, sigma, threshold = np.asarray(table["energy_MeV"]), np.asarray(table["total_1e-40cm2"]) * 1e-40, table["threshold_MeV"]
    first, positive = np.argmax(sigma > 0), sigma > 0
    only = np.arange(len(sigma)) == first
    shifted = {"all points −½ step": np.where(positive, np.clip(sigma - NC_HALF_STEP, 1e-50, None), sigma),
               "all points +½ step": np.where(positive, sigma + NC_HALF_STEP, sigma),
               "12 MeV point −½ step": np.where(only, np.clip(sigma - NC_HALF_STEP, 1e-50, None), sigma),
               "12 MeV point +½ step": np.where(only, sigma + NC_HALF_STEP, sigma)}
    out = {k: (lambda e, s=s: export._threshold_loglog(e, threshold, nodes, s)) for k, s in shifted.items()}
    out["onset at 11 MeV"] = lambda e: export._threshold_loglog(e, 11.0, nodes, sigma)
    return out


def _nc_grid():
    return np.unique(np.round(np.concatenate([np.arange(8.0, 30.0001, 0.05), np.arange(9.30, 12.0, 0.01),
                                              nc_ar40_reference.levels()[0]]), 6))


def _nc_inputs(inputs):
    """(inputs with the figure-reading variants of the default NC model as extra nc_ar40 models, their names).
    engine.Inputs reads the cross sections once, so the variants go into the data before it is built."""
    grid, variants = _nc_grid(), nc_reading_variants()
    discrete = nc_ar40_reference.discrete(grid)
    with_variants = {**inputs.data, "xsec": {**inputs.data["xsec"], "nc_ar40": {
        **inputs.data["xsec"]["nc_ar40"],
        **{k: {"energy": grid.tolist(), "sigma": (discrete + f(grid)).tolist()} for k, f in variants.items()}}}}
    return engine.Inputs(with_variants), list(variants)


def nc_ar40(inputs, tables, params):
    """Cross sections, figure-reading band and rates of NC on 40Ar for B4's NC card."""
    table = export._yaml("reference/xsec/vandessel2019_nc_ar40.yaml")
    variants = nc_reading_variants()
    grid = _nc_grid()
    discrete = nc_ar40_reference.discrete(grid)
    nc_inputs, _ = _nc_inputs(inputs)
    osc = engine.oscillation(params)

    def rate(model, solar_model="b16_gs98", threshold=5.0):
        setup = engine.Setup(solar_model=solar_model, components=("B8", "hep"), detector="argon", site="SURF",
                             channel="nc_ar40", xsec_model=model, period="day", nu_threshold=threshold)
        per = engine.combine(engine.component_totals(nc_inputs, tables, setup, osc), list(setup.components))
        return engine.quantity_value("rate", "day", *per)

    snowglobes = inputs.data["xsec"]["nc_ar40"]["snowglobes"]
    keep = [i for i, e in enumerate(snowglobes["energy"]) if 8.0 <= e <= 30.0]
    sigma = {"default": (discrete + export.vandessel2019_nc(grid)).tolist(), "tornow2025": discrete.tolist(),
             "vandessel2019": export.vandessel2019_nc(grid).tolist()}
    band = np.array([discrete + f(grid) for f in variants.values()])
    thresholds = np.round(np.arange(8.0, 16.0001, 0.25), 6)
    return dict(
        energy=grid.tolist(), sigma=sigma, band_low=band.min(axis=0).tolist(), band_high=band.max(axis=0).tolist(),
        snowglobes=dict(energy=[snowglobes["energy"][i] for i in keep], sigma=[snowglobes["sigma"][i] for i in keep]),
        points=dict(energy=[e for e in table["energy_MeV"] if e <= 30],
                    sigma=[s * 1e-40 for e, s in zip(table["energy_MeV"], table["total_1e-40cm2"]) if e <= 30]),
        half_step=NC_HALF_STEP, solar_models=list(NC_SOLAR_MODELS),
        rates={m: {sm: rate(m, sm) for sm in NC_SOLAR_MODELS} for m in [*NC_MODELS, *variants]},
        above=dict(threshold=thresholds.tolist(), **{m: [rate(m, threshold=t) for t in thresholds] for m in ("default", "snowglobes")}))


def _clean(x):
    """NaN and numpy scalars to JSON, floats to 6 significant digits."""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (float, np.floating)):
        return None if not np.isfinite(x) else float(f"{x:.6g}")
    if isinstance(x, np.integer):
        return int(x)
    return x


def export_sections(tables_dir):
    tables_dir = Path(tables_dir)
    inputs = engine.Inputs.load(tables_dir / "inputs.json")
    tables = engine.TableProbabilities(tables_dir)
    params = engine.parameters(inputs, SET)
    osc = engine.oscillation(params)
    data = dict(set=SET, solar_model=SOLAR_MODEL, draws=N_DRAWS, single_density=SINGLE_DENSITY,
                observables=impacts(inputs, tables, params), solar_profiles=sun_profiles(inputs),
                survival=survival_curves(inputs, osc), regeneration=regeneration(inputs, tables, osc),
                tools=tool_agreement(), observed=observed(), nc_ar40=nc_ar40(inputs, tables, params))
    path = tables_dir / "sections.json"
    with path.open("w") as handle:
        json.dump(_clean(data), handle, allow_nan=False, separators=(",", ":"))  # compact: the page downloads it
    return path
