"""Data frames as plotipus pickles (``snufish export-pkl``).

plotipus reads ``<data_root>/<path>/<datafile>.pkl``; this writes the solar
neutrino spectrum in the layout the DUNE papers' figures use (the left panel of
the LOWE reconstruction paper's fig. 1, ``Solar_Neutrino_Spectrum.pkl``), so the
same plotipus command draws it from SNUfish's solar models:

    plotipus line --path theory --datafile Solar_Neutrino_Spectrum -i Source -x Energy -y Flux --logx --logy --exact

One row per flux component, columns ``Flux`` and ``Energy`` (arrays), ``Source``
(``pp pep b7 b8 n13 o15 f17 hep``) and ``Plot`` (the solar model's label).
A continuum is its flux density in cm^-2 s^-1 MeV^-1 at the energies of its
spectral shape; a line is the pair of points ``Energy = [E, E]``, ``Flux = [0, F]``
(F in cm^-2 s^-1), a vertical line in a log-log plot; ``7Be`` has one row per line.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from . import engine
from .plotipus_plugin import SOLAR_MODEL_LABELS
from .solar import COMPONENTS

# Source ids of the DUNE papers' pickles (config/plot_params.json: solar_dict)
SOURCE_IDS = {"Be7": "b7"}
PERIODS = ("none", "day", "night", "annual")


def _label(solar_model, period, parameter_set):
    label = SOLAR_MODEL_LABELS.get(solar_model, solar_model)
    return label if period == "none" else f"{label}, {period} $\\nu_e$ ({parameter_set})"


def solar_spectrum(solar_model="b16_gs98", period="none", parameter_set="solar_global_2024", site="Kamioka",
                   earth_model="prem_crust1", night_fraction=0.5, probabilities=None):
    """Flux at Earth of every solar component as a plotipus frame (module docstring).

    ``period="none"``: the solar model's flux, the flavours summed (no oscillation, the
    figure's "flux reaching the Earth"). ``"day"``, ``"night"``, ``"annual"``: the nu_e
    flux in the detector, i.e. times P_ee(E) of the parameter set (``snufish.engine``,
    the exact solvers unless ``probabilities`` is given); the night and the annual
    mean ((1 - f) day + f night, f = ``night_fraction``) go through the Earth at ``site``.
    """
    from .uncertainty import inputs

    if period not in PERIODS:
        raise ValueError(f"period is one of {PERIODS}")
    data = inputs()
    pee = {}
    if period != "none":
        from .export import ExactProbabilities

        setup = engine.Setup(solar_model=solar_model, components=COMPONENTS, earth_model=earth_model, site=site)
        osc = engine.oscillation(engine.parameters(data, parameter_set))
        night = period != "day"
        for c, (day_p, night_p) in engine.survival(data, probabilities or ExactProbabilities(), setup, osc,
                                                   night=night).items():
            pee[c] = {"day": day_p, "night": night_p,
                      "annual": None if night_p is None else (1 - night_fraction) * day_p + night_fraction * night_p}[period]
    label = _label(solar_model, period, parameter_set)
    rows = []
    for c in COMPONENTS:
        kind, energy, weight = data.components[c]
        total = data.flux(solar_model, c)
        source = SOURCE_IDS.get(c, c.lower())
        factor = pee.get(c, 1.0)
        if kind == "line":
            for e, branching, f in sorted(zip(energy, weight, np.broadcast_to(factor, energy.shape))):
                rows.append(dict(Flux=np.array([0.0, total * branching * f]), Energy=np.array([e, e]), Source=source,
                                 Plot=label))
        else:
            rows.append(dict(Flux=total * weight * factor, Energy=energy.copy(), Source=source, Plot=label))
    return pd.DataFrame(rows, columns=["Flux", "Energy", "Source", "Plot"])


def write_pkl(frame, directory, datafile, path="theory"):
    """``<directory>/<path>/<datafile>.pkl``: where ``--path`` and ``--datafile`` of plotipus look."""
    out = Path(directory) / path / f"{datafile}.pkl"
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_pickle(out)
    return out
