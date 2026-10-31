"""Rate tables of DUNE solar analyses (thesis ch. 3, the DUNE solar Phase I paper) in the SOLAR analysis's
conventions: interactions per kt-yr of liquid argon, B16-GS98 8B + hep, annual (night share 0.507), above
thresholds in neutrino energy E_nu and in electron kinetic energy T_e. See docs/dune-solar-tables.md.

    python scripts/dune_solar_tables.py [--earth prem_full] [--b3-night]

Oscillation: dm2_21 = 6e-5 eV^2, sin2_12 = 0.304, sin2_13 = 0.022, dm2_31 = 2.515e-3 eV^2 (SOLAR
config/analysis/physics.json). Night: SOLAR's (snufish.export.ExactProbabilities(night_mode="solar")).
CC T_e: the electron alone (gammas undetected), from each 40K level's share of the cross section; only models
with levels (MARLEY 2) have it.
"""

import argparse

from snufish import engine
from snufish.export import ExactProbabilities, collect_inputs

SOLAR = {"dm2_21_eV2": 6e-5, "sin2_theta12": 0.304, "sin2_theta13": 0.022, "dm2_31_eV2": 2.515e-3}
THRESHOLDS = (5.0, 8.0, 10.0, 15.0)
CC_MODELS = ("ar40_marley", "ar40_marley1_bhattacharya2009", "ar40_marley2_bhattacharya2009")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--earth", default="prem_full", help="Earth model (SOLAR's is not known; default prem_full)")
    parser.add_argument("--b3-night", action="store_true", help="B3's night (surface, cell-integrated W) instead of SOLAR's")
    parser.add_argument("--night-fraction", type=float, default=0.507)
    args = parser.parse_args()

    inputs = engine.Inputs(collect_inputs())
    probabilities = ExactProbabilities() if args.b3_night else ExactProbabilities(night_mode="solar")
    osc = engine.oscillation(engine.parameters(inputs, "nufit60_global", SOLAR))
    base = engine.Setup(solar_model="b16_gs98", components=("B8", "hep"), detector="argon", site="SURF",
                        earth_model=args.earth, period="annual", night_fraction=args.night_fraction)

    def rate(setup):
        engine.check(inputs, setup)
        per = engine.component_totals(inputs, probabilities, setup, osc)
        return engine.quantity_value("rate", "annual", *engine.combine(per, list(setup.components)),
                                     night_fraction=setup.night_fraction)

    rows = []
    for model in CC_MODELS:
        cc = base.replace(channel="cc_nue_ar40", xsec_model=model)
        rows.append((f"CC {model}", "E_nu", [rate(cc.replace(nu_threshold=t)) for t in THRESHOLDS]))
        if model in inputs.data.get("xsec_levels", {}).get("cc_nue_ar40", {}):
            electron = engine.electron_smearing(inputs, "cc_nue_ar40", model, 0.0)
            rows.append((f"CC {model}", "T_e", [rate(cc.replace(threshold=t, smearing_table=electron)) for t in THRESHOLDS]))
    es = base.replace(channel="es")
    rows.append(("ES (BKS)", "E_nu", [rate(es.replace(nu_threshold=t)) for t in THRESHOLDS]))
    rows.append(("ES (BKS)", "T_e", [rate(es.replace(threshold=t)) for t in THRESHOLDS]))
    rows.append(("NC (SNOwGLoBES table)", "E_nu", [rate(base.replace(channel="nc_ar40", nu_threshold=t)) for t in THRESHOLDS]))

    print(f"{'channel':40s} {'above':5s} " + " ".join(f"{t:>9g}" for t in THRESHOLDS) + "   (MeV; per kt-yr)")
    for name, axis, values in rows:
        print(f"{name:40s} {axis:5s} " + " ".join(f"{v:9.4g}" for v in values))


if __name__ == "__main__":
    main()
