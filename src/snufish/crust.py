"""Site-dependent Earth models: PREM under the Moho, the local CRUST1.0 column above it.

``prem_crust1`` replaces PREM's average crust and ocean (the top 24.4 km: 3 km of water, then 2.6 and
2.9 g/cm^3) with the crust of the 1 x 1 degree CRUST1.0 cell of the detector
(reference/earth/crust1_sites.yaml), from the surface down to the local Moho, and PREM from there to
the centre. The model is still radial: the column under the detector stands for the crust everywhere,
which is what matters most for the day-night asymmetry (the density the neutrinos cross last); the crust
where a chord enters the Earth, a 3D effect, is not included.
"""

import functools
import hashlib
import math
import os
import tempfile
from pathlib import Path

import yaml

from .paths import repo_root
from .spec import load_spec

SITE_MODELS = ("prem_crust1", "prem_crust1_3d")  # the second: earth3d.py
CRUST_YE = 0.494  # as PREM's crust in the B3 spec


@functools.lru_cache(maxsize=1)
def columns():
    path = repo_root() / "reference" / "earth" / "crust1_sites.yaml"
    if not path.exists():
        return {}
    with path.open() as handle:
        return yaml.safe_load(handle)["sites"]


def available():
    """The site-dependent models that can be built (the CRUST1.0 columns, and for prem_crust1_3d the whole grid,
    are there)."""
    if not columns():
        return []
    grid = (repo_root() / "reference" / "earth" / "crust1_global.npz").exists()
    return [m for m in SITE_MODELS if m == "prem_crust1" or grid]


def regions(earth_model, site):
    """B3-style regions (outer_radius_km, coefficients, ye), innermost first, of ``earth_model`` at ``site``."""
    if earth_model != "prem_crust1":
        raise KeyError(earth_model)
    spec = load_spec("B3_earth")
    radius = spec["earth"]["radius_km"]
    column = columns()[site]
    moho = radius - column["moho_depth_km"]
    out = []
    for region in spec["earth_models"]["prem_full"]["regions"]:
        inner = out[-1]["outer_radius_km"] if out else 0.0
        if inner >= moho:
            break
        out.append(dict(region, outer_radius_km=min(region["outer_radius_km"], moho)))
    top = radius
    shells = []
    for layer in column["layers"]:  # top down
        shells.append(dict(outer_radius_km=round(top, 6), coefficients=[layer["density"]], ye=CRUST_YE))
        top -= layer["thickness_km"]
    return out + shells[::-1]


def split(regions_list, step_km):
    """The regions with every non-constant one cut into shells of at most ``step_km`` (same polynomial):
    NuFast-Earth takes each crossing's mean density, which converges to the continuous profile as the
    shells thin (docs/crosschecks.md, NuFast-Earth on continuous density)."""
    out, inner = [], 0.0
    for region in regions_list:
        outer = region["outer_radius_km"]
        if len(region["coefficients"]) > 1:
            n = max(1, math.ceil((outer - inner) / step_km))
            out += [dict(region, outer_radius_km=round(inner + (outer - inner) * (k + 1) / n, 6)) for k in range(n)]
        else:
            out.append(region)
        inner = outer
    return out


def write_regions(regions_list, name):
    """A file of the regions in the NuFast-Earth driver's `regions:` format (one per line: outer radius, Ye,
    coefficients). Named by its content and written whole (a unique temporary file renamed into place): the
    export's workers, and other checkouts on the same machine, write the same models at once."""
    text = "".join(f"{r['outer_radius_km']} {r['ye']} {' '.join(map(str, r['coefficients']))}\n" for r in regions_list)
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    path = Path(tempfile.gettempdir()) / f"snufish_{name}_{digest}.regions"
    if not path.exists():
        with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=path.name, delete=False) as handle:
            handle.write(text)
        os.replace(handle.name, path)
    return str(path)


@functools.lru_cache(maxsize=None)
def regions_file(earth_model, site):
    return write_regions(regions(earth_model, site), f"{earth_model}_{site}")
