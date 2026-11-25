"""Theoretical uncertainty of the CC day-night asymmetry in argon at SURF, for the DUNE solar Phase I paper.

    python scripts/dune_phase1_adn_budget.py [--n 100] [--sets nufit61_global solar_global_2024]

Same settings as scripts/dune_phase1_rates.py (B16-GS98 8B + hep, MARLEY v1 allowed CC, SURF), with the oscillation
parameters centred on the analysis point (dm2_21 = 6e-5 eV^2, sin2_12 = 0.304, sin2_13 = 0.022) and the errors of each
parameter set (sin2_13: +-0.00056). A_DN = 2 (N - D) / (N + D) of the CC rate, no detector response, no threshold.

Two sources are reported, as in ``snufish budget``:

* oscillation parameters: standard deviation of A_DN over draws of (dm2_21, sin2_12, sin2_13), relative to the central A_DN;
* Earth model: the range of A_DN over the state-of-the-art Earth models (reference/status.yaml: PREM with the CRUST1.0
  column under the detector, and with the CRUST1.0 crust along every night trajectory), relative to the central value.
  The "legacy spread" over every selectable model, approximations included, is printed for context only.
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from snufish import engine  # noqa: E402
from snufish.export import ExactProbabilities, collect_inputs  # noqa: E402
from dune_phase1_rates import CC_MODEL, SETTINGS, SOLAR  # noqa: E402

SIN13_ERROR = 0.00056


def budget(set_name, n, seed=1):
    inputs = engine.Inputs(collect_inputs())
    registry = inputs["parameter_sets"]["sets"][set_name]
    custom = {"dm2_21_eV2": {"value": SOLAR["dm2_21_eV2"], "error": registry["dm2_21_eV2"]["error"]},
              "sin2_theta12": {"value": SOLAR["sin2_theta12"], "error": registry["sin2_theta12"]["error"]},
              "sin2_theta13": {"value": SOLAR["sin2_theta13"], "error": [SIN13_ERROR, SIN13_ERROR]}}
    params = engine.parameters(inputs, set_name, custom)
    setup = engine.Setup(**dict(SETTINGS, earth_model="prem_crust1"), period="annual").replace(
        channel="cc_nue_ar40", xsec_model=CC_MODEL)
    rows, _ = engine.budget(inputs, ExactProbabilities(), setup, params, "adn", n=n, seed=seed,
                            ranges=("earth_model",), legacy=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=100, help="oscillation-parameter draws")
    parser.add_argument("--sets", nargs="+", default=["nufit61_global", "solar_global_2024"])
    args = parser.parse_args()
    for set_name in args.sets:
        for r in budget(set_name, args.n):
            print(f"{set_name:20s} {r['Source']:32s} {r['Kind']:14s} A_DN = {r['Central']:.4f}  "
                  f"relative = {r['Relative']:.4f}")


if __name__ == "__main__":
    main()
