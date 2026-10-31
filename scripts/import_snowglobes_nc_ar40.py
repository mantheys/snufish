"""Writes reference/xsec/snowglobes_nc_ar40.yaml: the nu + 40Ar -> nu + 40Ar* (NC inelastic) cross section
that SNOwGLoBES tabulates, so that SNUfish's NC column on argon uses the same table as SNOwGLoBES rate tables.

    python scripts/import_snowglobes_nc_ar40.py --snowglobes <SNOwGLoBES checkout at 6fa928e>

Source: xscns/xs_nc_nue_Ar40.dat (added in SNOwGLoBES b59e1d7, 2018-10-22, unchanged since b469e5f): log10(E/GeV)
and sigma/E in 1e-38 cm^2/GeV per flavour. All six columns are identical (flavour independent at these energies),
so one is kept. Converted here to sigma in cm^2 per 40Ar nucleus; energies 0.5-100 MeV as tabulated.
"""

import argparse
import subprocess
from pathlib import Path

import numpy as np
import yaml

FILE = "xscns/xs_nc_nue_Ar40.dat"
OUT = Path(__file__).resolve().parents[1] / "reference" / "xsec" / "snowglobes_nc_ar40.yaml"
HEADER = """\
# Neutrino-40Ar neutral-current inelastic cross section (cm^2 per 40Ar nucleus), any active flavour, as tabulated by
# SNOwGLoBES (xscns/xs_nc_nue_Ar40.dat, commit {commit}; added in b59e1d7, 2018-10-22). Written by
# scripts/import_snowglobes_nc_ar40.py.
#
# PROVENANCE (weak): SNOwGLoBES's documentation (doc/tex_src/snowglobes_1.3.tex, sec. "Charged and Inelastic Neutral
# Current Interactions with Argon") calls it a QRPA calculation from private communication with P. Pirinen and
# J. Suhonen, "without experimentally measured nuclear levels, but with a spectrum of final states". No publication
# of this 40Ar table has been identified. It is used only so that SNUfish's NC column on argon is the same table as
# SNOwGLoBES rate tables; it is not a validated cross section.
#
# The table is zero below 8.0 MeV, has 23 small negative values from 8.0 to 9.0 MeV (interpolation artefacts,
# |sigma| < 2e-44 cm^2) and is positive from 9.07 MeV. The negatives are kept here as published and set to zero by
# the engine (snufish.export). They are not negligible: kept, they lower the B16-GS98 8B+hep NC rate above
# E_nu = 5 MeV by 7.7 % (28.80 -> 26.58 per kt-yr); above 10 MeV they do not enter.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snowglobes", type=Path, required=True)
    args = parser.parse_args()
    data = np.loadtxt(args.snowglobes / FILE, comments="#")
    assert all(np.allclose(data[:, 1], data[:, k]) for k in range(2, 7)), "flavour columns differ"
    energy_gev = 10 ** data[:, 0]
    sigma = data[:, 1] * 1e-38 * energy_gev
    commit = subprocess.run(["git", "-C", str(args.snowglobes), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip() or "unknown"
    body = {"source": f"SNOwGLoBES {FILE} @ {commit}",
            "model": "QRPA, Pirinen & Suhonen (private communication to SNOwGLoBES, 2018); unpublished",
            "flavours": "nu_e, nu_mu, nu_tau and antineutrinos identical",
            "energy_MeV": [float(f"{e:.6g}") for e in energy_gev * 1e3],
            "sigma_cm2": [float(f"{s:.6g}") for s in sigma]}
    OUT.write_text(HEADER.format(commit=commit) + yaml.safe_dump(body, default_flow_style=None, width=150, sort_keys=False))
    print(f"wrote {OUT} ({len(sigma)} points)")


if __name__ == "__main__":
    main()
