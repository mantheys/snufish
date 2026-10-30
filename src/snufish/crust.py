"""Site-dependent Earth models: PREM under the Moho, the local CRUST1.0 column above it.

``prem_crust1`` replaces PREM's average crust and ocean (the top 24.4 km: 3 km of water, then 2.6 and
2.9 g/cm^3) with the crust of the 1 x 1 degree CRUST1.0 cell of the detector
(reference/earth/crust1_sites.yaml), from the surface down to the local Moho, and PREM from there to
the centre. The model is still radial: the column under the detector stands for the crust everywhere,
which is what matters most for the day-night asymmetry (the density the neutrinos cross last); the crust
where a chord enters the Earth, a 3D effect, is not included.
"""

import functools
import tempfile
from pathlib import Path

import yaml

from .paths import repo_root
from .spec import load_spec

SITE_MODELS = ("prem_crust1",)
CRUST_YE = 0.494  # as PREM's crust in the B3 spec


@functools.lru_cache(maxsize=1)
def columns():
    path = repo_root() / "reference" / "earth" / "crust1_sites.yaml"
    if not path.exists():
        return {}
    with path.open() as handle:
        return yaml.safe_load(handle)["sites"]


def available():
    """The site-dependent models that can be built (the CRUST1.0 columns are there)."""
    return list(SITE_MODELS) if columns() else []


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


@functools.lru_cache(maxsize=None)
def regions_file(earth_model, site):
    """A file of the regions in the NuFast-Earth driver's `regions:` format (one per line: outer radius, Ye,
    coefficients)."""
    path = Path(tempfile.gettempdir()) / f"snufish_{earth_model}_{site}.regions"
    path.write_text("".join(f"{r['outer_radius_km']} {r['ye']} {' '.join(map(str, r['coefficients']))}\n"
                            for r in regions(earth_model, site)))
    return str(path)
