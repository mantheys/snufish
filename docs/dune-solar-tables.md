# DUNE solar rate tables in SOLAR's conventions

`python scripts/dune_solar_tables.py` gives the CC, ES and NC rates on argon that DUNE solar analyses
quote (a thesis ch. 3 table and the DUNE solar Phase I paper), with the assumptions of the SOLAR analysis
code (github.com/CIEMAT-Neutrino/SOLAR at ce5721f). The tables these analyses quote were labelled
SNOwGLoBES; this page compares them with SNUfish.

## SOLAR's assumptions

From SOLAR's `config/analysis/physics.json` and `lib/`, as checked on 2026-10-31:

| Item | SOLAR | SNUfish here |
|---|---|---|
| Fluxes | B16-GS98, ⁸B 5.46 × 10⁶, hep 7.98 × 10³ cm⁻² s⁻¹ | the same |
| Oscillation | Δm²₂₁ 6 × 10⁻⁵ eV², sin²θ₁₂ 0.304, sin²θ₁₃ 0.022 (Δm²₃₁ 2.515 × 10⁻³ is never passed to the solver) | the same |
| Sun | production at one density, ρY_e = 90 g/cm³ | the ⁸B (hep) production profile: SOLAR's choice is −0.6 % on CC, −0.4 % on ES |
| Earth | NuFast-Earth through a Python binding outside SOLAR's repository: **density model not known** | `prem_full` (or `prem_crust1`) |
| Night | 1.478 km deep, latitude 44.35°, W(η) sampled at 80 night bins | `ExactProbabilities(night_mode="solar")`; +0.02 % on rates, +1 % on A_DN against B3's night |
| Exposure | day 0.493, night 1 − 0.493 (a constant, not from the latitude) | `night_fraction=0.507`: +0.03 % on rates |
| Targets | 1 kt × N_A / 39.948 = 1.508 × 10³¹ ⁴⁰Ar | 1.501 × 10³¹ (natural argon, 99.60 % ⁴⁰Ar): −0.4 % |
| Year | 365.25 d in `lib/weights.py`, 365 d in two other scripts | 365.25 d |
| CC cross section | an external file, `neutrino_cc_final.txt` on /pnfs, model not stated | three tables, below |

SOLAR contains no SNOwGLoBES table, script or ES/NC rate. Its MARLEY signal samples are normalised with
SOLAR's own flux × `neutrino_cc_final.txt` integral (the `*_exposure.pkl` counts; the script that writes them
is not in the repository), not with a SNOwGLoBES rate. Its sensitivity fit uses a closed-form pull χ² by
default; iminuit appears only in the legacy `Sensitivity_Fitter` path and the vertex fit.

## Rates

Per kt-yr, annual, ⁸B + hep, `--earth prem_full`, SOLAR's night:

| Channel | above | 5 MeV | 8 MeV | 10 MeV | 15 MeV |
|---|---|---|---|---|---|
| CC `ar40_marley` (SNOwGLoBES 2018 table) | E_ν | 1552 | 1331 | 818 | 2.61 |
| CC `ar40_marley1_bhattacharya2009` (MARLEY v1 model) | E_ν | 2306 | 1942 | 1186 | 3.61 |
| CC `ar40_marley2_bhattacharya2009` (MARLEY 2) | E_ν | 2267 | 1903 | 1151 | 3.46 |
| CC `ar40_marley2_bhattacharya2009` | T_e | 1140 | 132 | 11.4 | 0 |
| ES (BKS) | E_ν | 1081 | 610 | 276 | 0.387 |
| ES (BKS) | T_e | 360 | 93.0 | 22.6 | 0.0174 |
| NC (SNOwGLoBES table) | E_ν | 28.8 | 28.8 | 26.5 | 0.161 |
| *thesis CC* | *E_ν* | *2380* | *1990* | *1200* | *3.77* |
| *thesis CC* | *T_e* | *1150* | *156* | *8.36* | – |
| *thesis ES* | *E_ν* | *1080* | *599* | *265* | *0.384* |
| *thesis ES* | *T_e* | *358* | *90.9* | *21.7* | *0.0168* |
| *thesis NC* | *E_ν* | *27.7* | *27.7* | *25.3* | *0.17* |

Above 15 MeV the ⁸B shape stops at 15.2 MeV ([status.md](status.md#known-approximations)): the 15 MeV
column is hep plus the last 0.2 MeV of ⁸B: it is not a reliable comparison.

**What the thesis table used.** Its CC column is not SNOwGLoBES's MARLEY table (`ar40_marley` is 35 % lower)
but a MARLEY calculation with the Coulomb factor: `ar40_marley1_bhattacharya2009` is within −3.1, −2.4, −1.2 %
of it above E_ν = 5, 8, 10 MeV. ES agrees to +0.1 to +4 % (E_ν) and +0.5 to +4 % (T_e): fluxes, oscillation and
exposure are the same. NC has the thesis's shape but is 4–5 % higher; SNOwGLoBES's table has negative values at
8–9 MeV, which SNUfish sets to zero (kept, the rate above 5 MeV falls to 26.6, below the thesis).

**Not reproduced.** The thesis's CC T_e column agrees above 5 MeV (−0.9 %) but not above 8 and 10 MeV (156 and
8.4 against 132 and 11.4 with MARLEY 2's levels, 134 and 11.7 with MARLEY v1's): the level distribution behind it is
not known. The paper's appendix A (CC 482, ES 141, NC 18.8 per kt-yr above E_ν = 1 MeV) is 0.21 (CC), 0.11 (ES) and
0.65 (NC) times SNUfish's rates above 1 MeV (2314, 1281, 28.8): no single factor (units, mass, exposure,
oscillation) explains three different ratios, and NC above 1 MeV cannot be below NC above 5 MeV (27.7).
