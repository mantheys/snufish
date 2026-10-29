"""Error budgets of the 8B rates and the day-night asymmetry (``snufish
budget``), computed by :mod:`snufish.engine` with the exact B2/B3 solvers
(or, with ``probabilities``, any engine provider such as the app tables).

Two kinds of input uncertainty are kept apart:

- sampled (Monte Carlo): solar fluxes (each B1 model's published fractional
  errors, with its correlation matrix where published, i.e. B23; or the
  measured SNO NC 8B flux) and the oscillation parameters of a parameter
  set (split-normal for asymmetric errors, independent, as the sources
  publish no correlation). Reported as a standard deviation.
- model choices: the nu_e-40Ar nuclear model (B4 variants), ES radiative
  corrections (tree level vs SNOwGLoBES's tables), the Earth model (B3
  variants) and the solar model (B1). Reported as the range of the
  alternatives around the nominal, never folded into a sigma: the range
  depends on which models exist, not on a probability.

Quantities are daytime 8B rates per kton-year (true neutrino energy, recoil
threshold for ES, no detector response) and the ES day-night asymmetry.
"""

import functools

import numpy as np
import pandas as pd

from . import engine
from .build import _write_frame
from .export import B8_MEASURED, ExactProbabilities, collect_inputs  # noqa: F401 (B8_MEASURED re-exported)
from .paths import build_dir
from .solar import COMPONENTS

QUANTITIES = {
    # name: engine setup and quantity (rate by day, or the day-night asymmetry)
    "argon_cc_b8": dict(setup=dict(detector="argon", channel="cc_nue_ar40"), quantity="rate",
                        label="8B CC on 40Ar"),
    "argon_es_b8_t5": dict(setup=dict(detector="argon", channel="es", threshold=5.0), quantity="rate",
                           label="8B ES in argon, T > 5 MeV"),
    "water_es_b8_t349": dict(setup=dict(detector="water", channel="es", threshold=3.49), quantity="rate",
                             label="8B ES in water, T > 3.49 MeV"),
    "kamioka_adn_es": dict(setup=dict(detector="water", channel="es", threshold=3.49, site="Kamioka"),
                           quantity="adn", label="ES day-night asymmetry at Kamioka"),
}
NOMINAL = dict(xsec_model="default", es_model="bks", earth_model="prem_full")

_split_normal = engine.split_normal


@functools.lru_cache(maxsize=1)
def inputs():
    return engine.Inputs(collect_inputs())


def sample_flux_scales(rng, solar_model, n):
    """Array [n, 8] of multipliers of every component, with the model's correlation."""
    return engine.sample_fluxes(inputs(), rng, solar_model, list(COMPONENTS), n)


def budget(set_name="juno_2025", solar_model="b23_gs98", n=300, seed=1, quantities=None, b8_constraint=False,
           probabilities=None):
    """Error budget frames: one row per quantity and source, and the samples.
    ``probabilities``: an engine provider (default: the exact solvers)."""
    probabilities = probabilities or ExactProbabilities()
    params = engine.parameters(inputs(), set_name)
    rows, samples = [], []
    for quantity in quantities or list(QUANTITIES):
        q = QUANTITIES[quantity]
        setup = engine.Setup(solar_model=solar_model, b8_flux="sno_nc" if b8_constraint else "model",
                             **dict(NOMINAL, **q["setup"]))
        found, drawn = engine.budget(inputs(), probabilities, setup, params, q["quantity"], n, seed)
        base = dict(Quantity=quantity, Label=q["label"], Set=set_name, SolarModel=solar_model,
                    Flux="SNO NC" if b8_constraint else "solar model")
        rows += [dict(base, **row) for row in found]
        samples += [dict(base, Source=source, Central=found[0]["Central"], Values=values)
                    for source, values in drawn.items()]
    return {"Budget": pd.DataFrame(rows), "Budget_Samples": pd.DataFrame(samples)}


def write_budget(sets, solar_model="b23_gs98", n=300, seed=1, b8_constraint=(False, True), probabilities=None):
    """Budgets for several parameter sets and both 8B flux treatments, in one frame each."""
    out = build_dir()
    out.mkdir(parents=True, exist_ok=True)
    parts = {"Budget": [], "Budget_Samples": []}
    for set_name in sets:
        for constrained in b8_constraint:
            quantities = None if not constrained else [q for q in QUANTITIES if "site" not in QUANTITIES[q]]
            frames = budget(set_name, solar_model, n, seed, quantities, constrained, probabilities)
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
        for source in g.index[g.Kind == "model range"]:
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
