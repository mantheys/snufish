"""Writes reference/xsec/vandessel2019_nuebar_ar40.yaml: the nu_e-bar + 40Ar -> e+ + 40Cl total cross section of
Van Dessel, Jachowicz & Nikolakopoulos, Phys. Rev. C 100, 055503 (2019), arXiv:1903.07726, fig. 9, bottom panel
("sigma_J,total"), curve "Total" (HF+CRPA).

    curl -L -o 1903.07726.tar.gz https://arxiv.org/e-print/1903.07726      # arXiv v3, the published version
    python scripts/import_vandessel2019_nuebar_ar40.py --source 1903.07726.tar.gz

The paper gives no table. Its arXiv source contains the figure as a vector PDF (argtotccanti.pdf, gnuplot through
pdfTeX), so the curve is read from the PDF's drawing commands, not from pixels: the "Total" curve is one solid
polyline whose vertices are the plotted data points. The axes are calibrated by a straight-line fit of the major tick
marks to their numeric labels, and the vertex coordinates are quantised to 0.05 pt by gnuplot, the digitisation
uncertainty. Needs PyMuPDF (pip install pymupdf), which SNUfish itself does not.
"""

import argparse
import hashlib
import io
import tarfile
from pathlib import Path

import numpy as np
import yaml

FIGURE = "argtotccanti.pdf"
TOTAL_RGB = (0.580, 0.000, 0.830)    # gnuplot's first line colour, the "Total" curve
OUT = Path(__file__).resolve().parents[1] / "reference" / "xsec" / "vandessel2019_nuebar_ar40.yaml"
HEADER = """\
# nu_e-bar 40Ar -> e+ 40Cl total charged-current cross section (cm^2 per 40Ar nucleus), HF+CRPA: N. Van Dessel,
# N. Jachowicz and A. Nikolakopoulos, "Forbidden transitions in neutral and charged current interactions between
# low-energy neutrinos and Argon", Phys. Rev. C 100, 055503 (2019), arXiv:1903.07726 (v3, 2019-10-22), fig. 9, bottom
# panel ("sigma_J,total"), curve "Total". Retrieved {retrieved} from the arXiv source (e-print sha256
# {tar_sha}), figure file {figure} (sha256 {pdf_sha}). Written by scripts/import_vandessel2019_nuebar_ar40.py.
#
# METHOD: digitised from the vector figure, not from pixels. The paper publishes no table (none in the arXiv source,
# no supplemental material, none found in later papers of the group). The "Total" curve is a single gnuplot polyline
# of {n} vertices, the plotted data points: E = 10, 16, 18, 20, ..., 100 MeV (2 MeV steps; the vertex abscissae lie
# within {dx:.3f} MeV of these values and are rounded to them). Axis calibration, a straight-line fit of the major
# ticks to their labels: E = {ex[0]:+.4f} {ex[1]:+.6f} x/pt MeV (6 ticks, max residual {ex_res:.1e} pt),
# sigma = {ey[0]:+.4f} {ey[1]:+.6f} y/pt 1e-40 cm^2 (10 ticks, max residual {ey_res:.1e} pt).
# UNCERTAINTY: gnuplot writes coordinates to 0.05 pt, i.e. +-{dsig:.2g} cm^2 in sigma (half a step), absolute: 1.4 % at
# 30 MeV, 0.15 % at 50 MeV, 0.014 % at 100 MeV, but 17 % at 20 MeV and 50 % at 18 MeV, where the curve is 1-3 steps
# above zero. The paper quotes no model uncertainty.
#
# MODEL: Hartree-Fock (Skyrme) + continuum RPA, self-consistent residual interaction, all computed multipoles (the
# J <= 3 curve of the figure lies a few % below the Total at 100 MeV; the paper's fig. 11 sums J <= 7). FREE g_A =
# 1.27, not quenched (sec. II: "we use the free-nucleon value for the axial coupling of g_A = 1.27"). Coulomb
# correction of the outgoing positron (Z' = 17): an interpolation between the Fermi function and the modified
# effective momentum approximation (MEMA), taking at each energy transfer the zeta^2 closest to unity (sec. II, after
# Engel 1998); for argon the Fermi function applies below about 60-70 MeV, MEMA above.
#
# THRESHOLD: the reaction threshold is Q_beta(40Cl) + 2 m_e = 7.48 + 1.022 = 8.50 MeV, but the 40Cl ground state is
# 2- (unique first-forbidden from the 0+ 40Ar ground state) and the allowed (1+) strength lies higher. The published
# curve is zero (below 1.2e-43 cm^2, half a plotting step) at its vertices 10 and 16 MeV and positive from 18 MeV.
# SNUfish does not invent strength below the curve: threshold_MeV = 16.0 is the last published zero, sigma = 0 below
# it, and between 16 and 18 MeV the first segment of log(sigma) in log(E - 16 MeV) is continued to zero. The true
# cross section between 8.5 and 16 MeV is small but not exactly zero; the figure does not resolve it.
"""


def _figure(source):
    """(tarball bytes or None, figure PDF bytes) from the arXiv e-print tarball or an unpacked directory."""
    source = Path(source)
    if source.is_dir():
        return None, (source / FIGURE).read_bytes()
    raw = source.read_bytes()
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        return raw, tar.extractfile(FIGURE).read()


def _segments(drawing):
    return [(it[1].x, it[1].y, it[2].x, it[2].y) for it in drawing["items"] if it[0] == "l"]


def digitise(pdf):
    """(energy MeV, sigma 1e-40 cm^2, calibration) of the bottom panel's "Total" curve."""
    try:
        import pymupdf as fitz
    except ImportError:   # PyMuPDF < 1.24
        import fitz

    page = fitz.open(stream=pdf, filetype="pdf")[0]
    drawings = page.get_drawings()
    frames = [it[1].rect for d in drawings for it in d["items"] if it[0] == "qu"]
    frame = max(frames, key=lambda r: r.y1)   # the bottom panel
    on = lambda v, w: abs(v - w) < 0.01
    inside = lambda x, y: frame.x0 - 0.01 <= x <= frame.x1 + 0.01 and frame.y0 - 0.01 <= y <= frame.y1 + 0.01
    lines = [s for d in drawings if d.get("color") == (0.0, 0.0, 0.0) for s in _segments(d)]
    # major ticks: 6.3 pt long, on the bottom edge (x) and the left edge (y)
    xticks = sorted({round(s[0], 3) for s in lines if on(s[0], s[2]) and on(s[1], frame.y1) and on(s[1] - s[3], 6.3)})
    yticks = sorted({round(s[1], 3) for s in lines if on(s[1], s[3]) and on(s[0], frame.x0) and on(s[2] - s[0], 6.3)
                     and frame.y0 - 0.01 <= s[1] <= frame.y1 + 0.01})
    words = [w for w in page.get_text("words") if w[4].lstrip("-").isdigit()]
    xlabels = {round(0.5 * (w[0] + w[2]), 1): float(w[4]) for w in words if frame.y1 < w[1] < frame.y1 + 10}
    ylabels = {round(0.5 * (w[1] + w[3]), 1): float(w[4]) for w in words if w[2] < frame.x0 and frame.y0 - 10 < w[1] < frame.y1}

    def fit(ticks, labels):
        value = [labels[min(labels, key=lambda c: abs(c - t))] for t in ticks]
        assert len(set(value)) == len(ticks), "tick labels not matched one to one"
        coef = np.polynomial.polynomial.polyfit(ticks, value, 1)
        residual = np.max(np.abs(np.polynomial.polynomial.polyval(ticks, coef) - value)) / abs(coef[1])
        return coef, residual

    ex, ex_res = fit(xticks, xlabels)
    ey, ey_res = fit(yticks, ylabels)
    assert len(xticks) == 6 and len(yticks) == 10, (xticks, yticks)
    # the "Total" curve: the solid purple polyline in the frame; the legend sample is a lone segment, not chained
    total = [d for d in drawings if d.get("color") and np.allclose(d["color"], TOTAL_RGB, atol=2e-3)
             and d.get("dashes") in (None, "[] 0") and inside(d["rect"].x1, d["rect"].y1)]
    assert len(total) == 1, total
    segments = _segments(total[0])
    chain = [segments[1]]
    for s in segments[2:]:
        assert on(s[0], chain[-1][2]) and on(s[1], chain[-1][3]), "the Total curve is not one polyline"
        chain.append(s)
    assert not (on(segments[0][2], segments[1][0]) and on(segments[0][3], segments[1][1])), "legend sample not found"
    x = np.array([chain[0][0]] + [s[2] for s in chain])
    y = np.array([chain[0][1]] + [s[3] for s in chain])
    energy = np.polynomial.polynomial.polyval(x, ex)
    dx = np.max(np.abs(energy - np.round(energy)))
    assert dx < 0.03, "vertices off the integer-MeV grid"
    sigma = np.polynomial.polynomial.polyval(y, ey)
    step = 0.05 * abs(ey[1])                   # gnuplot's 0.05 pt output resolution, in 1e-40 cm^2
    sigma = np.where(np.abs(sigma) < 0.5 * step, 0.0, sigma)
    calibration = dict(ex=ex, ey=ey, ex_res=ex_res, ey_res=ey_res, step=step, dx=dx)
    return np.round(energy), sigma, calibration


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, required=True, help="arXiv e-print tarball of 1903.07726 (or its unpacked directory)")
    parser.add_argument("--retrieved", default="2026-11-19", help="date the e-print was downloaded")
    args = parser.parse_args()
    tar, pdf = _figure(args.source)
    energy, sigma, cal = digitise(pdf)
    sha = lambda b: hashlib.sha256(b).hexdigest()
    positive = energy[sigma > 0]
    threshold = float(energy[energy < positive[0]].max())
    assert np.all(np.diff(sigma[energy >= threshold]) > 0), "Total curve not increasing above its threshold"
    header = HEADER.format(retrieved=args.retrieved, tar_sha=sha(tar)[:16] + "..." if tar else "n/a", figure=FIGURE,
                           n=len(energy), dx=cal["dx"],
                           pdf_sha=sha(pdf)[:16] + "...", ex=cal["ex"], ey=cal["ey"], ex_res=cal["ex_res"],
                           ey_res=cal["ey_res"], dsig=0.5 * cal["step"] * 1e-40)
    body = {"source": "Phys. Rev. C 100, 055503 (2019), arXiv:1903.07726, fig. 9 (bottom panel, Total)",
            "retrieved": args.retrieved,
            "method": "digitised (vector PDF of the figure, arXiv source)",
            "model": "HF (Skyrme) + CRPA, all multipoles",
            "g_A": 1.27,
            "coulomb": "Fermi function / MEMA interpolation (zeta^2 closest to 1)",
            "uncertainty_cm2": float(f"{0.5 * cal['step'] * 1e-40:.2g}"),   # digitisation only, absolute
            "reaction_threshold_MeV": 8.50,
            "threshold_MeV": threshold,
            "energy_MeV": [float(e) for e in energy],
            "total_1e-40cm2": [float(f"{s:.4g}") for s in sigma]}
    OUT.write_text(header + yaml.safe_dump(body, default_flow_style=None, width=118, sort_keys=False))
    print(f"wrote {OUT} ({len(energy)} points, sigma > 0 from {positive[0]:g} MeV, "
          f"{sigma[energy == 100][0]:.3f}e-40 cm^2 at 100 MeV)")


if __name__ == "__main__":
    main()
