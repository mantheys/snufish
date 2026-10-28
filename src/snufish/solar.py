"""Solar electron density profiles and production distributions of a B2
spec (``solar_models`` and ``production`` blocks)."""

import functools

import numpy as np

from .paths import repo_root


@functools.lru_cache(maxsize=8)
def _table(path):
    return np.loadtxt(path, comments="#")


def table(spec, relative_path):
    return _table(str(repo_root() / relative_path))


def electron_density(spec, model_name, r):
    """n_e in N_A / cm^3 at r / R_sun (array-friendly), as the spec defines it."""
    model = spec["solar_models"][model_name]
    r = np.asarray(r, dtype=float)
    if "n0" in model:
        return model["n0"] * np.exp(-model["scale"] * r)
    data = table(spec, model["table"])
    radius, log_ne = data[:, model["radius_column"]], data[:, model["log10_ne_column"]]
    tail = model["tail"]
    inside = np.interp(r, radius, log_ne)  # constant below the first point
    outside = tail["intercept"] + tail["slope"] * r
    return 10.0 ** np.where(r > radius[-1], outside, inside)


def production_weights(spec, radius_grid):
    """{component: weights over ``radius_grid``}: the fraction of each flux
    produced in the cell around each grid radius (cells bounded by midpoints;
    the last cell extends to the end of the table). Weights sum to 1."""
    production = spec["production"]
    data = table(spec, production["table"])
    r = data[:, 0]
    grid = np.asarray(radius_grid, dtype=float)
    edges = np.concatenate([[-np.inf], 0.5 * (grid[1:] + grid[:-1]), [np.inf]])
    cell = np.digitize(r, edges) - 1
    weights = {}
    for name, column in production["components"].items():
        f = data[:, column] * np.gradient(r)
        w = np.bincount(cell, weights=f, minlength=len(grid))[: len(grid)]
        weights[name] = w / w.sum()
    return weights
