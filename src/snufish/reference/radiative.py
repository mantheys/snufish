"""Neutrino-electron elastic scattering with electroweak, QCD and QED
radiative corrections: Bahcall, Kamionkowski and Sirlin, PRD 51, 6146 (1995),
arXiv:astro-ph/9502003, appendices A and B,

    dsigma/dT = (2 G_F^2 m / pi) { g_L^2(T) [1 + a/pi f_-(z)] + g_R^2(T) (1 - z)^2 [1 + a/pi f_+(z)]
                                   - g_R(T) g_L(T) (m/q) z [1 + a/pi f_+-(z)] },   z = T/q,

with g_L = rho (1/2 - kappa(T) s^2) - 1 (nu_e; without the -1 for nu_mu, nu_tau),
g_R = -rho kappa(T) s^2, rho = 1.0126, kappa_e = 0.9791 + 0.0097 I(T),
kappa_mu = 0.9970 - 0.00037 I(T), s^2 = sin^2 theta_W(m_Z) MS-bar = 0.2317,
and the inelastic nu e -> nu e gamma included (the photon not detected).
The QED functions diverge logarithmically at the end point (where perturbation
theory breaks down); the differential cross section is clipped at zero there,
which only affects the last ~1e-3 of the recoil range.
"""

import numpy as np
from scipy.special import spence

ALPHA = 1 / 137.035999
SIN2 = 0.2317        # sin^2 theta_W(m_Z), MS-bar, as used by BKS
RHO = 1.0126         # +- 0.0016
KAPPA = {"nue": (0.9791, 0.0097), "numu": (0.9970, -0.00037), "nutau": (0.9970, -0.00037)}  # +- 0.0025


def _L(x):
    """L(x) = int_0^x ln|1 - t| dt / t = -Li2(x); scipy's spence(1 - x) is Li2(x)."""
    return -spence(1.0 - x)


def couplings(T, flavour, me):
    x = np.sqrt(1.0 + 2.0 * me / T)
    I = (1.0 / 3.0 + (3.0 - x**2) * (0.5 * x * np.log((x + 1.0) / (x - 1.0)) - 1.0)) / 6.0
    k0, k1 = KAPPA[flavour]
    kappa = k0 + k1 * I
    gl = RHO * (0.5 - kappa * SIN2) - (1.0 if flavour == "nue" else 0.0)
    gr = -RHO * kappa * SIN2
    return gl, gr


def qed(q, T, me):
    """f_-(z), (1 - z)^2 f_+(z) and f_+-(z), eqs. (B3)-(B5)."""
    z = T / q
    E = T + me
    l = np.sqrt(E**2 - me**2)
    beta = l / E
    c = E / l * np.log((E + l) / me) - 1.0
    log_end = np.log(np.maximum(1.0 - z - me / (E + l), 1e-300))
    lz, l1z = np.log(z), np.log(1.0 - z)
    f_minus = (c * (2 * log_end - l1z - 0.5 * lz - 5.0 / 12.0) + 0.5 * (_L(z) - _L(beta)) - 0.5 * l1z**2
               - (11.0 / 12.0 + z / 2) * l1z + z * (lz + 0.5 * np.log(2 * q / me))
               - (31.0 / 18.0 + lz / 12.0) * beta - 11.0 / 12.0 * z + z**2 / 24.0)
    f_plus = (c * ((1 - z) ** 2 * (2 * log_end - l1z - lz / 2 - 2.0 / 3.0) - (z**2 * lz + 1 - z) / 2)
              - (1 - z) ** 2 / 2 * (l1z**2 + beta * (_L(1 - z) - lz * l1z))
              + l1z * (z**2 / 2 * lz + (1 - z) / 3 * (2 * z - 0.5))
              - z**2 / 2 * _L(1 - z) - z * (1 - 2 * z) / 3 * lz - z * (1 - z) / 6
              - beta / 12 * (lz + (1 - z) * (115 - 109 * z) / 6))
    f_pm = c * 2 * log_end
    return f_minus, f_plus, f_pm


def es_differential(q, T, flavour, constants):
    """dsigma/dT (cm^2 / MeV per electron) at neutrino energy q and recoil T (MeV, broadcast)."""
    me = constants["m_e_MeV"]
    G = constants["G_F_GeV-2"] * 1e-6
    hbarc2 = (constants["hbarc_MeV_fm"] * 1e-13) ** 2
    q, T = np.broadcast_arrays(np.asarray(q, float), np.asarray(T, float))
    t_max = 2 * q**2 / (me + 2 * q)
    inside = (T > 0) & (T < t_max)
    out = np.zeros(q.shape)
    q, T = q[inside], T[inside]
    gl, gr = couplings(T, flavour, me)
    fm, fp, fpm = qed(q, T, me)
    z = T / q
    a = ALPHA / np.pi
    value = gl**2 * (1 + a * fm) + gr**2 * ((1 - z) ** 2 + a * fp) - gr * gl * me / q * z * (1 + a * fpm)
    out[inside] = np.maximum(value, 0.0) * 2 * G**2 * me / np.pi * hbarc2
    return out


_NODES, _WEIGHTS = np.polynomial.legendre.leggauss(48)


def es_above(q, flavour, constants, fractions):
    """sigma(q; T > u T_max) for each u in ``fractions`` (cm^2 per electron), [len(q), len(fractions)].
    Integrated in y = ln((T_max - T)/T_max) pieces to resolve the end-point logarithm."""
    me = constants["m_e_MeV"]
    q = np.atleast_1d(np.asarray(q, float))
    u = np.asarray(fractions, float)
    t_max = 2 * q**2 / (me + 2 * q)
    # cumulative integral from the end point down: on [u_k, u_{k+1}] with Gauss-Legendre in s = log10(1 - u)
    nodes = np.unique(np.concatenate([u, 1.0 - np.geomspace(1e-9, 1.0, 120)[:-1], [0.0]]))
    nodes = nodes[(nodes >= 0) & (nodes < 1)]
    pieces = np.zeros((len(q), len(nodes)))
    for k in range(len(nodes)):
        lo, hi = nodes[k], (nodes[k + 1] if k + 1 < len(nodes) else 1.0 - 1e-12)
        s_lo, s_hi = np.log(1 - lo), np.log(1 - hi)
        s = 0.5 * (s_hi - s_lo) * _NODES + 0.5 * (s_hi + s_lo)
        w = 0.5 * (s_lo - s_hi) * _WEIGHTS
        v = 1 - np.exp(s)                        # u at the nodes; du = (1 - u) ds
        T = t_max[:, None] * v[None, :]
        d = es_differential(q[:, None], T, flavour, constants)
        pieces[:, k] = (d * (1 - v)[None, :] * w[None, :]).sum(axis=1) * t_max
    tail = np.cumsum(pieces[:, ::-1], axis=1)[:, ::-1]     # sigma(T > nodes_k T_max)
    return np.stack([np.where(u < 1.0, np.interp(u, nodes, row), 0.0) for row in tail])


TABLE_ENERGY = np.geomspace(0.05, 30.0, 70)
TABLE_FRACTION = np.unique(np.concatenate([np.linspace(0.0, 0.9, 46), 1.0 - np.geomspace(1e-4, 0.1, 25), [1.0]]))


def ratio_table(constants):
    """{energy, fraction, nue, numu}: sigma_BKS(E; T > u T_max) / sigma_tree(E; T > u T_max), the engine's
    table (at u = 1, where both vanish, the last ratio before it)."""
    from .xsec import es_above as tree_above

    me = constants["m_e_MeV"]
    t_max = 2 * TABLE_ENERGY**2 / (me + 2 * TABLE_ENERGY)
    out = {"energy": TABLE_ENERGY.tolist(), "fraction": TABLE_FRACTION.tolist(),
           "source": "Bahcall, Kamionkowski, Sirlin, PRD 51, 6146 (1995), arXiv:astro-ph/9502003"}
    for flavour in ("nue", "numu"):
        bks = es_above(TABLE_ENERGY, flavour, constants, TABLE_FRACTION[:-1])
        tree = np.stack([tree_above(TABLE_ENERGY, flavour, constants, u * t_max) for u in TABLE_FRACTION[:-1]], axis=1)
        ratio = bks / tree
        out[flavour] = np.round(np.hstack([ratio, ratio[:, -1:]]), 7).tolist()
    return out
