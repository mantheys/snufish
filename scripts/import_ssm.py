"""Convert published standard solar model tables into SNUfish's format.

    python scripts/import_ssm.py --b23 <SolarModels dir of the B23 Zenodo zip> \
                                 --peanuts <PEANUTS Data dir>

Writes reference/ssm/<model>.dat (columns: r/R_sun, log10 n_e [N_A/cm^3],
then the production densities per unit r/R_sun of pp, pep, hep, Be7, B8,
N13, O15, F17, each integrating to 1) and benchmarks/B1_ssm/models.yaml
(fluxes, uncertainties, sources, density tail beyond the table).

The inputs are only read as numbers (np.loadtxt); nothing from them runs.
"""

import argparse
import hashlib
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ["pp", "pep", "hep", "Be7", "B8", "N13", "O15", "F17"]
HEADER = "r_over_Rsun  log10_ne_NA_per_cm3  " + "  ".join(COMPONENTS)

# B16 flux table rows (fluxes_b16.dat): pp, pep, hep, 7Be, 8B, 13N, 15O, 17F,
# in units of 1e10, 1e8, 1e3, 1e9, 1e6, 1e8, 1e8, 1e6 cm^-2 s^-1.
B16_UNITS = [1e10, 1e8, 1e3, 1e9, 1e6, 1e8, 1e8, 1e6]
# BS05 profile columns 6-13: pp, 8B, 13N, 15O, 17F, 7Be, pep, hep (zone fractions).
BS05_ORDER = {"pp": 5, "B8": 6, "N13": 7, "O15": 8, "F17": 9, "Be7": 10, "pep": 11, "hep": 12}

B23_MODELS = {
    "b23_gs98": ("GS98", "Grevesse & Sauval (1998)"),
    "b23_agss09": ("AGSS09", "Asplund et al. (2009)"),
    "b23_c11": ("C11", "Caffau et al. (2011)"),
    "b23_aag21": ("AAG21", "Asplund et al. (2021)"),
    "b23_mb22m": ("MB22m", "Magg et al. (2022), meteoritic"),
    "b23_mb22p": ("MB22p", "Magg et al. (2022), photospheric"),
}
B23_SOURCE = ("Herrera & Serenelli, Standard Solar Models B23 / SF-III v1.2, Zenodo 10.5281/zenodo.10174172 "
              "(record 10822316); cite Magg et al. 2022 (A&A 661, A140) and Solar Fusion III "
              "(Acharya et al. 2025, Rev. Mod. Phys. 97, 035002)")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tail_fit(r, log_ne):
    """log10 n_e = a + b r fitted for r > 0.4 (tables that stop at 0.5)."""
    sel = r > 0.4
    slope, intercept = np.polyfit(r[sel], log_ne[sel], 1)
    residual = float(np.abs(log_ne[sel] - (intercept + slope * r[sel])).max())
    return {"intercept": round(float(intercept), 4), "slope": round(float(slope), 4), "max_residual": round(residual, 4)}


def write_table(name, r, log_ne, densities, note):
    path = ROOT / "reference" / "ssm" / f"{name}.dat"
    densities = np.clip(densities, 0.0, None)  # tables carry -1e-11 rounding noise at the centre
    densities = densities / np.trapezoid(densities, r, axis=0)
    data = np.column_stack([r, log_ne, densities])
    np.savetxt(path, data, fmt="%.6e", header=f"{note}\n{HEADER}")
    return path


def b16(peanuts):
    fluxes = np.loadtxt(peanuts / "fluxes_b16.dat", comments="#")
    out = {}
    for name, label, file, column in (("b16_gs98", "GS98", "nudistr_b16_gs98.dat", 0),
                                      ("b16_agss09met", "AGSS09met", "nudistr_b16_agss09.dat", 2)):
        table = np.loadtxt(peanuts / file, comments="#")
        r, log_ne = table[:, 0], table[:, 2]
        path = write_table(name, r, log_ne, table[:, 4:12],
                           f"B16-{label} (Vinyoles et al. 2017, arXiv:1611.09867), from PEANUTS Data/{file}")
        out[name] = {
            "family": "B16", "composition": label, "reference": "arXiv:1611.09867",
            "fluxes": {c: float(f"{fluxes[k, column] * u:.4g}") for k, (c, u) in enumerate(zip(COMPONENTS, B16_UNITS))},
            "flux_uncertainty": {c: float(fluxes[k, column + 1]) for k, c in enumerate(COMPONENTS)},
            "table": str(path.relative_to(ROOT)), "tail": tail_fit(r, log_ne),
            "source": {"file": f"PEANUTS Data/{file}, fluxes_b16.dat", "sha256": sha256(peanuts / file)},
        }
    return out


def _numeric_row(line, n):
    tokens = line.split()
    try:
        return len(tokens) == n and all(np.isfinite(float(t)) for t in tokens)
    except ValueError:
        return False


def bs05(peanuts):
    out = {}
    for name, label, file in (("bs05_op", "GS98 (OP opacities)", "bs2005opflux.dat"),
                              ("bs05_agsop", "AGS05 (OP opacities)", "bs2005agsopflux.csv")):
        lines = (peanuts / file).read_text().splitlines()
        cumulative = next(i for i, line in enumerate(lines) if "cumulative neutrino fluxes" in line)
        totals = [float(v) * 1e10 for v in lines[cumulative + 2].split()]  # units of 1e10 cm^-2 s^-1
        order = ["pp", "pep", "hep", "Be7", "B8", "N13", "O15", "F17"]
        start = next(i for i, line in enumerate(lines) if _numeric_row(line, 13))
        table = np.loadtxt(lines[start:])
        r, log_ne = table[:, 0], table[:, 2]
        fractions = np.column_stack([table[:, BS05_ORDER[c]] for c in COMPONENTS])
        densities = fractions / np.gradient(r)[:, None]  # zone fractions -> per unit r
        path = write_table(name, r, log_ne, densities,
                           f"BS05 {label} (Bahcall, Serenelli & Basu 2005, astro-ph/0412440), from PEANUTS Data/{file}")
        out[name] = {
            "family": "BS05", "composition": label, "reference": "astro-ph/0412440",
            "fluxes": {c: float(f"{v:.4g}") for c, v in zip(order, totals)},
            "flux_uncertainty": None,
            "table": str(path.relative_to(ROOT)), "tail": tail_fit(r, log_ne),
            "source": {"file": f"PEANUTS Data/{file}", "sha256": sha256(peanuts / file)},
        }
    return out


def b23(directory):
    out = {}
    for name, (label, composition) in B23_MODELS.items():
        struct = directory / f"struct+nu_SF3_{label}.dat"
        table = np.loadtxt(struct, comments="#")
        r, log_ne, densities = table[:, 0], table[:, 17], table[:, 9:17]
        path = write_table(name, r, log_ne, densities,
                           f"B23-{label} / SF-III, {composition} abundances. {B23_SOURCE}")
        flux_lines = (directory / f"fluxes_SF3_{label}.dat").read_text().splitlines()
        values = next(line for line in flux_lines if line.rstrip().endswith("Flux")).split()[:8]
        errors = next(line for line in flux_lines if line.rstrip().endswith("Fract.Err")).split()[:8]
        out[name] = {
            "family": "B23", "composition": f"{label}: {composition}", "reference": "Zenodo 10.5281/zenodo.10174172",
            "fluxes": {c: float(v) for c, v in zip(COMPONENTS, values)},
            "flux_uncertainty": {c: float(e) for c, e in zip(COMPONENTS, errors)},
            "table": str(path.relative_to(ROOT)), "tail": None,  # tabulated to the surface
            "source": {"file": f"SolarModels_ICE2023_v1.2.zip: SolarModels/struct+nu_SF3_{label}.dat, "
                               f"fluxes_SF3_{label}.dat", "sha256": sha256(struct), "license": "CC-BY-4.0"},
        }
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--b23", type=Path, required=True)
    parser.add_argument("--peanuts", type=Path, required=True)
    args = parser.parse_args()
    models = {**b16(args.peanuts), **bs05(args.peanuts), **b23(args.b23)}
    target = ROOT / "benchmarks" / "B1_ssm" / "models.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w") as handle:
        handle.write("# Written by scripts/import_ssm.py: do not edit by hand.\n")
        yaml.safe_dump(models, handle, sort_keys=False, width=120)
    print(f"{len(models)} models -> {target}")


if __name__ == "__main__":
    main()
