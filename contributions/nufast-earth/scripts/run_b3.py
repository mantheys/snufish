"""NuFast-Earth contribution to SNUfish B3 (all four variants).

    make && python run_b3.py        # from this directory, SNUfish installed

Runs b3_driver on the spec's grid and writes
contributions/nufast-earth/B3_earth/<version>/.
"""

import datetime
import subprocess
from pathlib import Path

import numpy as np

from snufish.contribution import write_contribution
from snufish.paths import contributions_dir
from snufish.spec import load_spec

HERE = Path(__file__).resolve().parent


def _git(*args):
    return subprocess.run(["git", "-C", str(HERE / "NuFast-Earth"), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


COMMIT = _git("rev-parse", "--short", "HEAD")
VERSION = _git("describe", "--tags").removeprefix("v")  # e.g. 1.2.0-3-g327586d
NATIVE = "PREM_NDiscontinuityLayer(2, 10, 10, 5): piecewise-constant PREM, 27 shells (NuFast-Earth examples)"


def run_variant(spec, variant, grid_name):
    osc, grid = spec["oscillation"], spec["grids"][grid_name]
    argv = [variant, *(str(osc[k]) for k in ("sin2_theta12", "sin2_theta13", "sin2_theta23", "delta_cp_deg",
                                             "dm2_21_eV2", "dm2_31_eV2")),
            str(spec["earth"]["detector_depth_km"]),
            *(str(grid[axis][k]) for axis in ("energy", "cos_nadir") for k in ("start", "stop", "step"))]
    out = subprocess.run([str(HERE / "b3_driver"), *argv], capture_output=True, text=True, check=True).stdout
    table = np.loadtxt(out.splitlines())
    energy, cos_nadir = spec.axis("energy", grid_name), spec.axis("cos_nadir", grid_name)
    # snap the driver's grid onto the spec's rounded values
    table[:, 0] = energy[np.abs(table[:, [0]] - energy).argmin(axis=1)]
    table[:, 1] = cos_nadir[np.abs(table[:, [1]] - cos_nadir).argmin(axis=1)]
    records = []
    for row in table:
        for i in range(3):
            records.append((grid_name, variant, f"P{i + 1}e", row[0], row[1], row[2 + 3 * i]))  # m[i][e]
    return records


def main():
    spec = load_spec("B3_earth")
    records = [r for variant in spec.variants for grid in spec.grids for r in run_variant(spec, variant, grid)]
    meta = {
        "tool": "nufast-earth",
        "tool_version": VERSION,
        "tool_commit": COMMIT,
        "benchmark": spec.id,
        "benchmark_version": spec.version,
        "contributor": "SNUfish maintainers (wrapper); NuFast-Earth by P. B. Denton and S. J. Parke",
        "date": datetime.date.today().isoformat(),
        "command": "cd contributions/nufast-earth/scripts && make && python run_b3.py",
        "settings": {
            "quantity": "Probability_Engine::solar_night_in_earth (Earth matrix, checked against "
                        "Get_Solar_Night_Probabilities = Vsolar x Earth matrix)",
            "eigenvalue_precision": "default",
            "earth_models": {"prem_prob3": "PREM_Prob3", "prem_four": "PREM_Four (mean density per segment)",
                             "prem_full": "PREM_Full (mean density per segment)", "native": NATIVE},
            "earth_model": NATIVE,
        },
        "license": "CC-BY-4.0",
        "reference": "arXiv:2511.04735",
    }
    path = contributions_dir() / meta["tool"] / spec.id / VERSION
    write_contribution(path, meta, records, spec)
    print(f"wrote {path} ({len(records)} rows)")


if __name__ == "__main__":
    main()
