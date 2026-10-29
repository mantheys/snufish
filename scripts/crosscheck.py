"""Published numbers recomputed with the SNUfish engine, each with the inputs its paper states.

    python scripts/crosscheck.py [--exact]      # needs snufish export-app (build/app)

--exact uses the B2 solver and NuFast-Earth instead of the app's interpolated tables.
Prints one row per number: what, published, SNUfish, difference, and what the setup
cannot reproduce. Day-night asymmetries are given in each paper's convention.
"""

import argparse
import sys
from pathlib import Path

import numpy as np

from snufish import engine
from snufish.paths import repo_root

APP = repo_root() / "build" / "app"
DAYS = 365.25
SK4_RES = (-0.05525, 0.3162, 0.04572)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--exact", action="store_true")
    args = parser.parse_args()
    inputs = engine.Inputs.load(APP / "inputs.json")
    if args.exact:
        from snufish.export import ExactProbabilities
        probs = ExactProbabilities()
    else:
        probs = engine.TableProbabilities(APP)
    curve = inputs["efficiency_curves"]["sk4_final"]
    sk_eff = engine.Table("sk4", tuple(curve["x"]), tuple(curve["y"]))
    rows = []

    def osc(**values):
        return engine.oscillation(engine.parameters(inputs, "nufit60_global", custom=values))

    def totals(setup, o, night=True):
        return engine.combine(engine.component_totals(inputs, probs, setup, o, night), list(setup.components))

    def adn(day, night):
        return 2 * (night - day) / (night + day)

    def row(source, what, published, ours, unit="", note="", fmt="{:.4g}"):
        rel = (ours - published) / abs(published) if published else np.nan
        rows.append((source, what, fmt.format(published) + unit, fmt.format(ours) + unit, rel, note))

    # ---- Bahcall, Kamionkowski & Sirlin 1995, table VIII: spectrum-averaged sigma_e (1e-46 cm^2), all T
    o = osc()
    for c, published in (("pp", 11.6), ("Be7", 57.9), ("B8", 594), ("N13", 45.8), ("O15", 70.8)):
        s = engine.Setup(components=(c,), threshold=0.0)
        per = engine.component_totals(inputs, probs, s, o, False)[c]
        sigma = per["ref"] / (engine._targets(inputs, s) * inputs.flux(s.solar_model, c) * inputs["seconds_per_year"])
        if c == "Be7":  # BKS's 57.9 is the 862 keV line alone
            _, energy, weight = inputs.components[c]
            from snufish.reference.radiative import es_above
            sigma = es_above([energy.max()], "nue", inputs["constants"], [0.0])[0, 0]
        row("BKS 1995 tab. VIII", f"<σ_e> {engine.DISPLAY[c]}" + (" 862 keV" if c == "Be7" else ""), published,
            sigma / 1e-46, " e-46 cm²", "BKS spectra (Bahcall 1989-96); ours B16/SNUfish shapes" if c != "Be7" else "")

    # ---- Borexino Phase-II (arXiv:1707.09279): B16-GS98 predictions, cpd/100 t, all recoil energies
    o = osc()
    k = 0.1 * 86400 / inputs["seconds_per_year"]
    for c, published in (("pp", 131.1), ("Be7", 47.9), ("pep", 2.74)):
        s = engine.Setup(solar_model="b16_gs98", components=(c,), detector="scintillator_pc", site="LNGS", period="annual")
        d, n, _ = totals(s, o)
        row("Borexino 1707.09279", f"{engine.DISPLAY[c]} rate, B16-GS98", published, 0.5 * (d + n) * k, " cpd/100t",
            "NuFIT 6.0 here; Borexino's oscillation inputs as in their paper")
    # oscillated / unoscillated, as quoted by Super-K (arXiv:2312.12907 sec. VII D) for Borexino's parameters
    o = osc(sin2_theta12=0.306, sin2_theta13=0.02166, dm2_21_eV2=7.50e-5)
    for c, published, t in (("pp", 0.689, 0.165), ("pep", 0.614, 1.0), ("Be7", 0.638, 0.25)):
        s = engine.Setup(solar_model="b16_gs98", components=(c,), detector="scintillator_pc", site="LNGS",
                         period="annual", threshold=t)
        d, n, ref = totals(s, o)
        row("SK 2312.12907 §VII D", f"Borexino {engine.DISPLAY[c]} osc/no-osc", published, 0.5 * (d + n) / ref, "",
            f"window unknown: T > {t} MeV here", "{:.3f}")

    # ---- Borexino 8B (arXiv:1709.00756): rate above 3.2 MeV (50 % efficiency there), B16-HZ flux 5.46e6
    o = osc(sin2_theta12=0.306, sin2_theta13=0.02166, dm2_21_eV2=7.50e-5)
    s = engine.Setup(solar_model="b16_gs98", components=("B8",), detector="scintillator_pc", site="LNGS", period="annual",
                     threshold=2.6, efficiency_e50=3.2, efficiency_width=0.12, resolution_a=0.045)
    d, n, ref = totals(s, o)
    row("Borexino 1709.00756", "8B ES equiv. flux (no-osc), 1e6", 2.57, 0.5 * (d + n) / ref * 5.25, "",
        "measured ±0.19; ours with the SNO NC flux, logistic turn-on at 3.2 MeV", "{:.3f}")
    row("Borexino 1709.00756", "8B rate > 3.2 MeV, B16-GS98", 0.223, 0.5 * (d + n) * k, " cpd/100t",
        "measured ±0.016 (stat); prediction with B16-GS98 5.46e6", "{:.3f}")

    # ---- JUNO 8B (arXiv:2006.11760): table 1, cpd/kt in day and in night time, SNO NC flux, PDG 2018 mixing
    for dm2, (d0, n0, d2, n2) in ((4.8e-5, (2.05, 2.10, 1.36, 1.40)), (7.5e-5, (2.17, 2.19, 1.44, 1.46))):
        o = osc(sin2_theta12=0.307, sin2_theta13=0.0212, dm2_21_eV2=dm2)
        for t, (pd, pn) in ((0.0, (d0, n0)), (2.0, (d2, n2))):
            for es in ("tree", "bks"):
                s = engine.Setup(components=("B8", "hep"), b8_flux="sno_nc", detector="scintillator_lab", site="Jiangmen",
                                 threshold=t, resolution_a=0.03, es_model=es)
                d, n, _ = totals(s, o)
                note = "JUNO: tree level, g1 ≈ 0.73" if es == "tree" else "with radiative corrections"
                row("JUNO 2006.11760 tab. 1", f"Δm²={dm2 * 1e5:.1f}, E>{t:g}, day+night, {es}", pd + pn, (d + n) / 2 / DAYS,
                    " cpd/kt", note, "{:.3f}")
    # A_DN = (D - N) / ((D + N)/2), table 7 (Δm² 4.8e-5) and text (7.5e-5, 2-16 MeV)
    for dm2, lo, hi, published in ((4.8e-5, 2, 16, -0.029), (4.8e-5, 5, 16, -0.034), (4.8e-5, 3, 5, -0.025),
                                   (4.8e-5, 2, 3, -0.021), (7.5e-5, 2, 16, -0.016)):
        o = osc(sin2_theta12=0.307, sin2_theta13=0.0212, dm2_21_eV2=dm2)
        s = engine.Setup(components=("B8", "hep"), b8_flux="sno_nc", detector="scintillator_lab", site="Jiangmen",
                         threshold=lo, resolution_a=0.03, efficiency_table=engine.Table(f"win{lo}{hi}", (lo, hi - 1e-3, hi),
                                                                                        (1.0, 1.0, 0.0)))
        d, n, _ = totals(s, o)
        row("JUNO 2006.11760 tab. 7", f"A_DN Δm²={dm2 * 1e5:.1f}, {lo}-{hi} MeV", published, -adn(d, n), "",
            "JUNO: ±0.009-0.032 statistical (expected counts)", "{:+.3f}")

    # ---- Super-K IV (arXiv:2312.12907)
    o = osc(sin2_theta12=0.305, sin2_theta13=0.0220, dm2_21_eV2=6.1e-5)
    sk = dict(components=("B8", "hep"), b8_flux="sno_nc", site="Kamioka", resolution_poly=SK4_RES, period="annual")
    s = engine.Setup(threshold=3.49, efficiency_table=sk_eff, **sk)
    d, n, ref = totals(s, o)
    row("SK 2312.12907 §V", "SK-IV 8B flux / SNO NC flux", 2.314 / 5.25, 0.5 * (d + n) / ref, "",
        "measured ±0.009 (SK) ⊕ NC 3.8 %; Δm² 6.1e-5", "{:.4f}")
    row("SK 2312.12907 §V", "SK-IV events, 22.5 kt, 2970 d", 65443, 0.5 * (d + n) * 22.5 * 2970 / DAYS, "",
        "measured ±1005; NC flux ±3.8 %", "{:.0f}")
    row("SK 2312.12907 §VIII", "SK-IV expected A_DN, Δm² 6.1e-5", -0.0238, -adn(d, n), "",
        "SK convention (D-N)/mean; SK weights the zenith shape by energy bin", "{:+.4f}")
    for dm2, published in ((6.1e-5, -0.0242), (7.5e-5, -0.0172), (4.8e-5, -0.0384)):
        o = osc(sin2_theta12=0.305, sin2_theta13=0.0220, dm2_21_eV2=dm2)
        s = engine.Setup(threshold=4.49, efficiency_table=sk_eff, **sk)
        d, n, _ = totals(s, o)
        row("SK 2312.12907 §VIII", f"SK-I range expected A_DN, Δm² {dm2 * 1e5:.1f}e-5", published, -adn(d, n), "",
            "T > 4.49 MeV with SK-IV response", "{:+.4f}")

    # ---- SNO salt (nucl-ex/0502021): ratios of the no-oscillation-equivalent fluxes above T_eff 5.5 MeV
    o = osc()
    sno = dict(components=("B8", "hep"), b8_flux="sno_nc", detector="heavy_water", site="SNOLAB", threshold=5.5,
               period="annual")
    cc = totals(engine.Setup(channel="cc_nue_d", **sno), o)
    es = totals(engine.Setup(channel="es", **sno), o)
    r_cc, r_es = 0.5 * (cc[0] + cc[1]) / cc[2], 0.5 * (es[0] + es[1]) / es[2]
    row("SNO nucl-ex/0502021", "φ_CC/φ_NC", 0.340, r_cc, "", "measured −0.039 +0.037", "{:.3f}")
    row("SNO nucl-ex/0502021", "φ_ES/φ_NC (2.35/4.94)", 2.35 / 4.94, r_es, "", "measured ±0.06", "{:.3f}")
    row("SNO nucl-ex/0502021", "φ_CC/φ_ES", 0.712, r_cc / r_es, "", "measured −0.087 +0.087", "{:.3f}")
    # SNO combined (arXiv:1109.0763): daytime P_ee at 10 MeV, c0 = 0.317 +- 0.018
    s = engine.Setup(components=("B8",), detector="heavy_water", channel="cc_nue_d", site="SNOLAB")
    pee, _ = engine.survival(inputs, probs, s, o, night=False)["B8"]
    energy = inputs.components["B8"][1]
    row("SNO 1109.0763 tab. VII", "P_ee(10 MeV), day", 0.317, float(np.interp(10.0, energy, pee)), "",
        "measured ±0.018; NuFIT 6.0 here", "{:.3f}")

    width = max(len(r[1]) for r in rows)
    print(f"{'source':24} {'quantity':{width}} {'published':>16} {'SNUfish':>16} {'diff':>8}  note")
    for source, what, pub, ours, rel, note in rows:
        print(f"{source:24} {what:{width}} {pub:>16} {ours:>16} {100 * rel:+7.1f}%  {note}")


if __name__ == "__main__":
    sys.exit(main())
