"""The 3D crust (prem_crust1_3d) against the radial Earth models, and the published numbers it is checked with.

    python scripts/earth3d_literature.py            # all three parts, ~10 min (the chords of five sites first)
    python scripts/earth3d_literature.py --part han

1. ``han``: Han et al., arXiv:2607.24421, table 7.1. A^osc_DN, the day-night asymmetry of the 8B nu_e flux
   (0.1-16 MeV, B16-GS98, no cross section), PDG 2025 parameters. Their 1D Earth is PREM with Ye = 0.50 in the
   mantle and 0.467 in the core; their 3D Earth is LITHO1.0 (crust and lithosphere to 320 km) on SAW642AN (mantle
   to 2880 km). Their 1D asymmetry is A^osc - Delta (Delta: the 3D shift of the flux asymmetry, the same for A^osc
   since the Earth-Sun distance does not depend on the Earth model). Reproduced here: the 1D value with PREM at
   their Ye, and Delta against SNUfish's shift from full PREM to the CRUST1.0 crust along each chord.
2. ``bakhti``: Bakhti & Smirnov, arXiv:2001.08030, sec. IV: Hyper-K (Kamioka), ES with T > 6.5 MeV, sigma_E/E =
   15 %, A_ND = N/D - 1, Delta m^2_21 = 7.5e-5 eV^2, theta13 = 8.4 deg (theta12 not stated: 0.307). With CRUST1.0
   A_ND = 0.022, "about 5 % smaller than with the PREM model" (their PREM: no ocean, its crust to the surface).
3. ``sites``: annual A_DN of 8B (+ hep) ES in water above 3.49 MeV and of 8B CC on 40Ar above 5 MeV (B23-MB22m,
   JUNO 2025), full PREM, PREM + the local crust and PREM + the crust along each chord, at the five B3 sites.
4. ``average`` (not in the default run): the approximation of prem_crust1_3d, the crust of a cos-nadir cell's
   chords averaged before solving, against P averaged over the cell's single chords (each turned to the cell's
   nadir), at a few cells of one site (``--site``).
"""

import argparse
import subprocess

import numpy as np

from snufish import crust, earth3d, engine
from snufish.export import ExactProbabilities, collect_inputs
from snufish.fluxes import components
from snufish.scan import SPLIT_KM, _nufast_driver, day_fractions, night_probabilities, oscillation, site_latitude
from snufish.spec import load_spec, pmns

SITES = ("Kamioka", "LNGS", "SURF", "SNOLAB", "Jiangmen")
# Han et al. table 7.1: A^osc_DN (3D) and Delta (pp); SNO for SNOLAB, JUNO for Jiangmen
HAN = {"Kamioka": (1.407, 0.025), "LNGS": (1.353, 0.001), "SURF": (1.391, 0.049), "SNOLAB": (1.393, 0.064),
       "Jiangmen": (1.477, 0.050)}
PDG2025 = dict(sin2_theta12=0.308, sin2_theta13=0.02215, dm2_21_eV2=7.49e-5, dm2_31_eV2=2.438e-3 + 7.49e-5)


def regions_model(ye_mantle=None, ye_core=None, ocean=None):
    """``regions:FILE`` of full PREM with other Ye, or its ocean replaced by ``ocean`` g/cm^3, cut into
    SPLIT_KM shells."""
    regions = [dict(r) for r in load_spec("B3_earth")["earth_models"]["prem_full"]["regions"]]
    for r in regions:
        if ye_mantle is not None:
            r["ye"] = ye_core if r["ye"] < 0.48 else ye_mantle
    if ocean is not None:
        regions[-1]["coefficients"] = [ocean]
    name = f"prem_ye{ye_mantle}_{ye_core}_ocean{ocean}"
    return f"regions:{crust.write_regions(crust.split(regions, SPLIT_KM), name)}"


def flux_adn(osc, earth_model, site):
    """A^osc_DN in % of the 8B nu_e flux over 0.1-16 MeV (B16-GS98), P_ee as in scan.observables."""
    _, energy, shape = components(load_spec("B5_rates"), "b16_gs98")["B8"]
    keep = (energy >= 0.1) & (energy <= 16)
    energy, shape = energy[keep], shape[keep]
    ue2 = np.abs(pmns(osc)[0]) ** 2
    F = day_fractions(osc, "b16_gs98", energy)
    night_e, night_p = night_probabilities(osc, earth_model, site_latitude(site), site)
    P = np.stack([np.interp(energy, night_e, night_p[:, i], left=ue2[i]) for i in range(3)], axis=-1)
    day, night = np.trapezoid(shape * (F @ ue2), energy), np.trapezoid(shape * np.sum(F * P, axis=1), energy)
    return 100 * 2 * (night - day) / (night + day)


def han():
    osc = oscillation(None, **PDG2025)
    their_1d = regions_model(0.50, 0.467)
    print("Han et al. 2607.24421: A^osc_DN of the 8B nu_e flux (%), PREM at their Ye; 3D shift (pp)")
    print(f"{'site':9} {'1D theirs':>9} {'1D here':>8} {'Delta theirs':>12} {'local crust':>11} {'3D crust':>9}")
    for site in SITES:
        a3d, delta = HAN[site]
        mine_1d = flux_adn(osc, their_1d, site)
        full = flux_adn(osc, "prem_full", site)
        local, chords = (flux_adn(osc, m, site) - full for m in ("prem_crust1", "prem_crust1_3d"))
        print(f"{site:9} {a3d - delta:9.3f} {mine_1d:8.3f} {delta:+12.3f} {local:+11.3f} {chords:+9.3f}")


def _engine(models):
    inputs = engine.Inputs(collect_inputs())
    inputs.data["earth_models"] = list(inputs.data["earth_models"]) + [m for m in models if m.startswith("regions:")]
    return inputs


def bakhti():
    osc = oscillation(None, sin2_theta12=0.307, sin2_theta13=float(np.sin(np.radians(8.4)) ** 2), dm2_21_eV2=7.5e-5)
    rock = regions_model(ocean=2.6)
    models = {"PREM, crust to the surface (theirs)": rock, "PREM (B3, ocean)": "prem_full",
              "PREM + local crust": "prem_crust1", "PREM + crust along each chord": "prem_crust1_3d"}
    inputs, probabilities = _engine(models.values()), ExactProbabilities()
    print("Bakhti & Smirnov 2001.08030: Hyper-K ES, T > 6.5 MeV, 15 % resolution, A_ND = N/D - 1 (theirs: 0.022"
          " with CRUST1.0, ~5 % below PREM)")
    values = {}
    for label, model in models.items():
        setup = engine.Setup(detector="water", channel="es", components=("B8", "hep"), threshold=6.5,
                             resolution_b=0.15, site="Kamioka", earth_model=model, solar_model="b16_gs98")
        day, night, _ = engine.combine(engine.component_totals(inputs, probabilities, setup, osc), list(setup.components))
        values[label] = night / day - 1
    ref = values["PREM, crust to the surface (theirs)"]
    for label, v in values.items():
        print(f"  {label:38} A_ND {v:.4f}  ({100 * (v / ref - 1):+.1f} % against their PREM)")


def sites():
    inputs, probabilities = _engine(()), ExactProbabilities()
    params = engine.parameters(inputs, "juno_2025")
    osc = engine.oscillation(params)
    kinds = {"water ES > 3.49": dict(detector="water", channel="es", components=("B8", "hep"), threshold=3.49),
             "argon CC > 5": dict(detector="argon", channel="cc_nue_ar40", components=("B8",), threshold=5.0,
                                  xsec_model="ar40_marley2_bhattacharya2009")}
    print("Annual A_DN (%), B23-MB22m, JUNO 2025, exact solvers; shifts of the crust models against full PREM")
    for kind, extra in kinds.items():
        for site in SITES:
            adn = {}
            for model in ("prem_full", "prem_crust1", "prem_crust1_3d"):
                setup = engine.Setup(solar_model="b23_mb22m", site=site, earth_model=model, **extra)
                day, night, _ = engine.combine(engine.component_totals(inputs, probabilities, setup, osc),
                                               list(setup.components))
                adn[model] = 100 * engine.quantity_value("adn", "annual", day, night)
            print(f"  {kind:16} {site:9} PREM {adn['prem_full']:.3f}  local crust {adn['prem_crust1']:.3f} "
                  f"({100 * (adn['prem_crust1'] / adn['prem_full'] - 1):+.2f} %)  3D crust {adn['prem_crust1_3d']:.3f} "
                  f"({100 * (adn['prem_crust1_3d'] / adn['prem_full'] - 1):+.2f} %; "
                  f"{100 * (adn['prem_crust1_3d'] / adn['prem_crust1'] - 1):+.2f} % against the local crust)")


def _solve(osc, chords):
    """[E, chord, 3] of P(nu_i -> nu_e) on the B3 exposure energies, chords as earth3d.write_trajectories takes."""
    path = earth3d.write_trajectories(chords, "average_check")
    argv = [f"trajectories:{path}", *(str(osc[k]) for k in ("sin2_theta12", "sin2_theta13", "sin2_theta23",
                                                            "delta_cp_deg", "dm2_21_eV2", "dm2_31_eV2")),
            "0", "1", "20", "0.5", "0", "1", "1"]
    table = np.loadtxt(subprocess.run([str(_nufast_driver()), *argv], capture_output=True, text=True,
                                      check=True).stdout.splitlines())
    energy = table[:, 0].reshape(39, -1)[:, 0]
    return energy, table[:, [2, 5, 8]].reshape(len(energy), len(chords), 3)


def average(site="Kamioka", cells=(0.05, 0.2, 0.4, 0.6, 0.8, 0.9)):
    osc = oscillation("juno_2025")
    ue2 = np.abs(pmns(osc)[0]) ** 2
    near, far, counts = earth3d.averaged_crust(site)
    grid = earth3d.cos_grid()
    print(f"prem_crust1_3d at {site}: crust averaged per cell against P averaged over its chords (4-20 MeV)")
    for c0 in cells:
        k = int(np.argmin(abs(grid - c0)))
        singles = earth3d.direction_chords(site, grid[k] - 0.0005, grid[k] + 0.0005, at=grid[k])
        energy, P = _solve(osc, singles)
        _, mean = _solve(osc, [(grid[k], *earth3d.pieces(*earth3d.chord_profile(grid[k], near[k], far[k])))])
        sel = energy >= 4
        diff = (mean[:, 0, 1] - P.mean(axis=1)[:, 1])[sel]
        regeneration = (P.mean(axis=1)[:, 1] - ue2[1])[sel]
        print(f"  cos {grid[k]:.3f}, {len(singles)} chords: max |dP2e| {np.abs(diff).max():.1e}, mean over the "
              f"regeneration {diff.mean() / regeneration.mean():+.1e}, spread of single chords "
              f"{P[:, :, 1].std(axis=1)[sel].max():.1e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--part", choices=("han", "bakhti", "sites", "average"), action="append")
    parser.add_argument("--site", default="Kamioka", help="for --part average")
    args = parser.parse_args()
    for part in args.part or ("han", "bakhti", "sites"):
        {"han": han, "bakhti": bakhti, "sites": sites, "average": lambda: average(args.site)}[part]()
        print()
