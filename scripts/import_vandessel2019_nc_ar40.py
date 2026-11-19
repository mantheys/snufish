"""Writes reference/xsec/vandessel2019_nc_ar40.yaml: the nu + 40Ar -> nu + 40Ar* neutral-current inelastic cross section
of Van Dessel, Jachowicz & Nikolakopoulos, Phys. Rev. C 100, 055503 (2019), arXiv:1903.07726, fig. 8, bottom panel
("sigma_J,total"), curve "Total" (HF+CRPA), neutrinos.

    curl -L -o 1903.07726.tar.gz https://arxiv.org/e-print/1903.07726      # arXiv v3, the published version
    python scripts/import_vandessel2019_nc_ar40.py --source 1903.07726.tar.gz

Same paper, figure format and method as scripts/import_vandessel2019_nuebar_ar40.py (whose digitiser this reuses):
the curve is read from the drawing commands of the vector figure in the arXiv source (argtotnc.pdf), not from
pixels. Needs PyMuPDF (pip install pymupdf).
"""

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_vandessel2019_nuebar_ar40 import G_A, _figure, digitise  # noqa: E402

FIGURE = "argtotnc.pdf"
OUT = Path(__file__).resolve().parents[1] / "reference" / "xsec" / "vandessel2019_nc_ar40.yaml"
HEADER = """\
# nu + 40Ar -> nu + 40Ar* neutral-current inelastic total cross section (cm^2 per 40Ar nucleus), neutrinos, HF+CRPA:
# N. Van Dessel, N. Jachowicz and A. Nikolakopoulos, "Forbidden transitions in neutral and charged current interactions
# between low-energy neutrinos and Argon", Phys. Rev. C 100, 055503 (2019), arXiv:1903.07726 (v3, 2019-10-22), fig. 8,
# bottom panel ("sigma_J,total"), curve "Total". Retrieved {retrieved} from the arXiv source (e-print sha256
# {tar_sha}), figure file {figure} (sha256 {pdf_sha}). Written by scripts/import_vandessel2019_nc_ar40.py.
#
# METHOD: digitised from the vector figure, as reference/xsec/vandessel2019_nuebar_ar40.yaml (same paper): the paper
# publishes no table. The "Total" curve is a single gnuplot polyline of {n} vertices, the plotted data points:
# E = 10, 12, 14, ..., 100 MeV (2 MeV steps; abscissae within {dx:.3f} MeV of these values, rounded to them). Axis
# calibration, a straight-line fit of the major ticks to their labels: E = {ex[0]:+.4f} {ex[1]:+.6f} x/pt MeV (max
# residual {ex_res:.1e} pt), sigma = {ey[0]:+.4f} {ey[1]:+.6f} y/pt 1e-40 cm^2 (max residual {ey_res:.1e} pt).
# UNCERTAINTY: gnuplot writes coordinates to 0.05 pt, i.e. +-{dsig:.2g} cm^2 in sigma (half a step; the panel runs to
# 1.4e-39 cm^2), absolute: {rel12:.0f} % at 12 MeV, {rel16:.0f} % at 16 MeV, {rel20:.0f} % at 20 MeV, {rel30:.1f} % at
# 30 MeV, {rel50:.2f} % at 50 MeV. Below about 20 MeV, the solar range, the curve rests on 1-11 plotting steps. The
# paper quotes no model uncertainty.
#
# MODEL: Hartree-Fock (Skyrme) + continuum RPA, self-consistent residual interaction, all computed multipoles,
# FREE g_A = {g_a} (sec. II). NC: no Coulomb factor (zeta^2 = 1), lepton prefactor (G_F/2pi)^2. Flavour-blind for
# neutrinos (nu_e, nu_mu, nu_tau alike); the antineutrino curve (fig. 10) is smaller and is not stored here.
#
# CAVEAT, DISCRETE STATES: "within the CRPA, discrete excitations are not taken into account" (the paper, sec. III,
# on why its strength is low at low energies). For NC on 40Ar the measured isovector M1 (spin-flip, GT0-like) strength
# lies in bound 1+ levels, mostly at 9.7-10.0 MeV (Tornow et al., PLB 835, 137576 (2022)), below or at the neutron
# separation energy (about 9.9 MeV). That strength is missing from this curve; Tornow et al.'s shell-model estimate of
# the 0+ -> 1+ cross section from it is about 3e-44 cm^2 at 10 MeV and 1.4e-43 cm^2 at 15 MeV (+-43 %), a tenth of
# this curve at 15 MeV but all of the cross section below 12 MeV.
#
# THRESHOLD: NC has no Q value; any excited level can be reached (the first, 2+, at 1.46 MeV). The published curve is
# zero (below {half:.1e} cm^2, half a plotting step) at its first vertex, 10 MeV, and positive from 12 MeV. SNUfish does
# not invent strength below the curve: threshold_MeV = 10.0, sigma = 0 below it, and between 10 and 12 MeV the first
# segment of log(sigma) in log(E - 10 MeV) is continued to zero.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, required=True, help="arXiv e-print tarball of 1903.07726 (or its unpacked directory)")
    parser.add_argument("--retrieved", default="2026-11-19", help="date the e-print was downloaded")
    args = parser.parse_args()
    tar, pdf = _figure(args.source, FIGURE)
    energy, sigma, cal = digitise(pdf, "total")
    positive = energy[sigma > 0]
    threshold = float(energy[energy < positive[0]].max())
    assert np.all(np.diff(sigma[energy >= threshold]) > 0), "Total curve not increasing above its threshold"
    half = 0.5 * cal["step"]
    rel = lambda e: 100 * half / sigma[energy == e][0]
    sha = lambda b: hashlib.sha256(b).hexdigest()
    header = HEADER.format(retrieved=args.retrieved, tar_sha=sha(tar)[:16] + "..." if tar else "n/a", figure=FIGURE,
                           pdf_sha=sha(pdf)[:16] + "...", n=len(energy), dx=cal["dx"], ex=cal["ex"], ey=cal["ey"],
                           ex_res=cal["ex_res"], ey_res=cal["ey_res"], dsig=half * 1e-40, half=half * 1e-40,
                           rel12=rel(12), rel16=rel(16), rel20=rel(20), rel30=rel(30), rel50=rel(50), g_a=G_A)
    body = {"source": "Phys. Rev. C 100, 055503 (2019), arXiv:1903.07726, fig. 8 (bottom panel, Total)",
            "retrieved": args.retrieved,
            "method": "digitised (vector PDF of the figure, arXiv source)",
            "model": "HF (Skyrme) + CRPA, all multipoles, continuum only (no discrete excitations)",
            "g_A": G_A,
            "flavours": "nu_e, nu_mu, nu_tau identical; antineutrinos not stored (fig. 10)",
            "uncertainty_cm2": float(f"{half * 1e-40:.2g}"),   # digitisation only, absolute
            "threshold_MeV": threshold,
            "energy_MeV": [float(e) for e in energy],
            "total_1e-40cm2": [float(f"{s:.4g}") for s in sigma]}
    OUT.write_text(header + yaml.safe_dump(body, default_flow_style=None, width=118, sort_keys=False))
    print(f"wrote {OUT} ({len(energy)} points, sigma > 0 from {positive[0]:g} MeV, "
          f"{sigma[energy == 100][0]:.3f}e-40 cm^2 at 100 MeV)")


if __name__ == "__main__":
    main()
