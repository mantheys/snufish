"""Raw solar-neutrino interaction rates on argon for the DUNE solar Phase I paper, as LaTeX macros, a table and
JSON. SOLAR's settings (docs/dune-solar-tables.md): B16-GS98 8B + hep, dm2_21 = 6e-5 eV^2, sin2_12 = 0.304,
sin2_13 = 0.022, SOLAR's night at SURF, night share 0.507, annual, per kt-yr of liquid argon, no detector response.

    python scripts/dune_phase1_rates.py [--out build/dune_phase1] [--cc-model ar40_marley1_bhattacharya2009]

Writes <out>/snufish_rates.tex (\\snufishRate<Channel><Axis><Threshold> macros, e.g. \\snufishRateCCTeFive),
<out>/snufish_rates_table.tex (a booktabs tabular for the paper's appendix table) and <out>/snufish_rates.json
(day, night and annual rates with the settings and the SNUfish version). Axis Enu is a cut in true neutrino energy,
Te in electron kinetic energy (CC: the electron alone, from the 40K level shares; ES: the recoil). NC has
no electron: E_nu cuts only. CC: the cross section of DUNE's MARLEY samples (MARLEY v1.2.1 in dunesw v09_91_04,
reaction file ve40ArCC_Bhattacharya2009.react, allowed approximation: ar40_marley1_allowed, equal to SOLAR's
neutrino_cc_final.txt). The T_e cut takes the model's own 40K level shares (from its measured B(GT)), or MARLEY 2's
(ar40_marley2_bhattacharya2009) for a model without them.
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))

from snufish import __version__, engine  # noqa: E402
from snufish.export import ExactProbabilities, collect_inputs  # noqa: E402

SOLAR = {"dm2_21_eV2": 6e-5, "sin2_theta12": 0.304, "sin2_theta13": 0.022, "dm2_31_eV2": 2.515e-3}
SETTINGS = dict(solar_model="b16_gs98", components=("B8", "hep"), detector="argon", site="SURF",
                earth_model="prem_full", night_fraction=0.507)
CC_MODEL = "ar40_marley1_allowed"
FALLBACK_LEVELS = "ar40_marley2_bhattacharya2009"  # the 40K level shares of a model without its own
# (channel, axis, threshold in MeV): the cuts the paper quotes
CUTS = [("CC", "Enu", 1.0), ("ES", "Enu", 1.0), ("NC", "Enu", 1.0),
        ("CC", "Enu", 5.0), ("ES", "Enu", 5.0), ("NC", "Enu", 5.0),
        ("CC", "Te", 5.0), ("ES", "Te", 5.0)]
CHANNELS = {"CC": "cc_nue_ar40", "ES": "es", "NC": "nc_ar40"}
NUMBER_WORDS = {1.0: "One", 5.0: "Five", 8.0: "Eight", 10.0: "Ten", 15.0: "Fifteen"}
PERIODS = ("day", "night", "annual")


def rates(cc_model=CC_MODEL, earth_model="prem_full"):
    """{(channel, axis, threshold): {period: rate per kt-yr}} for CUTS."""
    inputs = engine.Inputs(collect_inputs())
    probabilities = ExactProbabilities(night_mode="solar")
    osc = engine.oscillation(engine.parameters(inputs, "nufit60_global", SOLAR))
    base = engine.Setup(**{**SETTINGS, "earth_model": earth_model}, period="annual")
    electron = engine.electron_smearing(inputs, "cc_nue_ar40", levels_model(inputs, cc_model), 0.0)  # E_nu -> T_e

    out = {}
    for channel, axis, threshold in CUTS:
        setup = base.replace(channel=CHANNELS[channel])
        if channel == "CC":
            setup = setup.replace(xsec_model=cc_model)
        if axis == "Enu":
            setup = setup.replace(nu_threshold=threshold)
        elif channel == "CC":
            setup = setup.replace(threshold=threshold, smearing_table=electron)
        else:
            setup = setup.replace(threshold=threshold)
        engine.check(inputs, setup)
        per = engine.combine(engine.component_totals(inputs, probabilities, setup, osc), list(setup.components))
        out[channel, axis, threshold] = {p: engine.quantity_value("rate", p, *per, night_fraction=setup.night_fraction)
                                         for p in PERIODS}
    return out


def levels_model(inputs, cc_model):
    return cc_model if cc_model in inputs.data.get("xsec_levels", {}).get("cc_nue_ar40", {}) else FALLBACK_LEVELS


def latex_number(value, digits=3):
    """$1.15\\times10^{3}$, the paper's style."""
    mantissa, exponent = f"{value:.{digits - 1}e}".split("e")
    return f"${mantissa}\\times10^{{{int(exponent)}}}$"


def macro_name(channel, axis, threshold):
    return f"snufishRate{channel}{axis}{NUMBER_WORDS[threshold]}"


def commit():
    try:
        return subprocess.run(["git", "describe", "--always", "--dirty"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def write(values, out, cc_model, earth_model, levels=None):
    out.mkdir(parents=True, exist_ok=True)
    levels = levels or cc_model
    version = f"{__version__} ({commit()})"
    header = (f"% Written by SNUfish {version}, scripts/dune_phase1_rates.py: do not edit.\n"
              f"% Annual rates per kt-yr of liquid argon, B16-GS98 8B + hep, SOLAR's oscillation, night and night share\n"
              f"% (0.507), CC model {cc_model} (T_e cuts: level shares of {levels}), Earth {earth_model}.\n")

    lines = [header, f"\\newcommand{{\\snufishVersion}}{{{__version__}}}\n",
             f"\\newcommand{{\\snufishCommit}}{{{commit()}}}\n"]
    for key, value in values.items():
        lines.append(f"\\newcommand{{\\{macro_name(*key)}}}{{{latex_number(value['annual'])}}}\n")
    (out / "snufish_rates.tex").write_text("".join(lines))

    def cell(key):
        return latex_number(values[key]["annual"]) if key in values else "---"

    rows = []
    for axis, threshold, label in (("Enu", 1.0, r"$E_\nu > 1$ MeV"), ("Enu", 5.0, r"$E_\nu > 5$ MeV"),
                                   ("Te", 5.0, r"$T_e > 5$ MeV")):
        keys = [(c, axis, threshold) for c in CHANNELS]
        total = latex_number(sum(values[k]["annual"] for k in keys)) if all(k in values for k in keys) else "---"
        rows.append(f"{label} & " + " & ".join(cell(k) for k in keys) + f" & {total} \\\\\n")
    table = (header + "\\begin{tabular}{lcccc}\n\\toprule\n"
             "Cut & \\multicolumn{4}{c}{Solar $\\nu$ interactions in LAr [kt$^{-1}$\\,yr$^{-1}$]} \\\\\n"
             " & CC & ES & NC & Total \\\\\n\\midrule\n" + "".join(rows) + "\\bottomrule\n\\end{tabular}\n")
    (out / "snufish_rates_table.tex").write_text(table)

    record = {"snufish": version, "units": "interactions per kt-yr (365.25 d) of liquid argon",
              "settings": {**SETTINGS, "earth_model": earth_model, "components": list(SETTINGS["components"]),
                           "oscillation": SOLAR, "night": "SOLAR (1.478 km, latitude 44.35 deg, 80 nadir bins)",
                           "cc_model": cc_model, "cc_te_level_shares": levels},
              "rates": [{"channel": c, "axis": a, "threshold_MeV": t, "macro": macro_name(c, a, t), **v}
                        for (c, a, t), v in values.items()]}
    (out / "snufish_rates.json").write_text(json.dumps(record, indent=1) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "dune_phase1")
    parser.add_argument("--cc-model", default=CC_MODEL, help="CC cross section for the E_nu cuts")
    parser.add_argument("--earth", default="prem_full", help="Earth model (SOLAR's is not known)")
    args = parser.parse_args()

    values = rates(args.cc_model, args.earth)
    write(values, args.out, args.cc_model, args.earth, levels_model(engine.Inputs(collect_inputs()), args.cc_model))
    print(f"{'channel':8s} {'cut':12s} {'day':>9s} {'night':>9s} {'annual':>9s}   (per kt-yr)")
    for (channel, axis, threshold), v in values.items():
        print(f"{channel:8s} {axis + ' > ' + format(threshold, 'g'):12s} "
              + " ".join(f"{v[p]:9.4g}" for p in PERIODS))
    print(f"Wrote {args.out}/snufish_rates.tex, snufish_rates_table.tex, snufish_rates.json")


if __name__ == "__main__":
    main()
