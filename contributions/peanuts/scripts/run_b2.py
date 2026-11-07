"""PEANUTS contribution to SNUfish B2 (mass-eigenstate fractions leaving the Sun).

    python run_b2.py        # from this directory, SNUfish and requirements.txt installed

F_i(E, r0) = peanuts.solar.Tei at the spec's electron density n_e(r0): the adiabatic weights from the
matter mixing angles at the production point (PEANUTS's own expressions, arXiv:1604.08167 and
arXiv:1801.06514). Writes contributions/peanuts/B2_sun/<version>/.
"""

import datetime

import numpy as np
from _common import COMMIT, CONSTANT_SUN, CONTRIBUTOR, REFERENCE, VERSION, angles, quiet_import

from snufish.contribution import write_contribution
from snufish.paths import contributions_dir
from snufish.solar import electron_density
from snufish.spec import load_spec

quiet_import()
from peanuts.solar import Tei  # noqa: E402


def run(spec, variant, grid):
    osc = spec["oscillation"]
    th12, th13, _, _ = angles(osc)
    energies, radii = spec.axis("energy", grid), spec.axis("radius", grid)
    density = np.asarray(electron_density(spec.variants[variant]["solar_model"], radii, spec), dtype=float)  # mol/cm^3
    records = []
    for e in energies:
        weights = Tei(th12, th13, osc["dm2_21_eV2"], osc["dm2_31_eV2"], float(e), density)
        for i in range(3):
            records += [(grid, variant, f"F{i + 1}", e, r, float(w)) for r, w in zip(radii, weights[i])]
    return records


def main():
    spec = load_spec("B2_sun")
    records = [r for variant in spec.variants for grid in spec.grids for r in run(spec, variant, grid)]
    meta = {
        "tool": "peanuts",
        "tool_version": VERSION,
        "tool_commit": COMMIT,
        "benchmark": spec.id,
        "benchmark_version": spec.version,
        "contributor": CONTRIBUTOR,
        "date": datetime.date.today().isoformat(),
        "command": "cd contributions/peanuts/scripts && python run_b2.py",
        "settings": {
            "quantity": "peanuts.solar.Tei (adiabatic weights (c13m c12m)^2, (c13m s12m)^2, s13m^2 from the matter "
                        "angles th13_M, th12_M_given_th13_M at n_e(r0))",
            "matter_potential": CONSTANT_SUN,
            "electron_density": "the spec's n_e(r0) (snufish.solar.electron_density), passed in mol/cm^3",
        },
        "license": "CC-BY-4.0",
        "reference": REFERENCE,
    }
    path = contributions_dir() / meta["tool"] / spec.id / VERSION
    write_contribution(path, meta, records, spec)
    print(f"wrote {path} ({len(records)} rows)")


if __name__ == "__main__":
    main()
