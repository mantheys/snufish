"""Data frames as plotipus pickles (``snufish export-pkl``).

plotipus reads ``<data_root>/<path>/<datafile>.pkl``; this writes the solar
neutrino spectrum in the layout the DUNE papers' figures use (the left panel of
the LOWE reconstruction paper's fig. 1, ``Solar_Neutrino_Spectrum.pkl``), so the
same plotipus command draws it from SNUfish's solar models:

    plotipus line --path theory --datafile Solar_Neutrino_Spectrum -i Source -x Energy -y Flux --logx --logy --exact

``xsec_comparison`` (``snufish export-xsec``) writes the neutrino-argon cross sections of the paper's
fig. 2, ``xs_comparison.pkl`` (MARLEY, and SNUfish's reference tables for NC and nu_e-bar CC).

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
    pd.to_pickle(frame, out)
    return out


XSEC_CONFIGS = (  # Config, Flavor, Interaction: the rows of the paper's xs_comparison.pkl
    ("xs_nue_Ar40", r"$\nu_e$", "CC"),
    ("xs_nuebar_Ar40", r"$\bar{\nu}_e$", "CC"),
    ("xs_nue_e", r"$\nu_e$", "ES"),
    ("xs_nuebar_e", r"$\bar{\nu}_e$", "ES"),
    ("xs_numu_nutau_e", r"$\nu_{\mu ,\nu_\tau}$", "ES"),
    ("xs_nc_nue_Ar40", r"$\nu_x$", "NC"),
)


def xsec_comparison(marley, cc_model="ar40_marley1_allowed", energies=None):
    """Neutrino-argon cross sections (1e-38 cm^2) in the layout of the paper's ``xs_comparison.pkl``.

    The settings of DUNE's official MARLEY production (``roiana_marley_dune.fcl``: MARLEY v1.2.1, reactions
    ``ve40ArCC_Bhattacharya2009.react`` and ``ES.react``): nu_e CC on 40Ar is ``marley xsec`` of the checkout
    ``marley`` with the B4 variant ``cc_model`` (``contributions/marley/scripts/run_b4.py``; default
    ``ar40_marley1_allowed``, MARLEY v1.2.1's cross section), at any energy. ES (nu_e, nu_e-bar, nu_mu, nu_tau;
    the last two averaged) is ``ES.react``: tree level, per electron. NC on 40Ar is the SNOwGLoBES table SNUfish
    stores (``reference/xsec/snowglobes_nc_ar40.yaml``). nu_e-bar CC on 40Ar, which MARLEY does not have, is the
    HF+CRPA calculation of Van Dessel, Jachowicz & Nikolakopoulos, PRC 100, 055503 (2019), fig. 9
    (``reference/xsec/vandessel2019_nuebar_ar40.yaml``, ``snufish.export.vandessel2019_nuebar``): zero up to
    16 MeV, where the published curve leaves zero. No SNOwGLoBES checkout is needed.
    """
    import importlib.util
    import tempfile

    import yaml

    from .export import vandessel2019_nuebar
    from .paths import contributions_dir, repo_root
    energies = np.geomspace(0.5, 100.0, 1001) if energies is None else np.asarray(energies, dtype=float)
    spec = importlib.util.spec_from_file_location("snufish_marley_run_b4", contributions_dir() / "marley" / "scripts" / "run_b4.py")
    run_b4 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_b4)
    if cc_model not in run_b4.CONFIGS:
        raise ValueError(f"cc_model is one of {sorted(run_b4.CONFIGS)}")
    marley = Path(marley).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        grid = np.round(np.arange(0.02, energies.max() + 0.02, 0.02), 2)   # B4's step, up to the top of the range
        sigma = run_b4.xsec(run_b4.executable(marley), marley, run_b4.CONFIGS[cc_model], Path(tmp), grid,
                            run_b4.OPTIONS.get(cc_model)) * 1e38
        # the official production's ES (DUNE's MARLEY v1.2.1 fcl: "ES.react"): tree level, per electron (Z = 18)
        es = {f: np.interp(energies, grid, run_b4.xsec(run_b4.executable(marley), marley, ["ES.react"], Path(tmp), grid,
                                                       neutrino=name, pdg=pdg)) * 1e38 / 18
              for f, name, pdg in (("nue", "ve", 12), ("nuebar", "vebar", -12), ("numu", "vu", 14), ("nutau", "vt", 16))}
    with (repo_root() / "reference" / "xsec" / "snowglobes_nc_ar40.yaml").open() as handle:
        nc = yaml.safe_load(handle)
    curves = {
        "xs_nue_Ar40": np.interp(energies, grid, sigma, left=0.0),
        "xs_nuebar_Ar40": vandessel2019_nuebar(energies) * 1e38,
        "xs_nue_e": es["nue"],
        "xs_nuebar_e": es["nuebar"],
        "xs_numu_nutau_e": 0.5 * (es["numu"] + es["nutau"]),
        "xs_nc_nue_Ar40": np.interp(energies, nc["energy_MeV"], np.asarray(nc["sigma_cm2"]) * 1e38),
    }
    return [dict(Config=c, Flavor=f, Energy=energies.copy(), XS=curves[c], Interaction=i) for c, f, i in XSEC_CONFIGS]
