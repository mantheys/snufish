"""Annual solar exposure of a detector against the nadir angle.

W(eta; latitude) from Lisi & Montanino, hep-ph/9702343 (table II), as
implemented in NuFast-Earth (src/Solar.cpp): the fraction of the
night the Sun spends at nadir angle eta, per radian, for a detector at
the given latitude (normalised to 1 over the night, eta < pi/2). W has
integrable log singularities at
eta = |latitude - i| and latitude + i, so averages over a nadir grid use the
exposure integrated over each grid cell (`cell_weights`), not W sampled at
the grid points.
"""

import functools

import numpy as np

INCLINATION = 0.4091  # Earth's axial tilt in radians (hep-ph/9702343, after eq. C4)


def _comp_ellint_1(k):
    """Complete elliptic integral of the first kind K(k), modulus k (AGM)."""
    a, b = np.ones_like(k), np.sqrt(1.0 - k**2)
    for _ in range(64):
        a, b = 0.5 * (a + b), np.sqrt(a * b)
        if np.all(np.abs(a - b) < 1e-15):
            break
    return np.pi / (2.0 * a)


def solar_weight(eta, latitude):
    """W(eta) per radian (eta, latitude in radians; array-friendly). Zero
    above the horizon (eta > pi/2) and where the Sun never reaches."""
    eta = np.atleast_1d(np.asarray(eta, dtype=float))
    i, lat = INCLINATION, abs(latitude)
    z2 = np.sin(i) * np.cos(lat) * np.sin(eta)
    y2 = (np.sin(0.5 * (i + lat + eta)) * np.sin(0.5 * (i - lat + eta))
          * np.cos(0.5 * (i + lat - eta)) * np.cos(0.5 * (i - lat - eta)))
    z, y = np.sqrt(np.clip(z2, 0, None)), np.sqrt(np.clip(y2, 0, None))

    if lat < i:
        y_over_z = (i - lat < eta) & (eta < i + lat)
    elif lat < 0.5 * np.pi - i:
        y_over_z = eta <= lat + i
    else:
        y_over_z = eta <= np.pi - lat - i
    num, den = np.where(y_over_z, y, z), np.where(y_over_z, z, y)

    reachable = (eta >= lat - i) & (eta <= 0.5 * np.pi) & (den > 0) & (num < den)
    out = np.zeros_like(eta)
    k = num[reachable] / den[reachable]
    out[reachable] = 2 * np.sin(eta[reachable]) * _comp_ellint_1(k) / (np.pi**2 * den[reachable])
    return out


@functools.lru_cache(maxsize=32)
def _cumulative(latitude, n=20000):
    """(eta, C(eta)): the night exposure below each eta on a mesh over
    [0, pi/2], split at the singular points and graded towards them."""
    i, lat = INCLINATION, abs(latitude)
    cuts = sorted({0.0, 0.5 * np.pi, *[c for c in (lat - i, lat + i, np.pi - lat - i) if 0 < c < 0.5 * np.pi]})
    nodes, weights = np.polynomial.legendre.leggauss(16)
    mesh = [np.array([0.0])]
    for a, b in zip(cuts[:-1], cuts[1:]):
        mesh.append(a + (b - a) * 0.5 * (1 - np.cos(np.linspace(0, np.pi, n // len(cuts))))[1:])
    eta = np.concatenate(mesh)
    lo, hi = eta[:-1], eta[1:]
    x = 0.5 * (hi - lo)[:, None] * nodes + 0.5 * (hi + lo)[:, None]
    pieces = 0.5 * (hi - lo) * (solar_weight(x.ravel(), latitude).reshape(x.shape) @ weights)
    return eta, np.concatenate([[0.0], np.cumsum(pieces)])


def night_exposure(latitude, eta_lo, eta_hi):
    """Exposure between two nadir angles (radians)."""
    eta, cumulative = _cumulative(float(latitude))
    return float(np.diff(np.interp([eta_lo, eta_hi], eta, cumulative))[0])


def cell_weights(cos_nadir, latitude):
    """Night exposure of each point of an ascending cos-nadir grid, from cells
    bounded by the midpoints between grid points (first and last cells half
    width). The weights sum to 1 (W is normalised over the night)."""
    cos_nadir = np.asarray(cos_nadir, dtype=float)
    edges = np.concatenate([[cos_nadir[0]], 0.5 * (cos_nadir[1:] + cos_nadir[:-1]), [cos_nadir[-1]]])
    eta, cumulative = _cumulative(float(latitude))
    at_edges = np.interp(np.arccos(np.clip(edges, -1, 1)), eta, cumulative)
    return at_edges[:-1] - at_edges[1:]
