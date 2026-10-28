"""Standard solar models: the B1 registry (benchmarks/B1_ssm/models.yaml)
and analytic profiles defined in a B2 spec (``solar_models`` block)."""

import functools

import numpy as np
import yaml

from .paths import repo_root
from .spec import load_spec

COMPONENTS = ("pp", "pep", "hep", "Be7", "B8", "N13", "O15", "F17")


@functools.lru_cache(maxsize=4)
def _registry(root):
    spec = load_spec("B1_ssm", root=root)
    with (repo_root(root) / spec["models_file"]).open() as handle:
        return yaml.safe_load(handle)


def models():
    """{name: model entry} of every B1 solar model."""
    return _registry(str(repo_root()))


@functools.lru_cache(maxsize=32)
def _table(path):
    return np.loadtxt(path)


def table(name):
    """Array [r, log10 n_e, production densities...] of a B1 model."""
    return _table(str(repo_root() / models()[name]["table"]))


def _analytic(spec, name):
    if spec is None:
        return None
    return spec.data.get("solar_models", {}).get(name)


def electron_density(name, r, spec=None):
    """n_e in N_A / cm^3 at r / R_sun (array-friendly): a B1 model, or an
    analytic profile of ``spec`` (a B2 spec)."""
    r = np.asarray(r, dtype=float)
    analytic = _analytic(spec, name)
    if analytic is not None:
        return analytic["n0"] * np.exp(-analytic["scale"] * r)
    data, tail = table(name), models()[name]["tail"]
    radius, log_ne = data[:, 0], data[:, 1]
    inside = np.interp(r, radius, log_ne)  # constant below the first point
    if tail is None:
        return 10.0 ** inside
    outside = tail["intercept"] + tail["slope"] * r
    return 10.0 ** np.where(r > radius[-1], outside, inside)


def production_weights(name, radius_grid, spec=None):
    """{component: weights over ``radius_grid``}: the fraction of each flux
    produced in the cell around each grid radius (cells bounded by midpoints;
    the last cell extends to the end of the table). Weights sum to 1.
    Analytic profiles use the production of their ``production_from`` model."""
    analytic = _analytic(spec, name)
    if analytic is not None:
        name = analytic["production_from"]
    data = table(name)
    r = data[:, 0]
    grid = np.asarray(radius_grid, dtype=float)
    edges = np.concatenate([[-np.inf], 0.5 * (grid[1:] + grid[:-1]), [np.inf]])
    cell = np.digitize(r, edges) - 1
    weights = {}
    for k, component in enumerate(COMPONENTS):
        f = data[:, 2 + k] * np.gradient(r)
        w = np.bincount(cell, weights=f, minlength=len(grid))[: len(grid)]
        weights[component] = w / w.sum()
    return weights


def fluxes(name):
    """{component: flux in cm^-2 s^-1} of a B1 model."""
    return models()[name]["fluxes"]
