"""What each benchmark contributes to the uncertainty of a result (``snufish
export-sections``): ``sections.json`` for the web page's benchmark pages.

    snufish export-app --out build/app          # the tables first
    snufish export-sections --tables build/app  # writes build/app/sections.json

For a few reference observables (``OBSERVABLES``), the engine's error budget
on the app tables, each source assigned to the benchmark it comes from
(``SECTION_OF``): B1 the solar fluxes, B2 the solar density and production
profiles, B3 the Earth model, B4 the cross sections; the oscillation
parameters are an input of B2 and B3 and are kept apart. B2 adds the
approximations some solvers make about where neutrinos are produced
(``TREATMENTS``): signed shifts of the observable, computed with the exact
B2 solver (the tables hold each component's own profile only). With them,
per benchmark, the curves its pages plot (solar profiles, P_ee per
component, regeneration per Earth model) and the agreement between tools.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import engine
from .export import MARLEY_DEFAULT
from .paths import build_dir, contributions_dir
from .reference.sun import adiabatic_fractions, fractions_at_density
from .scan import _with_oscillation
from .solar import COMPONENTS, electron_density, production_weights, table
from .spec import load_spec, pmns

SET, SOLAR_MODEL = "juno_2025", "b23_mb22m"  # state of the art (reference/status.yaml)
N_DRAWS, SEED = 300, 1
OBSERVABLES = {
    "water_es_b8": dict(label="8B + hep ES in water, T > 3.49 MeV, Kamioka", quantity="rate",
                        setup=dict(detector="water", channel="es", components=("B8", "hep"), threshold=3.49,
                                   site="Kamioka", period="annual")),
    "argon_cc_b8": dict(label="8B CC on 40Ar, visible energy > 5 MeV, SURF", quantity="rate",
                        setup=dict(detector="argon", channel="cc_nue_ar40", components=("B8",), threshold=5.0,
                                   site="SURF", xsec_model=MARLEY_DEFAULT, period="annual")),
    "argon_cc_hep": dict(label="hep CC on 40Ar, SURF", quantity="rate",
                         setup=dict(detector="argon", channel="cc_nue_ar40", components=("hep",), site="SURF",
                                    xsec_model=MARLEY_DEFAULT, period="annual")),
    "scint_es_be7": dict(label="7Be ES in scintillator, all recoils, LNGS", quantity="rate",
                         setup=dict(detector="scintillator_pc", channel="es", components=("Be7",), site="LNGS",
                                    period="annual")),
    "water_es_adn": dict(label="8B + hep ES day-night asymmetry, T > 3.49 MeV, Kamioka", quantity="adn",
                         setup=dict(detector="water", channel="es", components=("B8", "hep"), threshold=3.49,
                                    site="Kamioka")),
}
SECTION_OF = {"oscillation parameters": "oscillation", "solar model": "B1", "Earth model": "B3",
              "40Ar nuclear model": "B4", "cross-section model": "B4", "ES radiative corrections": "B4"}
# NuFast-Earth's examples set one solar density for every component: rhoYe = 100 x 2/3 g/cm^3
SINGLE_DENSITY = 100 * 2 / 3
TREATMENTS = {"B8": "every component on the 8B production profile",
              "centre": "every component produced at the centre",
              "single": f"one density for every component, n_e = {SINGLE_DENSITY:.1f} N_A/cm³ (NuFast-Earth's examples)"}
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
        return "B1"
    if source.startswith("measured B(GT)"):
        return "B4"
    return SECTION_OF.get(source)


def impacts(inputs, tables, params):
    """{observable: dict(label, quantity, central, rows)}; rows: dict(section, source, kind, sigma | low, high |
    shift), in the observable's units."""
    out = {}
    osc = engine.oscillation(params)
    models = list(inputs["solar_models"])
    for name, o in OBSERVABLES.items():
        setup = engine.Setup(solar_model=SOLAR_MODEL, **o["setup"])
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

        def value(probabilities, s=setup):
            per = engine.component_totals(inputs, probabilities, s, osc, night)
            return engine.quantity_value(q, s.period, *engine.combine(per, list(s.components)),
                                         night_fraction=s.night_fraction)

        # the solar model's density and production profiles, its fluxes fixed
        profiles = [value(tables, setup.replace(profile_model=m)) for m in models if engine.is_current(inputs, "solar_model", m)]
        rows.append(dict(section="B2", source="density and production profiles (solar models, fluxes fixed)",
                         kind="model range", low=min(profiles), high=max(profiles)))
        own = value(ProductionTreatment("own", tables))
        for treatment, label in TREATMENTS.items():
            rows.append(dict(section="B2", source=label, kind="approximation",
                             shift=value(ProductionTreatment(treatment, tables)) - own))
        out[name] = dict(label=o["label"], quantity=q, central=central, rows=rows)
    return out


def sun_profiles(inputs):
    """B1: log10 n_e and normalised production per unit r/R_sun of every model on RADII."""
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
    """B2: daytime P_ee(E) of every component for every solar model (own profiles), and for SOLAR_MODEL under
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


def _contribution(tool, benchmark):
    paths = sorted((contributions_dir() / tool / benchmark).glob("*/data.parquet"))
    return pd.read_parquet(paths[-1]) if paths else None


def tool_agreement():
    """Largest difference of each tool from the SNUfish reference on the cases both computed (B2, B3), and B5's
    full-chain rates over SNUfish's folding of the same inputs."""
    out = {}
    for benchmark, axis in (("B2_sun", "radius"), ("B3_earth", "cos_nadir")):
        ref = _contribution("snufish-reference", benchmark)
        rows = []
        for tool in ("nufast-earth",):
            other = _contribution(tool, benchmark)
            if ref is None or other is None:
                continue
            keys = ["grid", "variant", "quantity", "energy", axis]
            both = ref.merge(other, on=keys, suffixes=("_ref", "_tool"))
            diff = (both.value_tool - both.value_ref).abs()
            for variant, d in diff.groupby(both.variant):
                rows.append(dict(tool=tool, variant=variant, points=int(d.size), max_abs=float(d.max())))
        out[benchmark] = rows
    chain = build_dir() / "B5_Chain.parquet"
    if chain.exists():
        frame = pd.read_parquet(chain)
        frame = frame[(frame.Rate > 0) & frame.Ratio.notna() & (frame.Component != "all")]
        out["B5_rates"] = [dict(tool=r.Tool, variant=r.Variant, solar_model=r.SolarModel, detector=r.Detector, channel=r.Channel,
                                component=r.Component, threshold=r.Threshold, rate=r.Rate, folded=r.Folded,
                                ratio=r.Ratio) for r in frame.itertuples()]
    return out


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
                observables=impacts(inputs, tables, params), b1=sun_profiles(inputs),
                b2=survival_curves(inputs, osc), b3=regeneration(inputs, tables, osc), tools=tool_agreement())
    path = tables_dir / "sections.json"
    with path.open("w") as handle:
        json.dump(_clean(data), handle, allow_nan=False)
    return path
