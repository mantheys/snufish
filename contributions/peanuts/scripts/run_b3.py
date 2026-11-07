"""PEANUTS contribution to SNUfish B3 (Earth crossing), variant prem_prob3.

    python run_b3.py        # from this directory, SNUfish and requirements.txt installed

P(nu_i -> nu_e) = peanuts.earth.Pearth(e_i, ...)[0] in its default analytical mode (mass basis,
detector at the surface), on both grids of the spec. Writes contributions/peanuts/B3_earth/<version>/.

PEANUTS's Earth models are even polynomials n_e = alpha + beta r^2 + gamma r^4 (+ delta_n r^2n) per shell
(hep-ph/9702343). prem_prob3 is written in that form exactly (beta = gamma = 0). The PREM polynomials of
prem_four and prem_full have odd powers of r: PEANUTS cannot take them without refitting the density, so
those variants are left out (catalogue/tools/peanuts.yaml), not approximated. `native` (PEANUTS's own
Earth, Data/Earth_Density.csv) is left out too: on its non-constant shells the analytical evolutor is first
order in the density variation and not unitary, |P1e + P2e + P3e - 1| up to 9.7e-4 at 20 MeV, beyond B3's
1e-6 check (docs/crosschecks.md). `python run_b3.py --native` computes it for inspection, without writing it.
"""

import datetime
import sys
import tempfile
from pathlib import Path

import numpy as np
from _common import COMMIT, CONSTANT_EARTH, CONTRIBUTOR, PEANUTS, REFERENCE, VERSION, angles, quiet_import

from snufish.contribution import write_contribution
from snufish.paths import contributions_dir
from snufish.spec import load_spec

quiet_import()
from peanuts.earth import EarthDensity, Pearth  # noqa: E402
from peanuts.pmns import PMNS  # noqa: E402

NATIVE = ("PEANUTS Data/Earth_Density.csv: five shells, n_e = alpha + beta r^2 + gamma r^4 (Lisi & Montanino, "
          "hep-ph/9702343, fit to PREM)")


def density_file(spec, model, directory):
    """The spec's constant shells as a PEANUTS density file (r/R_E, n_e = rho Ye in mol/cm^3). The header
    copies Data/Earth_Density.csv: PEANUTS skips the comment lines and one blank line before the table."""
    radius = spec["earth"]["radius_km"]
    rows = [f"{s['outer_radius_km'] / radius!r}, {s['density'] * s['ye']!r}, 0, 0" for s in spec["earth_models"][model]["shells"]]
    path = Path(directory) / f"{model}.csv"
    path.write_text(f"# SNUfish B3 {model}: constant shells, n_e = rho Ye (mol/cm^3)\n"
                    "# In each layer N_j = alpha_j + beta_j*r_j**2 + gamma_j*r_j**4\n"
                    "# Radius  alpha  beta  gamma\n\n" + "\n".join(rows) + "\n")
    return path


def run_variant(spec, density, variant, grid):
    osc = spec["oscillation"]
    pmns = PMNS(*angles(osc))
    depth = 1e3 * spec["earth"]["detector_depth_km"]  # PEANUTS takes metres
    states = np.eye(3)
    records = []
    for e in spec.axis("energy", grid):
        for c in spec.axis("cos_nadir", grid):
            eta = float(np.arccos(c))  # nadir angle; cos = 0 gives pi/2 exactly (horizon, no matter)
            for i in range(3):
                p = Pearth(states[i], density, pmns, osc["dm2_21_eV2"], osc["dm2_31_eV2"], float(e), eta, depth)
                records.append((grid, variant, f"P{i + 1}e", e, c, float(p[0])))
    return records


def native_unitarity(spec):
    """Largest |P1e + P2e + P3e - 1| of PEANUTS's own Earth model on each grid (not a contribution)."""
    density = EarthDensity(density_file=str(PEANUTS / "Data" / "Earth_Density.csv"))
    for grid in spec.grids:
        sums = {}
        for _, _, _, e, c, p in run_variant(spec, density, "native", grid):
            sums[e, c] = sums.get((e, c), 0.0) + p
        (e, c), worst = max(((k, abs(v - 1)) for k, v in sums.items()), key=lambda kv: kv[1])
        print(f"native {grid}: |P1e + P2e + P3e - 1| up to {worst:.2e} (E = {e} MeV, cos_nadir = {c})")


def main():
    spec = load_spec("B3_earth")
    if "--native" in sys.argv:
        return native_unitarity(spec)
    records = []
    with tempfile.TemporaryDirectory() as tmp:
        density = EarthDensity(density_file=str(density_file(spec, "prem_prob3", tmp)))
        for grid in spec.grids:
            records += run_variant(spec, density, "prem_prob3", grid)
    meta = {
        "tool": "peanuts",
        "tool_version": VERSION,
        "tool_commit": COMMIT,
        "benchmark": spec.id,
        "benchmark_version": spec.version,
        "contributor": CONTRIBUTOR,
        "date": datetime.date.today().isoformat(),
        "command": "cd contributions/peanuts/scripts && python run_b3.py",
        "settings": {
            "quantity": "peanuts.earth.Pearth(e_i, mode='analytical', massbasis=True)[0], depth 0",
            "matter_potential": CONSTANT_EARTH,
            "earth_models": {
                "prem_prob3": "the spec's four shells as a PEANUTS density file (alpha = rho Ye, beta = gamma = 0): exact",
                "prem_four": "not computed: PREM's odd powers of r are not in PEANUTS's even-polynomial parametrisation",
                "prem_full": "not computed: as prem_four",
                "native": f"not contributed: {NATIVE}; the first-order analytical evolutor on its non-constant shells "
                          "breaks unitarity by up to 9.7e-4 (python run_b3.py --native)",
            },
        },
        "license": "CC-BY-4.0",
        "reference": REFERENCE,
    }
    path = contributions_dir() / meta["tool"] / spec.id / VERSION
    write_contribution(path, meta, records, spec)
    print(f"wrote {path} ({len(records)} rows)")


if __name__ == "__main__":
    main()
