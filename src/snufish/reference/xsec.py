"""Reference cross sections for B4: neutrino-electron elastic scattering at
tree level in the Standard Model (no radiative corrections), integrated over
all recoil energies,

    dsigma/dT = (2 G_F^2 m_e / pi) [g1^2 + g2^2 (1 - T/E)^2 - g1 g2 m_e T / E^2],

with g1 = 1/2 + s_W^2 (nu_e: CC + NC), -1/2 + s_W^2 (nu_mu, nu_tau: NC),
g2 = s_W^2, and T_max = 2 E^2 / (m_e + 2 E).
"""

import numpy as np


def es_total(energy_mev, flavour, constants):
    """sigma(E) in cm^2 per electron, for flavour 'nue', 'numu' or 'nutau'."""
    E = np.asarray(energy_mev, dtype=float)
    me, sw2 = constants["m_e_MeV"], constants["sin2_theta_W"]
    G = constants["G_F_GeV-2"] * 1e-6                     # MeV^-2
    hbarc2 = (constants["hbarc_MeV_fm"] * 1e-13) ** 2     # MeV^2 cm^2
    g1 = (0.5 if flavour == "nue" else -0.5) + sw2
    g2 = sw2
    T = 2 * E**2 / (me + 2 * E)
    integral = g1**2 * T + g2**2 * (E / 3) * (1 - (1 - T / E) ** 3) - g1 * g2 * me * T**2 / (2 * E**2)
    return 2 * G**2 * me / np.pi * integral * hbarc2


def es_above(energy_mev, flavour, constants, t_min_mev):
    """sigma(E; T > t_min) in cm^2 per electron: the tree-level cross section
    integrated over electron kinetic energies from t_min to T_max."""
    E = np.asarray(energy_mev, dtype=float)
    me, sw2 = constants["m_e_MeV"], constants["sin2_theta_W"]
    G = constants["G_F_GeV-2"] * 1e-6
    hbarc2 = (constants["hbarc_MeV_fm"] * 1e-13) ** 2
    g1 = (0.5 if flavour == "nue" else -0.5) + sw2
    g2 = sw2
    t_max = 2 * E**2 / (me + 2 * E)
    lo = np.minimum(t_min_mev, t_max)

    def primitive(T):
        return g1**2 * T - g2**2 * (E / 3) * (1 - T / E) ** 3 - g1 * g2 * me * T**2 / (2 * E**2)

    return 2 * G**2 * me / np.pi * (primitive(t_max) - primitive(lo)) * hbarc2


def solve_b4(spec, grid="map"):
    """Tree level as `default`; with radiative corrections (BKS 1995, all recoil energies) as `es_bks`."""
    from .radiative import es_above as bks_above

    energies = spec.axis("energy", grid)
    records = []
    for flavour in ("nue", "numu", "nutau"):
        for e, sigma in zip(energies, es_total(energies, flavour, spec["constants"])):
            records.append((grid, "default", f"es_{flavour}", e, sigma))
        for e, sigma in zip(energies, bks_above(energies, flavour, spec["constants"], [0.0])[:, 0]):
            records.append((grid, "es_bks", f"es_{flavour}", e, sigma))
    return records
