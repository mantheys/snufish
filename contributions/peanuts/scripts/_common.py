"""Shared by the PEANUTS drivers: the pinned PEANUTS checkout (submodule) and its version."""

import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PEANUTS = HERE / "PEANUTS"
sys.path.insert(0, str(PEANUTS))  # PEANUTS is not packaged: it runs from its checkout


def _git(*args):
    return subprocess.run(["git", "-C", str(PEANUTS), *args], capture_output=True, text=True, check=True).stdout.strip()


COMMIT = _git("rev-parse", "--short", "HEAD")
VERSION = _git("describe", "--tags").removeprefix("v")  # 1.6
REFERENCE = "arXiv:2303.15527"
CONTRIBUTOR = "SNUfish maintainers (wrapper); PEANUTS by T. E. Gonzalo and M. Lucente"
# PEANUTS's hard-coded matter potential. Earth (potentials.py): V/(hbar c) = 3.868e-7 m^-1 per mol/cm^3, 1.8e-5
# above sqrt(2) G_F N_A (hbar c)^2 from the spec's constants (3.86793e-7). Sun (matter_mixing.py, Vk):
# 2 E V / dm^2 = 3.868e-7 / 2.533 n_e E / dm^2 (MeV, eV^2), 3.6e-4 above the spec's 1.526493e-7.
CONSTANT_EARTH = "V/(hbar c) = 3.868e-7 m^-1 per mol/cm^3, hard-coded (potentials.py); 1.8e-5 above the spec's constants"
CONSTANT_SUN = ("2EV/dm^2 = 3.868e-7/2.533 n_e[mol/cm^3] E[MeV]/dm^2[eV^2], hard-coded (matter_mixing.Vk); "
                "3.6e-4 above the spec's 1.526493e-7")


def angles(osc):
    """PEANUTS takes angles in radians and Delta m^2_3l = Delta m^2_31 for normal ordering."""
    th = [float(np.arcsin(np.sqrt(osc[f"sin2_theta{ij}"]))) for ij in ("12", "13", "23")]
    return (*th, float(np.radians(osc["delta_cp_deg"])))


def quiet_import():
    """PEANUTS prints a warning when the optional pyslha is missing, and pandas warns about
    delim_whitespace; neither matters here."""
    warnings.filterwarnings("ignore", category=FutureWarning)
