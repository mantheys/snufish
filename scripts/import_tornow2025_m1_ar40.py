"""Writes reference/xsec/tornow2025_m1_ar40.yaml: the measured spin-flip M1 strength of 40Ar, B(M1 up) of the 1+
levels between 9.3 and 10.3 MeV, from Tornow, Tonchev, Finch, Krishichayan & Janssens, Phys. Rev. C 112, 054320
(2025), table II, the discrete strength that SNUfish's default NC model on 40Ar (snufish.reference.nc_ar40) uses.

    curl -L -o tornow2025.pdf https://www.osti.gov/pages/servlets/purl/3012352   # accepted manuscript, LLNL-JRNL-2010555
    python scripts/import_tornow2025_m1_ar40.py --source tornow2025.pdf

The table is read from the PDF's text layer (pdftotext -layout, poppler); every row is checked, and the sum is checked
against the paper's total, (1.31 +- 0.18) mu_N^2.
"""

import argparse
import hashlib
import re
import subprocess
from pathlib import Path

import yaml

OUT = Path(__file__).resolve().parents[1] / "reference" / "xsec" / "tornow2025_m1_ar40.yaml"
# a row of table II: Ex (keV), Gamma_0 (meV), B(M1 up) (1e-3 mu_N^2) (uncertainty), [B(M1 up) of Tornow et al. 2022]
ROW = re.compile(r"^\s*(\d{4,5}\.\d)\s+(\d+)\s+(\d+)\s*\((\d+)\)(?:\s+(\d+)\s*\((\d+)\))?\s{6,}\d{4,5}\.\d\s")
HEADER = """\
# Spin-flip M1 strength of 40Ar: the 1+ levels between 9.3 and 10.3 MeV excitation measured by nuclear resonance
# fluorescence with polarised photons at HIgS: W. Tornow, A. P. Tonchev, S. W. Finch, Krishichayan and R. V. F. Janssens,
# "Measurement of magnetic dipole strength in 40Ar between 9.3 and 10.3 MeV excitation energy and impact on neutral
# current neutrino interaction", Phys. Rev. C 112, 054320 (2025), doi:10.1103/55xh-b4f7, table II. Read from the
# accepted manuscript (OSTI 3012352, LLNL-JRNL-2010555, sha256 {sha}), retrieved {retrieved}, by
# scripts/import_tornow2025_m1_ar40.py: {n} levels, sum B(M1 up) = {total:.3f} mu_N^2 (the paper: 1.31 +- 0.18; its
# uncertainty adds 5 % for unobserved inelastic decays to the per-level 7-30 %).
#
# This is the "discrete neutral GT strength based on photonuclear data" that MARLEY's authors name for their planned
# NC model on 40Ar (Gardiner et al., arXiv:2604.26801, sec. VI). The paper finds no M1 strength from 10.3 to 11.7 MeV
# (detection limit 2e-3 mu_N^2), and none was found between 7.7 and 9.2 MeV by Li et al. (PRC 73, 054306 (2006));
# below 7.7 MeV the M1 strength of Gayer et al. (PRC 100, 034305 (2019)) is mainly orbital, not spin-flip, and is not
# used (the authors: "spin-flip M1 strength ... is not expected at such low energies"). The neutron separation energy
# is 9.870 MeV, but neutron emission is hindered by the centrifugal barrier below 11.137 MeV, so all levels are bound
# for this purpose. B(M1 up) of Tornow et al. 2022 (PLB 835, 137576), where measured, in b_m1_2022. At 9850.6 keV
# B(M1 up) is not 0.2592 Gamma_0 / Ex^3 (77): the authors correct its M1 yield for the strong E1 line at 9850.4 keV.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, required=True, help="the accepted manuscript (OSTI 3012352), PDF")
    parser.add_argument("--retrieved", default="2026-11-19", help="date the PDF was downloaded")
    args = parser.parse_args()
    text = subprocess.run(["pdftotext", "-layout", str(args.source), "-"], capture_output=True, text=True, check=True).stdout
    table = text[text.index("TABLE II."):text.index("substantial discrepancy remains")]
    rows = [m.groups() for m in map(ROW.match, table.splitlines()) if m]
    assert len(rows) == 28, f"expected 28 levels in table II, found {len(rows)}"
    total = sum(int(r[2]) for r in rows) * 1e-3
    assert abs(total - 1.31) < 0.005, f"sum of B(M1) {total} is not the paper's 1.31"
    # B(M1 up) = 0.2592 Gamma_0 / Ex^3 (eq. 2; 1e-3 mu_N^2, meV, MeV): every row is self-consistent except 9850.6 keV,
    # whose M1 yield the authors correct for the much stronger E1 line at 9850.4 keV (sec. IV): its Gamma_0 gives 77
    inconsistent = [ex for ex, gamma0, b, *_ in rows
                    if abs(259.2 * int(gamma0) / (float(ex) / 1e3) ** 3 - int(b)) > max(1.5, 0.05 * int(b))]
    assert inconsistent == ["9850.6"], inconsistent
    body = {"source": "Phys. Rev. C 112, 054320 (2025), table II (accepted manuscript, OSTI 3012352)",
            "retrieved": args.retrieved,
            "method": "table",
            "total_b_m1_muN2": [1.31, 0.18],
            "levels": [{"ex_keV": float(ex), "gamma0_meV": int(g), "b_m1_1e-3muN2": int(b), "error_1e-3muN2": int(e),
                        **({"b_m1_2022_1e-3muN2": int(b22)} if b22 else {})}
                       for ex, g, b, e, b22, _ in rows]}
    sha = hashlib.sha256(args.source.read_bytes()).hexdigest()
    OUT.write_text(HEADER.format(sha=sha[:16] + "...", retrieved=args.retrieved, n=len(rows), total=total)
                   + yaml.safe_dump(body, default_flow_style=None, width=118, sort_keys=False))
    print(f"wrote {OUT} ({len(rows)} levels, sum B(M1 up) = {total:.3f} mu_N^2)")


if __name__ == "__main__":
    main()
