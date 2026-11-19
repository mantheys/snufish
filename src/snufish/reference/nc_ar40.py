"""Neutral-current excitation of the discrete 1+ levels of 40Ar from their measured M1 strength,

    nu + 40Ar(0+) -> nu' + 40Ar*(1+, E_x),

the discrete half of SNUfish's default NC model on 40Ar (the other half is the HF+CRPA continuum of Van Dessel et
al. 2019; ``snufish.export.nc_ar40_default``). It follows the plan of MARLEY's authors for an NC model (Gardiner et
al., arXiv:2604.26801, sec. VI: "discrete neutral GT strengths based on photonuclear interaction data" with
"HF-CRPA NC responses") and MARLEY 2's treatment of a discrete transition:

- GT0 strength from M1 (Langanke et al., PRL 93, 202501 (2004)): the levels are taken as pure isovector spin-flip,
  so B(M1 up) = (3/4pi) (g_IV/2)^2 B(sigma tau_3), g_IV = (g_s^p - g_s^n)/2 = mu_p - mu_n = 4.706, with measured
  B(M1) (reference/xsec/tornow2025_m1_ar40.yaml, Tornow et al., PRC 112, 054320 (2025)); the measured strength
  carries the quenching of the spin operator, so the bare couplings are used throughout.
- NC axial current (g_A/2) sigma tau_3, so per level, with E' = E - E_x and theta the neutrino scattering angle,

      dsigma/dcos(theta) = G_F^2/(2 pi) E'^2 (g_A/2)^2 B(sigma tau_3) (1 - cos(theta)/3) F(kappa)^2 G_A(Q^2)^2/g_A^2,

  the allowed GT angular factor (MARLEY's lepton factors for a massless outgoing lepton), integrated over angles;
  without the form factors sigma = G_F^2/pi E'^2 (g_A/2)^2 B(sigma tau_3).
- Momentum dependence as in MARLEY 2's default: the squared nuclear form factor F(kappa)^2, adapted Klein-Nystrand
  (R = sqrt(5 r0^2/3 - 10 a^2), a = 0.7 fm, r0 = 3.4274 fm the 40Ar rms charge radius of Angeli & Marinova 2013),
  and the dipole axial nucleon form factor, M_A = 1032 MeV, kappa^2 = E^2 + E'^2 - 2 E E' cos(theta), Q^2 = kappa^2 -
  E_x^2. They lower sigma by 1 % at 10 MeV, 3 % at 15 MeV, 5 % at 20 MeV, 36 % at 50 MeV and 80 % at 100 MeV.

Neglected: the orbital and isoscalar parts of the M1 strength, the next-to-leading GT multipoles (MARLEY's kappa/M_N
terms) and so the difference between neutrinos and antineutrinos (this is the neutrino cross section), and the
1+ strength not yet measured (the shell model puts about 1 mu_N^2 between 8 and 9 MeV; Tornow et al. 2025).
Checked on 12C(nu, nu')12C*(15.11 MeV), the KARMEN measurement (10.5(1.3) e-42 cm^2, nu_e + nu_mu-bar from pi+ decay
at rest): from its B(M1 up) (Gamma_0 = 38.5 eV) this method gives 14.8 e-42 without form factors, 40 % high, as
expected of the orbital part of that M1 strength and of the momentum transfer at those energies.
"""

from functools import lru_cache

import numpy as np

from ..paths import repo_root
from ..spec import load_spec

G_A = 1.2754                          # PDG 2024
G_IV = 2.79284734 + 1.91304273        # mu_p - mu_n (mu_N), CODATA 2018: (g_s^p - g_s^n)/2
M_A = 1032.0                          # MeV, MARLEY 2's dipole axial mass
R0_AR40, A_KN = 3.4274, 0.7           # fm: rms charge radius of 40Ar (MARLEY's table), Klein-Nystrand range
# (g_A/2)^2 B(sigma tau_3) per B(M1 up) in mu_N^2
GT0_PER_M1 = (G_A / 2) ** 2 * (4 * np.pi / 3) / (G_IV / 2) ** 2
_X, _W = np.polynomial.legendre.leggauss(48)   # cos(theta) nodes and weights


def klein_nystrand(kappa, r0=R0_AR40, a=A_KN):
    """Adapted Klein-Nystrand nuclear form factor at 3-momentum transfer ``kappa`` (MeV), as MARLEY 2's default."""
    hbarc = load_spec("B4_xsec")["constants"]["hbarc_MeV_fm"]
    radius = np.sqrt(5 * r0**2 / 3 - 10 * a**2)
    q = np.asarray(kappa, dtype=float) / hbarc
    x = np.where(q * radius > 1e-8, q * radius, 1e-8)
    j1 = (np.sin(x) / x - np.cos(x)) / x
    return np.where(q * radius > 1e-8, 3 * j1 / x / (1 + q**2 * a**2), 1.0)


@lru_cache(maxsize=1)
def levels():
    """(E_x MeV, B(M1 up) mu_N^2, its error) of the measured 1+ levels (reference/xsec/tornow2025_m1_ar40.yaml)."""
    import yaml

    rows = yaml.safe_load((repo_root() / "reference" / "xsec" / "tornow2025_m1_ar40.yaml").read_text())["levels"]
    return tuple(np.array([r[k] for r in rows], dtype=float) * s
                 for k, s in (("ex_keV", 1e-3), ("b_m1_1e-3muN2", 1e-3), ("error_1e-3muN2", 1e-3)))


def discrete(energy, form_factors=True, strengths=None):
    """sigma(E) in cm^2 of nu 40Ar -> nu' 40Ar*(1+), summed over the measured levels (module docstring);
    ``strengths`` replaces the levels' B(M1 up) (mu_N^2), e.g. to propagate their errors."""
    constants = load_spec("B4_xsec")["constants"]
    gf = constants["G_F_GeV-2"] * 1e-6                       # MeV^-2
    hbarc2 = (constants["hbarc_MeV_fm"] * 1e-13) ** 2         # MeV^2 cm^2
    ex, b_m1, _ = levels()
    b_m1 = b_m1 if strengths is None else np.asarray(strengths, dtype=float)
    e = np.atleast_1d(np.asarray(energy, dtype=float))[:, None, None]
    ep = np.clip(e - ex[None, :, None], 0.0, None)           # [E, level, 1]
    if form_factors:
        kappa2 = e**2 + ep**2 - 2 * e * ep * _X[None, None, :]
        q2 = np.clip(kappa2 - ex[None, :, None] ** 2, 0.0, None)
        ff = klein_nystrand(np.sqrt(kappa2)) ** 2 / (1 + q2 / M_A**2) ** 4
    else:
        ff = 1.0
    angular = np.sum(_W * (1 - _X / 3) * ff * np.ones_like(ep), axis=-1) / 2   # 1 without form factors
    sigma = gf**2 / np.pi * ep[..., 0] ** 2 * GT0_PER_M1 * b_m1[None, :] * angular * hbarc2
    out = sigma.sum(axis=1)
    return out if np.ndim(energy) else float(out[0])
