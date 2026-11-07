"""``prem_crust1_3d``: the CRUST1.0 crust along every night chord, PREM below it.

``prem_crust1`` (:mod:`snufish.crust`) puts the CRUST1.0 column under the detector on top of PREM everywhere:
radial, so a chord's density depends on its nadir angle only. Here the crust is the one the chord actually
crosses: at every point of the chord within the crust, the layer of the 1 x 1 degree CRUST1.0 cell the point
lies under (reference/earth/crust1_global.npz, each cell's surface put at the Earth's radius as prem_crust1 does
under the detector); under the local Moho, PREM (its lid continued up to the Moho, as in prem_crust1). Ye 0.494
in the crust, as PREM's crust in the B3 spec. Near the detector the chord crosses the detector's cell (steep
chords) or its neighbours (shallow ones); on the far side, the crust where the chord enters the Earth.

The directions are the Sun's over a year at the site's latitude and longitude (:func:`night_directions`). The
night exposure in nadir angle is kept B3's (W of Lisi & Montanino, integrated over each cell of the 1001-point
cos-nadir grid), so prem_crust1_3d differs from the radial models by the Earth only; the time sampling gives,
within each cell, the azimuths and so the cells of CRUST1.0 the chords cross.

Each cos-nadir cell is solved once, with the crust of its chords averaged at equal distance from the detector
(near half) and from the entry point (far half): P(nu_i -> nu_e) is linear in a small change of density (first
order in the matter potential over the oscillation frequency), so the average of P over the cell's chords is P
along the average chord, to second order (``scripts/earth3d_literature.py --part average``). The chord is cut into pieces of near-constant
density (:func:`pieces`) and solved with NuFast-Earth's single-trajectory mode (the B3 driver's
``trajectories:`` model), validated against the B3 reference propagator (tests/test_earth3d.py).
"""

import functools
import hashlib
import math
import os
import tempfile
from pathlib import Path

import numpy as np

from .crust import CRUST_YE, columns
from .paths import build_dir, repo_root
from .spec import load_spec

MODEL = "prem_crust1_3d"
CRUST_ZONE_KM = 82.0      # deeper than any CRUST1.0 Moho (80 km)
SAMPLE_KM = 1.0           # resolution of the averaged crust along the chord
STEP_MINUTES = 2.0        # time step of the Sun over the year
YEAR_START = 9495.5       # days from J2000 (2000-01-01 12:00 UT): 2026-01-01 00:00 UT
PIECE_KM = 50.0           # longest piece of a chord
PIECE_TOLERANCE = 0.05    # g/cm^3 x Ye: a piece ends where the density has changed by this much


@functools.lru_cache(maxsize=1)
def crust_grid():
    """(boundaries km [180, 360, 9]: elevation of each layer's top and of the Moho; densities g/cm^3 [180, 360, 9])."""
    with np.load(repo_root() / "reference" / "earth" / "crust1_global.npz") as data:
        return data["bounds_10m"] / 100.0, data["density_cg"] / 100.0


def _cells(lat_deg, lon_deg):
    i = np.clip(np.floor(90.0 - lat_deg).astype(int), 0, 179)
    j = np.floor(lon_deg + 180.0).astype(int) % 360
    return i, j


def crust_density(lat_deg, lon_deg, depth_km):
    """Density (g/cm^3) of CRUST1.0 at a depth below the cell's surface; NaN under the cell's Moho."""
    bounds, density = crust_grid()
    i, j = _cells(np.asarray(lat_deg), np.asarray(lon_deg))
    b, rho = bounds[i, j], density[i, j]          # [..., 9]
    below = b[..., :1] - b[..., 1:]               # depth of the bottom of each layer (the 9th: the Moho)
    layer = np.sum(np.asarray(depth_km)[..., None] >= below, axis=-1)  # 0..8; 8: under the Moho
    out = np.take_along_axis(rho, np.minimum(layer, 7)[..., None], axis=-1)[..., 0]
    return np.where(layer < 8, out, np.nan)


@functools.lru_cache(maxsize=1)
def _radius():
    return float(load_spec("B3_earth")["earth"]["radius_km"])


@functools.lru_cache(maxsize=1)
def _mantle_regions():
    """PREM to its lid, the lid continued to the surface: (outer radii km, Ye x coefficients [region, 4])."""
    regions = load_spec("B3_earth")["earth_models"]["prem_full"]["regions"]
    lid = next(k for k, r in enumerate(regions) if r["outer_radius_km"] > 6300)
    outer = np.array([r["outer_radius_km"] for r in regions[: lid + 1]])
    outer[-1] = _radius()
    coefficients = np.zeros((lid + 1, 4))
    for k, r in enumerate(regions[: lid + 1]):
        coefficients[k, : len(r["coefficients"])] = r["ye"] * np.array(r["coefficients"])
    return outer, coefficients


def mantle_rhoye(r_km):
    """rho x Ye (g/cm^3) of PREM under the crust at radius r (lid continued up)."""
    outer, coefficients = _mantle_regions()
    r_km = np.asarray(r_km, dtype=float)
    c = coefficients[np.minimum(np.searchsorted(outer, r_km), len(outer) - 1)]
    x = r_km / _radius()
    return c[..., 0] + x * (c[..., 1] + x * (c[..., 2] + x * c[..., 3]))


def _unit(lat_deg, lon_deg):
    lat, lon = np.radians(lat_deg), np.radians(lon_deg)
    return np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=-1)


def _lat_lon(points):
    r = np.linalg.norm(points, axis=-1)
    return np.degrees(np.arcsin(np.clip(points[..., 2] / r, -1, 1))), np.degrees(np.arctan2(points[..., 1], points[..., 0])), r


def sun_directions(step_minutes=STEP_MINUTES, start=YEAR_START):
    """Unit vectors to the Sun in the Earth-fixed frame (x: 0 deg E on the equator, z: north), every
    ``step_minutes`` over one year from ``start`` (days from J2000). Low-precision solar coordinates of the
    Astronomical Almanac (0.01 deg) and the Earth rotation angle for Greenwich (UT1 = UT)."""
    t = start + np.arange(0.0, 365.25, step_minutes / 1440.0)
    mean_anomaly = np.radians(357.5291 + 0.98560028 * t)
    mean_longitude = np.radians(280.4665 + 0.98564736 * t)
    longitude = mean_longitude + np.radians(1.915 * np.sin(mean_anomaly) + 0.020 * np.sin(2 * mean_anomaly))
    obliquity = np.radians(23.439 - 4e-7 * t)
    ra = np.arctan2(np.cos(obliquity) * np.sin(longitude), np.cos(longitude))
    dec = np.arcsin(np.sin(obliquity) * np.sin(longitude))
    rotation = 2 * np.pi * ((0.7790572732640 + 1.00273781191135448 * t) % 1.0)
    return _unit(np.degrees(dec), np.degrees(ra - rotation))


def site_vector(site):
    column = columns()[site]
    return _unit(column["latitude_deg"], column["longitude_deg"])


def night_directions(site, **kwargs):
    """(unit vectors to the Sun when it is below the site's horizon, their cos nadir)."""
    s, d = sun_directions(**kwargs), site_vector(site)
    cos_nadir = -(s @ d)
    night = cos_nadir > 0
    return s[night], cos_nadir[night]


def _end_profiles(start, direction, length, radius, sample_km):
    """rho x Ye minus PREM's (mantle_rhoye) along the first half of chords from ``start`` (points on the
    surface, [n, 3] in km) along ``direction`` (unit vectors), at the centres of ``sample_km`` samples up to the
    crust zone or half the chord: (sample index [m], chord index [m], deviation [m])."""
    cos_out = -np.einsum("ni,ni->n", start / radius, direction)   # cos of the angle to the inward vertical
    # distance from the end at which the chord is CRUST_ZONE_KM deep (or never: half the chord)
    reach = radius * cos_out - np.sqrt(np.clip((radius * cos_out) ** 2 - (2 * radius - CRUST_ZONE_KM) * CRUST_ZONE_KM, 0, None))
    reach = np.where((radius * cos_out) ** 2 > (2 * radius - CRUST_ZONE_KM) * CRUST_ZONE_KM, reach, length / 2)
    n = np.ceil(np.minimum(reach, length / 2) / sample_km).astype(int)
    chord = np.repeat(np.arange(len(n)), n)
    k = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
    u = (k + 0.5) * sample_km
    points = start[chord] + u[:, None] * direction[chord]
    lat, lon, r = _lat_lon(points)
    crust = crust_density(lat, lon, radius - r)
    deviation = np.where(np.isnan(crust), 0.0, CRUST_YE * np.nan_to_num(crust) - mantle_rhoye(r))
    keep = (u <= length[chord] / 2) & (deviation != 0)
    return k[keep], chord[keep], deviation[keep]


@functools.lru_cache(maxsize=1)
def _cos_grid():
    return load_spec("B3_earth").axis("cos_nadir", "exposure")


def cos_grid():
    return _cos_grid().copy()


@functools.lru_cache(maxsize=None)
def averaged_crust(site, sample_km=SAMPLE_KM, step_minutes=STEP_MINUTES, chunk=4000):
    """(near [cells, samples], far [cells, samples], counts [cells]): the crust's rho x Ye minus PREM's, averaged
    over the night chords of each cell of the B3 cos-nadir grid, at the centres of ``sample_km`` samples from the
    detector (near) and from the entry point (far)."""
    radius = _radius()
    grid = cos_grid()
    step = grid[1] - grid[0]
    s, c = night_directions(site, step_minutes=step_minutes)
    cell = np.clip(np.rint((c - grid[0]) / step).astype(int), 0, len(grid) - 1)
    counts = np.bincount(cell, minlength=len(grid))
    width = int(math.ceil(radius / sample_km)) + 1
    near, far = np.zeros(len(grid) * width), np.zeros(len(grid) * width)
    detector = site_vector(site) * radius
    for a in range(0, len(s), chunk):
        sl = slice(a, a + chunk)
        length = 2 * radius * c[sl]
        entry = detector + length[:, None] * s[sl]
        for target, start, direction in ((near, np.broadcast_to(detector, (len(length), 3)), s[sl]),
                                         (far, entry, -s[sl])):
            k, chord, deviation = _end_profiles(start, direction, length, radius, sample_km)
            np.add.at(target, cell[sl][chord] * width + k, deviation)
    norm = np.maximum(counts, 1)[:, None]
    return near.reshape(len(grid), width) / norm, far.reshape(len(grid), width) / norm, counts


def _fill_empty(near, far, counts):
    """Cells no time sample fell in (W is zero there, or nearly): the nearest sampled cell's crust."""
    sampled = np.flatnonzero(counts)
    if len(sampled) == 0:
        return near, far
    nearest = sampled[np.abs(np.arange(len(counts))[:, None] - sampled[None, :]).argmin(axis=1)]
    return near[nearest], far[nearest]


def chord_profile(cos_nadir, near, far, sample_km=SAMPLE_KM):
    """(sample lengths km, rho x Ye) along one chord, from the entry point to the detector, at ``sample_km``
    resolution: PREM under the crust plus the averaged crust of the near and far halves."""
    radius = _radius()
    length = 2 * radius * cos_nadir
    if length <= 0:
        return np.zeros(0), np.zeros(0)
    n = max(1, int(math.ceil(length / sample_km)))
    h = length / n
    x = (np.arange(n) + 0.5) * h                       # from the entry point
    r = np.sqrt(radius**2 - x * (length - x))          # |entry + x s|, entry and detector on the surface
    rhoye = mantle_rhoye(r)
    from_detector = length - x
    k_far, k_near = np.minimum((x / sample_km).astype(int), far.size - 1), np.minimum((from_detector / sample_km).astype(int), near.size - 1)
    rhoye += np.where(from_detector <= length / 2, near[k_near], far[k_far])
    return np.full(n, h), rhoye


def pieces(lengths, rhoye, max_km=PIECE_KM, tolerance=PIECE_TOLERANCE):
    """Merge samples into pieces of their mean density: a piece ends once the density has varied by
    ``tolerance`` (a crust layer, a PREM discontinuity) or after ``max_km``."""
    if len(lengths) == 0:
        return lengths, rhoye
    variation = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(rhoye)))])
    distance = np.cumsum(lengths) - lengths
    piece = np.floor(variation / tolerance).astype(int) + np.floor(distance / max_km).astype(int)
    _, piece = np.unique(piece, return_inverse=True)
    total = np.bincount(piece, weights=lengths)
    return total, np.bincount(piece, weights=lengths * rhoye) / total


def write_trajectories(chords, name, directory=None):
    """A file of the driver's ``trajectories:`` format; ``chords``: [(cos nadir, lengths, rho x Ye)]."""
    path = Path(directory or tempfile.gettempdir()) / f"snufish_{name}.trajectories"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(f"{c:.6f} {len(lengths)}\n" + "".join(f"{a:.6f} {b:.8f}\n" for a, b in zip(lengths, rhoye))
                   for c, lengths, rhoye in chords)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=path.name, delete=False) as handle:
        handle.write(text)  # whole files only: several processes may build the same site
    os.replace(handle.name, path)
    return str(path)


TRAJECTORY_FILES = {}  # site: file, made in a worker (export.export_app)
# bump when the construction changes: the chords are cached in build/earth3d under a key of this and the settings
CHORDS_VERSION = 1


@functools.lru_cache(maxsize=None)
def trajectories_file(site, max_km=PIECE_KM, tolerance=PIECE_TOLERANCE):
    """The B3 driver's trajectories for ``site``: one chord per cell of the B3 cos-nadir grid (cached in
    build/earth3d)."""
    if (max_km, tolerance) == (PIECE_KM, PIECE_TOLERANCE) and site in TRAJECTORY_FILES:
        return TRAJECTORY_FILES[site]
    column = columns()[site]
    with np.load(repo_root() / "reference" / "earth" / "crust1_global.npz") as data:
        digest = str(data["sha256"])[:12]
    key = hashlib.sha256(repr((CHORDS_VERSION, digest, column["latitude_deg"], column["longitude_deg"], SAMPLE_KM,
                               STEP_MINUTES, YEAR_START, CRUST_ZONE_KM, max_km, tolerance)).encode()).hexdigest()[:16]
    directory = build_dir() / "earth3d"
    path = directory / f"snufish_{MODEL}_{site}_{key}.trajectories"
    if path.exists():
        return str(path)
    near, far = _fill_empty(*averaged_crust(site))
    chords = [(c, *pieces(*chord_profile(c, near[k], far[k]), max_km=max_km, tolerance=tolerance))
              for k, c in enumerate(cos_grid())]
    return write_trajectories(chords, f"{MODEL}_{site}_{key}", directory)


def direction_chords(site, cos_lo, cos_hi, limit=None, at=None, **kwargs):
    """The single chords (not averaged) of the night directions with cos nadir in [cos_lo, cos_hi), turned to
    cos nadir ``at`` if given (same azimuth): for checking the average (scripts/earth3d_literature.py). [(cos nadir, lengths, rho x Ye)]."""
    radius = _radius()
    s, c = night_directions(site, **kwargs)
    sel = np.flatnonzero((c >= cos_lo) & (c < cos_hi))[:limit]
    d = site_vector(site)
    if at is not None:
        horizontal = s[sel] + c[sel, None] * d
        horizontal /= np.linalg.norm(horizontal, axis=1, keepdims=True)
        s, c = s.copy(), c.copy()
        s[sel], c[sel] = -at * d + math.sqrt(1 - at**2) * horizontal, at
    detector = d * radius
    out = []
    for n in sel:
        length = 2 * radius * c[n]
        m = max(1, int(math.ceil(length / SAMPLE_KM)))
        x = (np.arange(m) + 0.5) * length / m
        entry = detector + length * s[n]
        points = entry - x[:, None] * s[n]
        lat, lon, r = _lat_lon(points)
        crust = crust_density(lat, lon, radius - r)
        rhoye = np.where(np.isnan(crust), mantle_rhoye(r), CRUST_YE * np.nan_to_num(crust))
        out.append((c[n], *pieces(np.full(m, length / m), rhoye)))
    return out
