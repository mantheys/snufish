"""Day-night asymmetry of the solar CC and ES channels in argon for the DUNE solar Phase I paper, and the ratio
A_ES / A_CC, computed from the full spectra rather than from a single survival probability.

    python scripts/dune_phase1_daynight.py [--out build/dune_phase1] [--bin 1.0]

Same settings as scripts/dune_phase1_rates.py (B16-GS98 8B + hep, dm2_21 = 6e-5 eV^2, sin2_12 = 0.304,
SOLAR's night at SURF, PREM, MARLEY v1 allowed CC with its 40K level shares for the electron energy, BKS ES),
no detector response. A_DN = 2 (N - D) / (N + D) of the rates, at 1 AU.

Two numbers are compared for each threshold in electron kinetic energy T_e:

* spectrum-weighted (the result): A_X = 2 (N_X - D_X) / (N_X + D_X), with D_X and N_X the day and night rates of
  channel X integrated over T_e > threshold. Every neutrino energy enters with its own regeneration, cross section
  and electron-energy response, so this is the A_X of a counting measurement above that threshold.
* one-number estimate: A_ES / A_CC = (1 - r) P / (P + r (1 - P)), the ratio for a regeneration that is the same at
  all energies. P is the CC-weighted day survival probability (D_CC over the CC rate without oscillation) and r the
  ratio of the nu_x to the nu_e ES rate above the threshold. It ignores that regeneration grows with E_nu and that
  CC samples higher E_nu than ES does at the same T_e.

Writes <out>/snufish_daynight.json (integrated rates and asymmetries per threshold, and the day and night spectra
in T_e bins of --bin MeV) and prints the summary.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from snufish import engine  # noqa: E402
from snufish.export import ExactProbabilities, collect_inputs  # noqa: E402
from dune_phase1_rates import CC_MODEL, SETTINGS, SOLAR, commit, levels_model  # noqa: E402

THRESHOLDS = (5.0, 8.0, 10.0)  # MeV of T_e
T_MAX = 25.0


def setups(inputs):
    """{channel: Setup} for CC (electron energy from the 40K level shares) and ES, no threshold."""
    base = engine.Setup(**SETTINGS, period="annual")
    electron = engine.electron_smearing(inputs, "cc_nue_ar40", levels_model(inputs, CC_MODEL), 0.0)
    return {"CC": base.replace(channel="cc_nue_ar40", xsec_model=CC_MODEL, smearing_table=electron),
            "ES": base.replace(channel="es")}


def fine_spectra(inputs, probabilities, setup, osc, edges):
    """(day, night) rates per kt-yr in the fine T_e bins ``edges``, summed over the components."""
    per = engine.observed_rates(inputs, probabilities, setup, osc, night=True, edges=edges)
    day = sum(per[c]["day"] for c in setup.components)
    night = sum(per[c]["night"] for c in setup.components)
    return np.asarray(day), np.asarray(night)


def adn(day, night):
    return float(2 * (night - day) / (night + day))


def es_flavour_rates(inputs, setup, threshold):
    """(nu_e, nu_x) ES rates per kt-yr above ``threshold`` if every neutrino were that flavour: the two kernels of
    the ES rate (engine.observed_rates: true = (q P) @ K_e + (q (1 - P)) @ K_x), integrated above the threshold."""
    s = setup.replace(threshold=threshold)
    nue = nux = 0.0
    for c in s.components:
        prep = engine._prepared(inputs, s, c)  # cached kernels times the response, as in engine._fast
        scale = inputs["seconds_per_year"] * engine._targets(inputs, s) * inputs.flux(s.solar_model, c, s.b8_flux)
        nux += scale * prep["base_total"]
        nue += scale * (float(prep["q"] @ prep["diff_total"]) + prep["base_total"])
    return nue, nux


def compute(bin_width=1.0):
    inputs = engine.Inputs(collect_inputs())
    probabilities = ExactProbabilities(night_mode="solar")
    osc = engine.oscillation(engine.parameters(inputs, "nufit60_global", SOLAR))
    channel_setups = setups(inputs)

    fine = engine.observed_edges(0.0)[0]
    for t in THRESHOLDS:  # each threshold a fine edge, so the cuts are exact
        if not np.any(np.isclose(fine, t, rtol=0, atol=1e-9)):
            fine = np.sort(np.append(fine, t))
    centres = 0.5 * (fine[1:] + fine[:-1])
    coarse = np.arange(0.0, T_MAX + bin_width / 2, bin_width)

    spectra, integrated = {}, {}
    for ch, setup in channel_setups.items():
        engine.check(inputs, setup)
        day, night = fine_spectra(inputs, probabilities, setup, osc, fine)
        d, n = engine.rebin(day, fine, coarse), engine.rebin(night, fine, coarse)
        with np.errstate(invalid="ignore", divide="ignore"):
            a = np.where(d + n > 0, 2 * (n - d) / (n + d), np.nan)
        spectra[ch] = {"day": d.tolist(), "night": n.tolist(), "adn": [None if np.isnan(x) else float(x) for x in a]}
        for t in THRESHOLDS:
            keep = centres > t
            D, N = float(day[keep].sum()), float(night[keep].sum())
            integrated.setdefault(t, {})[ch] = {"day": D, "night": N, "adn": adn(D, N)}

    for t in THRESHOLDS:
        row = integrated[t]
        cc = channel_setups["CC"].replace(threshold=t)
        per = engine.combine(engine.component_totals(inputs, probabilities, cc, osc), list(cc.components))
        p_day = per[0] / per[2]  # CC-weighted day survival probability
        nue, nux = es_flavour_rates(inputs, channel_setups["ES"], t)
        r = nux / nue
        row["ratio"] = row["ES"]["adn"] / row["CC"]["adn"]
        row["estimate"] = {"P_ee_day_cc_weighted": p_day, "r_es": r,
                           "ratio": (1 - r) * p_day / (p_day + r * (1 - p_day))}
    return {"thresholds": integrated, "spectra": {"edges_MeV": coarse.tolist(), **spectra}}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "dune_phase1")
    parser.add_argument("--bin", type=float, default=1.0, help="T_e bin width of the spectra in the JSON (MeV)")
    args = parser.parse_args()

    result = compute(args.bin)
    args.out.mkdir(parents=True, exist_ok=True)
    record = {"snufish": commit(), "units": "interactions per kt-yr; A_DN = 2 (N - D) / (N + D), rates at 1 AU",
              "settings": {**SETTINGS, "components": list(SETTINGS["components"]), "oscillation": SOLAR,
                           "cc_model": CC_MODEL, "es_model": "bks", "axis": "electron kinetic energy T_e"},
              "thresholds": [{"T_e_min_MeV": t, **v} for t, v in result["thresholds"].items()],
              "spectra": result["spectra"]}
    (args.out / "snufish_daynight.json").write_text(json.dumps(record, indent=1) + "\n")

    print(f"{'T_e >':>6s} {'A_CC %':>8s} {'A_ES %':>8s} {'A_ES/A_CC':>10s}   one-number estimate (P, r -> ratio)")
    for t, v in result["thresholds"].items():
        e = v["estimate"]
        print(f"{t:6.1f} {100 * v['CC']['adn']:8.2f} {100 * v['ES']['adn']:8.2f} {v['ratio']:10.3f}   "
              f"P = {e['P_ee_day_cc_weighted']:.3f}, r = {e['r_es']:.3f} -> {e['ratio']:.3f}")
    edges, cc, es = result["spectra"]["edges_MeV"], result["spectra"]["CC"]["adn"], result["spectra"]["ES"]["adn"]
    print(f"\nA_DN per {args.bin:g} MeV of T_e (%):")
    print(f"{'T_e':>9s} {'CC':>7s} {'ES':>7s}")
    for k in range(len(edges) - 1):
        if edges[k] >= 3 and cc[k] is not None and es[k] is not None and edges[k + 1] <= 18:
            print(f"{edges[k]:4.0f}-{edges[k + 1]:<4.0f} {100 * cc[k]:7.2f} {100 * es[k]:7.2f}")
    print(f"Wrote {args.out}/snufish_daynight.json")


if __name__ == "__main__":
    main()
