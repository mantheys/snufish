"""NuFast-Earth contribution to SNUfish B2 (adiabatic solar fractions).

    make && python run_b2.py        # from this directory, SNUfish installed

Evaluates the spec's electron density at every production radius and runs
b2_driver on the (E, n_e) points; writes contributions/nufast-earth/B2_sun/<version>/.
"""

import datetime
import subprocess
from pathlib import Path

import numpy as np

from snufish.contribution import write_contribution
from snufish.paths import contributions_dir
from snufish.solar import electron_density
from snufish.spec import load_spec

HERE = Path(__file__).resolve().parent


def _git(*args):
    return subprocess.run(["git", "-C", str(HERE / "NuFast-Earth"), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


COMMIT = _git("rev-parse", "--short", "HEAD")
VERSION = _git("describe", "--tags").removeprefix("v")


def run(spec, variant, grid):
    osc = spec["oscillation"]
    energies, radii = spec.axis("energy", grid), spec.axis("radius", grid)
    density = electron_density(spec.variants[variant]["solar_model"], radii, spec)
    points = "\n".join(f"{e:.10g} {n:.17g}" for n in density for e in energies)
    argv = [str(osc[k]) for k in ("sin2_theta12", "sin2_theta13", "sin2_theta23", "delta_cp_deg",
                                  "dm2_21_eV2", "dm2_31_eV2")]
    out = subprocess.run([str(HERE / "b2_driver"), *argv], input=points, capture_output=True, text=True,
                         check=True).stdout
    table = np.loadtxt(out.splitlines()).reshape(len(radii), len(energies), 5)
    return [(grid, variant, f"F{i + 1}", e, r, table[k, j, 2 + i])
            for k, r in enumerate(radii) for j, e in enumerate(energies) for i in range(3)]


def main():
    spec = load_spec("B2_sun")
    records = [r for variant in spec.variants for grid in spec.grids for r in run(spec, variant, grid)]
    meta = {
        "tool": "nufast-earth",
        "tool_version": VERSION,
        "tool_commit": COMMIT,
        "benchmark": spec.id,
        "benchmark_version": spec.version,
        "contributor": "SNUfish maintainers (wrapper); NuFast-Earth by P. B. Denton and S. J. Parke",
        "date": datetime.date.today().isoformat(),
        "command": "cd contributions/nufast-earth/scripts && make && python run_b2.py",
        "settings": {"quantity": "Probability_Engine::Calculate_Solar_Probability (adiabatic |V_ei|^2 at "
                                 "rhoYe = n_e(r0)); F1 = 1 - F2 - F3 by construction"},
        "license": "CC-BY-4.0",
        "reference": "arXiv:2511.04735",
    }
    path = contributions_dir() / meta["tool"] / spec.id / VERSION
    write_contribution(path, meta, records, spec)
    print(f"wrote {path} ({len(records)} rows)")


if __name__ == "__main__":
    main()
