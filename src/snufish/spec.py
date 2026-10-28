"""Benchmark specifications (``benchmarks/<id>/spec.yaml``)."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from .paths import benchmarks_dir


@dataclass
class Spec:
    id: str
    version: str
    data: dict
    path: Path

    def __getitem__(self, key):
        return self.data[key]

    def axis(self, name, grid=None):
        """Grid points of one axis of ``grid`` (default: the first grid),
        rounded to the step's decimals so that contributions written as text
        compare equal."""
        axis = self.data["grids"][grid or self.grids[0]][name]
        n = int(round((axis["stop"] - axis["start"]) / axis["step"])) + 1
        decimals = max(0, -int(np.floor(np.log10(axis["step"]))) + 1)
        return np.round(np.linspace(axis["start"], axis["stop"], n), decimals)

    @property
    def grids(self):
        return list(self.data["grids"])

    @property
    def grid_names(self):
        """Axis names, shared by every grid."""
        return list(self.data["grids"][self.grids[0]])

    @property
    def quantities(self):
        return list(self.data["quantities"])

    @property
    def variants(self):
        return self.data["variants"]


def _numeric_strings(data, where=""):
    """Paths of string values that look like numbers: YAML 1.1 reads 1e23
    (no exponent sign) as a string."""
    if isinstance(data, dict):
        return [p for key, value in data.items() for p in _numeric_strings(value, f"{where}.{key}")]
    if isinstance(data, list):
        return [p for i, value in enumerate(data) for p in _numeric_strings(value, f"{where}[{i}]")]
    if isinstance(data, str):
        try:
            float(data)
        except ValueError:
            return []
        return [where.lstrip(".")]
    return []


def load_spec(benchmark, root=None):
    path = benchmarks_dir(root) / benchmark / "spec.yaml"
    with path.open() as handle:
        data = yaml.safe_load(handle)
    suspicious = [p for p in _numeric_strings(data) if p not in ("version",)]
    if suspicious:
        raise ValueError(f"{path}: numbers read as strings (write 1e+23, not 1e23): {suspicious}")
    return Spec(id=data["id"], version=data["version"], data=data, path=path)


def available_benchmarks(root=None):
    return sorted(p.parent.name for p in benchmarks_dir(root).glob("*/spec.yaml"))


def pmns(osc):
    """PMNS matrix (PDG parametrisation) from a spec's ``oscillation`` block."""
    s12, s13, s23 = (np.sqrt(osc[f"sin2_theta{ij}"]) for ij in ("12", "13", "23"))
    c12, c13, c23 = (np.sqrt(1 - s**2) for s in (s12, s13, s23))
    phase = np.exp(1j * np.radians(osc["delta_cp_deg"]))
    return np.array([
        [c12 * c13, s12 * c13, s13 / phase],
        [-s12 * c23 - c12 * s23 * s13 * phase, c12 * c23 - s12 * s23 * s13 * phase, s23 * c13],
        [s12 * s23 - c12 * c23 * s13 * phase, -c12 * s23 - s12 * c23 * s13 * phase, c23 * c13],
    ])
