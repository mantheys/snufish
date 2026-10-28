"""SNOwGLoBES contribution to SNUfish B4 (cross sections from its xscns/ files).

    SNOWGLOBES=~/Code/GLoBES/snowglobes python run_b4.py

The files give log10(E/GeV) and sigma/E in 1e-38 cm^2/GeV per target, one
column per flavour (nu_e, nu_mu, nu_tau, anti...). sigma/E is interpolated
linearly in log10 E; outside a table's range the value is NaN (not provided):
no extrapolation. Writes contributions/snowglobes/B4_xsec/<version>/.
"""

import datetime
import os
import subprocess
from pathlib import Path

import numpy as np

from snufish.contribution import write_contribution
from snufish.paths import contributions_dir
from snufish.spec import load_spec

SNOWGLOBES = Path(os.environ.get("SNOWGLOBES", Path.home() / "Code" / "GLoBES" / "snowglobes"))
COLUMNS = {"nue": 1, "numu": 2, "nutau": 3}

# (variant, channel) -> (file, flavour column)
SOURCES = {
    ("default", "es_nue"): ("xs_nue_e.dat", "nue"),
    ("default", "es_numu"): ("xs_nue_e.dat", "numu"),
    ("default", "es_nutau"): ("xs_nue_e.dat", "nutau"),
    ("default", "cc_nue_ar40"): ("xs_nue_Ar40.dat", "nue"),
    ("default", "cc_nue_o16"): ("xs_nue_O16.dat", "nue"),
    ("default", "cc_nue_c13"): ("xs_nue_C13.dat", "nue"),
    ("default", "cc_nue_d"): ("xs_nue_d.dat", "nue"),
    ("ar40_klmv", "cc_nue_ar40"): ("xs_nue_Ar40_klmv.dat", "nue"),
    ("ar40_marley", "cc_nue_ar40"): ("xs_nue_Ar40_marley.dat", "nue"),
    ("ar40_marley1", "cc_nue_ar40"): ("xs_nue_Ar40_marley1.dat", "nue"),
}


def sigma(file, flavour, energies_mev):
    table = np.loadtxt(SNOWGLOBES / "xscns" / file, comments="#")
    log_e, per_gev = table[:, 0], table[:, COLUMNS[flavour]]
    x = np.log10(np.asarray(energies_mev) * 1e-3)
    inside = (x >= log_e[0] - 1e-9) & (x <= log_e[-1] + 1e-9)
    values = np.interp(x, log_e, per_gev) * 1e-38 * np.asarray(energies_mev) * 1e-3
    return np.where(inside, values, np.nan)


def _git(*args):
    return subprocess.run(["git", "-C", str(SNOWGLOBES), *args], capture_output=True, text=True,
                          check=True).stdout.strip()


def main():
    spec = load_spec("B4_xsec")
    energies = spec.axis("energy")
    records = [("map", variant, channel, e, s)
               for (variant, channel), (file, flavour) in SOURCES.items()
               for e, s in zip(energies, sigma(file, flavour, energies))]
    commit = _git("rev-parse", "--short", "HEAD")
    dirty = bool(_git("status", "--porcelain", "xscns"))
    meta = {
        "tool": "snowglobes",
        "tool_version": f"git-{commit}",
        "tool_commit": commit,
        "benchmark": spec.id,
        "benchmark_version": spec.version,
        "contributor": "SNUfish maintainers (wrapper)",
        "date": datetime.date.today().isoformat(),
        "command": "SNOWGLOBES=<path> python contributions/snowglobes/scripts/run_b4.py",
        "settings": {
            "files": {f"{v}/{c}": f for (v, c), (f, _) in SOURCES.items()},
            "interpolation": "sigma/E linear in log10 E; NaN outside each table",
            "units": "files in 1e-38 cm^2/GeV (sigma/E), as their headers state",
            "repository": "fork git@github.com:mantheys/snowglobes.git",
            "xscns_modified_locally": dirty,
        },
        "license": "CC-BY-4.0",
        "notes": "ES tables start at 0.5 MeV (no pp, no 7Be 384 keV line); MARLEY and deuteron tables at 5 MeV.",
    }
    path = contributions_dir() / meta["tool"] / spec.id / meta["tool_version"]
    write_contribution(path, meta, records, spec)
    print(f"wrote {path} ({len(records)} rows)")


if __name__ == "__main__":
    main()
