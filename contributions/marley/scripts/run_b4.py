"""MARLEY contribution to SNUfish B4: nu_e CC on 40Ar from MARLEY's own
`marley xsec` (total cross section against neutrino energy).

    git clone --branch v2.0.0 https://github.com/MARLEY-MC/marley.git
    cd marley && make IGNORE_ROOT=1 IGNORE_HEPMC3=1     # needs GSL; ROOT is not used
    python contributions/marley/scripts/run_b4.py --marley <that checkout>

MARLEY 2 treats transitions to bound 40K levels (the "Discrete" channel, from
measured B(GT)) and to the unbound continuum (HF-CRPA) separately; its
recommended configuration is HF-CRPA + Bhattacharya et al. 2009. Variants:

- ar40_marley2_bhattacharya2009 (also `default`): HF-CRPA + Bhattacharya 2009, (p,n)
- ar40_marley2_liu1998:          HF-CRPA + Liu et al. 1998, 40Ti beta decay
- ar40_marley2_bhattacharya1998: HF-CRPA + Bhattacharya et al. 1998, 40Ti beta decay
- ar40_marley1_bhattacharya2009: MARLEY's v1 reaction file (allowed approximation
  over all levels, no HF-CRPA), run by MARLEY 2: what SNOwGLoBES tabulates as
  xs_nue_Ar40_marley.dat above 5 MeV, but down to threshold

and, in bgt_levels.parquet next to data.parquet, the default variant's cross
section with one measured level's B(GT) raised by its 1 sigma, for every level
with a measured uncertainty: sigma is linear in each B(GT), so these give the
measured-B(GT) uncertainty of any rate exactly (independent levels).
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from snufish.contribution import write_contribution
from snufish.paths import contributions_dir
from snufish.spec import load_spec

CONFIGS = {  # variant: reaction files (MARLEY's data/react names, found on its search path)
    "ar40_marley2_bhattacharya2009": ["ve40ArCC_HF-CRPA.react", "ve40ArCC_Bhattacharya2009-Discrete.react"],
    "ar40_marley2_liu1998": ["ve40ArCC_HF-CRPA.react", "ve40ArCC_Liu1998-Discrete.react"],
    "ar40_marley2_bhattacharya1998": ["ve40ArCC_HF-CRPA.react", "ve40ArCC_Bhattacharya1998-Discrete.react"],
    "ar40_marley1_bhattacharya2009": ["v1/ve40ArCC_Bhattacharya2009.react"],
}
DEFAULT = "ar40_marley2_bhattacharya2009"
DISCRETE = "ve40ArCC_Bhattacharya2009-Discrete.react"
LEVEL = re.compile(r"^\s*([0-9.]+)\s+([0-9.eE+-]+)\s+([01])\s+([0-9.eE+-]+)\s*$")  # Ex, B, type, sigma(B)


def executable(checkout):
    for candidate in (checkout / "build" / "bin" / "marley", checkout / "build" / "marley", checkout / "marley"):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise SystemExit(f"no marley executable in {checkout} (build it first: make IGNORE_ROOT=1 IGNORE_HEPMC3=1)")


def xsec(marley, checkout, reactions, work, energies):
    """sigma(E) in cm^2 per 40Ar atom at the B4 energies, from `marley xsec`."""
    kemax = float(energies[-1])
    steps = int(round(kemax / (energies[1] - energies[0]))) + 1  # KE grid 0, step, ..., kemax
    config = {"reactions": reactions, "target": {"nuclides": [1000180400], "atom_fractions": [1.0]},
              "source": {"type": "mono", "neutrino": "ve", "energy": 10.0},
              "xsec": {"KEmin": 0.0, "KEmax": kemax, "steps": steps, "pdg": 12}}
    run = len(list(work.glob("config_*.js"))) + 1
    cfg, out = work / f"config_{run}.js", work / f"xsec_{run}.txt"
    cfg.write_text(json.dumps(config, indent=1))
    out.unlink(missing_ok=True)  # MARLEY asks before overwriting a file, and without a terminal keeps the old one
    # what MARLEY's setup_marley.sh sets: the data search root and its shared library
    env = dict(os.environ, MARLEY=str(checkout),
               LD_LIBRARY_PATH=f"{checkout / 'build' / 'lib'}:{os.environ.get('LD_LIBRARY_PATH', '')}")
    subprocess.run([str(marley), "xsec", "-o", str(out), str(cfg)], cwd=checkout, env=env, check=True,
                   capture_output=True)
    if not out.exists() or out.stat().st_mtime < cfg.stat().st_mtime:
        raise RuntimeError(f"marley xsec wrote no new table for {reactions}")
    table = np.loadtxt(out)
    return np.interp(energies, table[:, 0], table[:, 1]) * 1e-42  # file: 1e-42 cm^2 / atom


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--marley", type=Path, required=True, help="built MARLEY checkout")
    args = parser.parse_args()
    checkout = args.marley.resolve()
    marley = executable(checkout)
    spec = load_spec("B4_xsec")
    energies = spec.axis("energy")
    records, tables = [], {}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for variant, reactions in CONFIGS.items():
            print(f"marley xsec: {variant}")
            tables[variant] = xsec(marley, checkout, reactions, work, energies)
        levels = []
        lines = (checkout / "data" / "react" / DISCRETE).read_text().splitlines()
        measured = [k for k, line in enumerate(lines) if LEVEL.match(line)]
        for n, k in enumerate(measured, 1):
            ex, b, kind, err = LEVEL.match(lines[k]).groups()
            shifted = list(lines)
            shifted[k] = f"{ex} {float(b) + float(err):.6g} {kind} {err}"
            path = work / f"shifted_{n}.react"
            path.write_text("\n".join(shifted) + "\n")
            print(f"marley xsec: B(GT) of the {ex} MeV level + 1 sigma ({b} + {err})")
            sigma = xsec(marley, checkout, ["ve40ArCC_HF-CRPA.react", str(path)], work, energies)
            levels.append(dict(Level=float(ex), Kind="Fermi" if kind == "0" else "GT", Strength=float(b),
                               Error=float(err), Energy=energies, Sigma=sigma))
    for variant, sigma in tables.items():
        records += [("map", variant, "cc_nue_ar40", e, s) for e, s in zip(energies, sigma)]
    records += [("map", "default", "cc_nue_ar40", e, s) for e, s in zip(energies, tables[DEFAULT])]
    version = (checkout / ".VERSION").read_text().strip() if (checkout / ".VERSION").exists() else "2.0.0"
    commit = subprocess.run(["git", "-C", str(checkout), "rev-parse", "--short", "HEAD"], capture_output=True,
                            text=True).stdout.strip() or None
    meta = {
        "tool": "marley",
        "tool_version": version,
        "tool_commit": commit,
        "benchmark": spec.id,
        "benchmark_version": spec.version,
        "contributor": "SNUfish maintainers (wrapper)",
        "date": datetime.date.today().isoformat(),
        "command": "python contributions/marley/scripts/run_b4.py --marley <built MARLEY checkout>",
        "settings": {
            "reactions": {v: r for v, r in CONFIGS.items()},
            "xsec": "marley xsec, KE 0 to 20 MeV on the B4 step, 1e-42 cm^2/atom converted to cm^2",
            "default": DEFAULT,
            "bgt_levels": f"bgt_levels.parquet: the default variant with each measured level of {DISCRETE} "
                          "raised by its 1 sigma (one row per level)",
        },
        "license": "CC-BY-4.0",
        "notes": "MARLEY 2.0.0: HF-CRPA for the continuum, measured B(GT) for bound levels (see its reaction "
                 "files for references). Cite Gardiner, PRC 103, 044604 (2021) and CPC (arXiv:2101.11867).",
    }
    path = contributions_dir() / meta["tool"] / spec.id / meta["tool_version"]
    write_contribution(path, meta, records, spec)
    pd.DataFrame(levels).to_parquet(path / "bgt_levels.parquet", index=False)
    print(f"wrote {path} ({len(records)} rows, {len(levels)} B(GT) levels)")


if __name__ == "__main__":
    main()
