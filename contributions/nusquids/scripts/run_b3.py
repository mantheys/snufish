"""nuSQuIDS contribution to SNUfish B3 (Earth crossing): prem_prob3, prem_four, prem_full, and optionally native.

    make && python run_b3.py [--jobs N] [--variants prem_prob3 prem_four prem_full native]
                                            # from this directory, SNUfish installed

Runs b3_driver (nuSQuIDS, oscillations only, detector at the surface) on both grids of the spec, the
cos_nadir axis split over N processes; each chunk is kept in out/ so an interrupted run resumes.
Writes contributions/nusquids/B3_earth/<version>/.

- prem_prob3: ConstantDensity bodies per chord segment, evolved exactly.
- prem_four, prem_full: the spec's PREM polynomials along the chord (a Body subclass in b3_driver.cpp),
  integrated by GSL with relative and absolute error 1e-10 (within 3e-9 of 1e-12), one EvolveState per
  region crossing.
- native (not run by default: two more hours of GSL on 8 cores, and an Earth that no other tool shares):
  nuSQuIDS's Earth body (data/astro/EARTH_MODEL_PREM.dat: PREM every 0.005 R_E, Akima spline, Ye 0.4656
  core, 0.4957 mantle), one track, same GSL settings.
"""

import argparse
import datetime
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from snufish.contribution import write_contribution
from snufish.paths import contributions_dir
from snufish.spec import load_spec

HERE = Path(__file__).resolve().parent
VERSION, COMMIT = "1.13.3", "104914d"  # build_nusquids.sh: nuSQuIDS v1.13.3 on SQuIDS v1.3.1
TOLERANCE = 1e-10
NATIVE = ("nuSQuIDS Earth() body: data/astro/EARTH_MODEL_PREM.dat (PREM sampled every 0.005 R_E, Akima "
          "spline across the discontinuities; Ye 0.4656 core, 0.4957 mantle), R_E = 6371 km")
EARTH_MODELS = {
    "prem_prob3": "ConstantDensity per chord segment, Set_AllowConstantDensityOscillationOnlyEvolution(true): exact",
    "prem_four": "the spec's polynomials along the chord, GSL, one EvolveState per region crossing",
    "prem_full": "as prem_four",
    "native": NATIVE,
}
MODES = {"prem_prob3": "shells", "prem_four": "regions", "prem_full": "regions", "native": "native"}


def model_lines(spec, variant):
    if MODES[variant] == "native":
        return ""
    model = spec["earth_models"][spec.variants[variant]["earth_model"]]
    if "shells" in model:
        return "".join(f"{s['outer_radius_km']!r} {s['ye']!r} {s['density']!r}\n" for s in model["shells"])
    return "".join(f"{g['outer_radius_km']!r} {g['ye']!r} " + " ".join(map(repr, g["coefficients"])) + "\n"
                   for g in model["regions"])


def run_chunk(spec, variant, grid, k, cosines):
    out = HERE / "out" / f"{variant}_{grid}_{k:03d}.txt"
    if not out.exists():
        osc, axis = spec["oscillation"], spec["grids"][grid]["energy"]
        argv = [str(HERE / "b3_driver"), MODES[variant],
                *(repr(osc[q]) for q in ("sin2_theta12", "sin2_theta13", "sin2_theta23", "delta_cp_deg", "dm2_21_eV2", "dm2_31_eV2")),
                repr(TOLERANCE), repr(TOLERANCE), *(repr(axis[q]) for q in ("start", "stop", "step")), *(repr(float(c)) for c in cosines)]
        text = subprocess.run(argv, input=model_lines(spec, variant), capture_output=True, text=True, check=True).stdout
        out.parent.mkdir(exist_ok=True)
        part = out.with_suffix(".part")
        part.write_text(text)
        part.rename(out)
    return np.loadtxt(out, ndmin=2)


def run_variant(spec, variant, grid, jobs):
    energy, cos_nadir = spec.axis("energy", grid), spec.axis("cos_nadir", grid)
    chunks = np.array_split(cos_nadir[::-1], max(1, len(cos_nadir) // 8))  # long chords first, ~8 cosines each
    with ThreadPoolExecutor(jobs) as pool:
        tables = list(pool.map(lambda kc: run_chunk(spec, variant, grid, *kc), enumerate(chunks)))
    table = np.concatenate(tables)
    table[:, 0] = energy[np.abs(table[:, [0]] - energy).argmin(axis=1)]  # snap onto the spec's rounded values
    table[:, 1] = cos_nadir[np.abs(table[:, [1]] - cos_nadir).argmin(axis=1)]
    return [(grid, variant, f"P{i + 1}e", row[0], row[1], row[2 + i]) for row in table for i in range(3)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=os.cpu_count())
    parser.add_argument("--variants", nargs="*", default=["prem_prob3", "prem_four", "prem_full"], choices=list(MODES))
    args = parser.parse_args()
    spec = load_spec("B3_earth")
    records = []
    for variant in args.variants:
        for grid in spec.grids:
            records += run_variant(spec, variant, grid, args.jobs)
            print(f"{variant} {grid}: done", flush=True)
    meta = {
        "tool": "nusquids",
        "tool_version": VERSION,
        "tool_commit": COMMIT,
        "benchmark": spec.id,
        "benchmark_version": spec.version,
        "contributor": "SNUfish maintainers (wrapper); nuSQuIDS by C. A. Argüelles, J. Salvado and C. N. Weaver",
        "date": datetime.date.today().isoformat(),
        "command": "cd contributions/nusquids/scripts && make && python run_b3.py",
        "settings": {
            "quantity": "EvalFlavorAtNode(0) after evolving the vacuum mass eigenstate i (Set_initial_state(..., mass)); "
                        "one single-energy nuSQUIDS per point, oscillations only",
            "build": "SQuIDS v1.3.1 (f9e6182), nuSQuIDS v1.13.3 (104914d): build_nusquids.sh",
            "matter_potential": "sqrt(2) G_F N_A rho Ye with SQuIDS's G_F = 1.1663787e-5 GeV^-2, 8.6e-8 below the spec's",
            "gsl": f"rkf45 (SQuIDS default), rel_error = abs_error = {TOLERANCE:g} (prem_four, prem_full, native)",
            "earth_models": {variant: EARTH_MODELS[variant] if variant in args.variants else "not computed in this run (optional)"
                             for variant in MODES},
            **({"earth_model": NATIVE} if "native" in args.variants else {}),
        },
        "license": "CC-BY-4.0",
        "reference": "arXiv:2112.13804",
    }
    path = contributions_dir() / meta["tool"] / spec.id / VERSION
    write_contribution(path, meta, records, spec)
    print(f"wrote {path} ({len(records)} rows)")


if __name__ == "__main__":
    main()
