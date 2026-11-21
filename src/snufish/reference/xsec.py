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


def thresholds(spec):
    """{quantity: (flavour, T_min in MeV)} for the spec's thresholded ES quantities, es_<flavour>_T<T_min>."""
    out = {}
    for name in spec.quantities:
        head, _, t = name.partition("_T")
        if name.startswith("es_") and t:
            out[name] = (head[len("es_"):], float(t))
    return out


def bks_threshold(energy_mev, flavour, constants, t_min_mev):
    """sigma(E; T > t_min) with the BKS 1995 radiative corrections, cm^2 per electron (zero where
    T_max <= t_min): the end-point integration of `radiative.es_above` at u = t_min / T_max, per energy."""
    from .radiative import es_above as bks_above

    E = np.atleast_1d(np.asarray(energy_mev, dtype=float))
    me = constants["m_e_MeV"]
    u = t_min_mev / (2 * E**2 / (me + 2 * E))
    return np.array([bks_above([e], flavour, constants, [f])[0, 0] if f < 1.0 else 0.0 for e, f in zip(E, u)])


def solve_b4(spec, grid="map"):
    """Tree level as `default`; with radiative corrections (BKS 1995) as `es_bks`: all recoil energies
    (es_<flavour>) and above each recoil threshold of the spec (es_<flavour>_T<threshold>)."""
    from .radiative import es_above as bks_above

    energies = spec.axis("energy", grid)
    c = spec["constants"]
    records = []
    for flavour in ("nue", "numu", "nutau"):
        for e, sigma in zip(energies, es_total(energies, flavour, c)):
            records.append((grid, "default", f"es_{flavour}", e, sigma))
        for e, sigma in zip(energies, bks_above(energies, flavour, c, [0.0])[:, 0]):
            records.append((grid, "es_bks", f"es_{flavour}", e, sigma))
    for name, (flavour, t_min) in thresholds(spec).items():
        for e, sigma in zip(energies, es_above(energies, flavour, c, t_min)):
            records.append((grid, "default", name, e, sigma))
        for e, sigma in zip(energies, bks_threshold(energies, flavour, c, t_min)):
            records.append((grid, "es_bks", name, e, sigma))
    return records
