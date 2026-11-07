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
| Sun | production at one density, ρY<sub>e</sub> = 90 g/cm³ | the ⁸B (hep) production profile: SOLAR's choice is −0.6 % on CC, −0.4 % on ES |
| Earth | NuFast-Earth through a Python binding outside SOLAR's repository: **density model not known** | `prem_full` (or `prem_crust1`) |
| Night | 1.478 km deep, latitude 44.35°, W(η) sampled at 80 night bins | `ExactProbabilities(night_mode="solar")`; +0.02 % on rates, +1 % on A<sub>DN</sub> against B3's night |
| Exposure | day 0.493, night 1 − 0.493 (a constant, not from the latitude) | `night_fraction=0.507`: +0.03 % on rates |
| Targets | 1 kt × N<sub>A</sub> / 39.948 = 1.508 × 10³¹ ⁴⁰Ar | 1.501 × 10³¹ (natural argon, 99.60 % ⁴⁰Ar): −0.4 % |
| Year | 365.25 d in `lib/weights.py`, 365 d in two other scripts | 365.25 d |
| CC cross section | `neutrino_cc_final.txt` (CIEMAT /pnfs, `DUNE/SOLAR/data/SOLAR/`), 1 MeV steps from 4.5 MeV: MARLEY's v1 reaction file in the allowed approximation (no form factors), equal to `ar40_marley1_allowed` (`marley xsec` with `"form_factors": "allowed"`) to all six printed digits; 2.8 to 7.6 % above `ar40_marley1_bhattacharya2009` (MARLEY 2.0.0's default form factors) at 6 to 14 MeV | `ar40_marley1_allowed` |
| Signal samples | MARLEY v1.2.1 (`marley v1_2_1d`, via larsim v09_44_02 in dunesw v09_91_04), `ve40ArCC_Bhattacharya2009.react` (`prodmarley_nue_cc_flat_*.fcl`) | `ar40_marley1_allowed`: the same reaction file and cross section, run by MARLEY 2.0.0 |

SOLAR contains no SNOwGLoBES table, script or ES/NC rate. Its MARLEY signal samples are normalised with
SOLAR's own flux × `neutrino_cc_final.txt` integral (the `*_exposure.pkl` counts; the script that writes them
is not in the repository), not with a SNOwGLoBES rate. Its sensitivity fit uses a closed-form pull χ² by
default; iminuit appears only in the legacy `Sensitivity_Fitter` path and the vertex fit.

## Rates

Per kt-yr, annual, ⁸B + hep, `--earth prem_full`, SOLAR's night:

| Channel | above | 5 MeV | 8 MeV | 10 MeV | 15 MeV |
|---|---|---|---|---|---|
| CC `ar40_marley` (SNOwGLoBES 2018 table) | E<sub>ν</sub> | 1552 | 1331 | 818 | 2.61 |
| CC `ar40_marley1_allowed` (MARLEY v1.2.1, DUNE's samples, SOLAR) | E<sub>ν</sub> | 2416 | 2041 | 1253 | 3.95 |
| CC `ar40_marley1_allowed` | T<sub>e</sub> | 1210 | 144 | 12.6 | 0 |
| CC `ar40_marley1_bhattacharya2009` (v1 file, MARLEY 2's form factors) | E<sub>ν</sub> | 2306 | 1942 | 1186 | 3.61 |
| CC `ar40_marley2_bhattacharya2009` (MARLEY 2) | E<sub>ν</sub> | 2267 | 1903 | 1151 | 3.46 |
| CC `ar40_marley2_bhattacharya2009` | T<sub>e</sub> | 1140 | 132 | 11.4 | 0 |
| ES (BKS) | E<sub>ν</sub> | 1081 | 610 | 276 | 0.387 |
| ES (BKS) | T<sub>e</sub> | 360 | 93.0 | 22.6 | 0.0174 |
| NC (SNOwGLoBES table) | E<sub>ν</sub> | 28.8 | 28.8 | 26.5 | 0.161 |
| *thesis CC* | *E<sub>ν</sub>* | *2380* | *1990* | *1200* | *3.77* |
| *thesis CC* | *T<sub>e</sub>* | *1150* | *156* | *8.36* | – |
| *thesis ES* | *E<sub>ν</sub>* | *1080* | *599* | *265* | *0.384* |
| *thesis ES* | *T<sub>e</sub>* | *358* | *90.9* | *21.7* | *0.0168* |
| *thesis NC* | *E<sub>ν</sub>* | *27.7* | *27.7* | *25.3* | *0.17* |

Above 15 MeV the ⁸B shape stops at 15.2 MeV ([status.md](status.md#known-approximations)): the 15 MeV
column is hep plus the last 0.2 MeV of ⁸B: it is not a reliable comparison.

**What the thesis table used.** `LOWE_RECONSTRUCTION_PUBLICATION/scripts/generate_snowglobes_solar_interactions.py`,
model `marley2009` (the thesis's macros say so: `references/metrics/main.tex`). Every difference from SNUfish with
SOLAR's settings is accounted for. From `ar40_marley1_bhattacharya2009` (CC above E<sub>ν</sub> = 5 MeV, 2306 → 2384,
+3.4 %; from `ar40_marley1_allowed`, 2416 → 2384, −1.3 %):

| Step | Factor |
|---|---|
| day only (SNOwGLoBES's P<sub>ee</sub> has no Earth) | −2.1 % |
| P<sub>ee</sub> of SNOwGLoBES's `solar_bs05op_mixed.dat` (θ₁₃ = 0, BS05 parameters) instead of SOLAR's | +2.6 % |
| all argon as ⁴⁰Ar, 365 d | +0.3 % |
| cross section in the allowed approximation (`ar40_marley1_allowed`: SOLAR's file, MARLEY v1) | +4.7 % |
| ⁸B shape of Bahcall et al. 1996 (mean 6.735 MeV) instead of Winter et al. 2006 (6.77 MeV) | −2.1 % |

The ⁸B shape alone gives the thesis's NC (28.9 → 27.65, −4.3 %). Its CC column is not SNOwGLoBES's MARLEY table
(`ar40_marley` is 35 % lower). ES agrees to +0.1 to +4 % (E<sub>ν</sub>) and +0.5 to +4 % (T<sub>e</sub>): fluxes, oscillation and
exposure are the same. SNOwGLoBES's NC table has negative values at 8–9 MeV, which both set to zero.

**Not reproduced.** The thesis's CC T<sub>e</sub> column (1150, 156, 8.36 above 5, 8, 10 MeV) does not follow the same
ladder: `ar40_marley1_allowed` with its own levels gives 1210, 144 and 12.6 (about 1193, 142, 12.4 with the thesis's
conventions): 4 % above the thesis above 5 MeV, 9 % below above 8 MeV, 48 % above above 10 MeV. The electron spectrum behind the
thesis column is not known.

## Phase I paper

`python scripts/dune_phase1_rates.py --out <dir>` writes the raw rates the DUNE solar Phase I paper quotes, with
SOLAR's settings (the table above) and the CC cross section of DUNE's MARLEY samples and of SOLAR,
`ar40_marley1_allowed` (`--cc-model` to change it; MARLEY 2 is −6.2 %). Its T<sub>e</sub> cut takes the ⁴⁰K level shares of
the v1 reaction file's 15 measured levels (below 8 MeV), which carry all of its cross section at solar energies (a
model without levels takes MARLEY 2's).

- `snufish_rates.tex`: one macro per rate, `\snufishRate<CC|ES|NC><Enu|Te><One|Five>`, e.g.
  `\snufishRateCCTeFive` → $1.21\times10^{3}$, plus `\snufishVersion` and `\snufishCommit`;
- `snufish_rates_table.tex`: the booktabs tabular for the paper's appendix table;
- `snufish_rates.json`: day, night and annual rates with the settings and the SNUfish version.

The paper `\input`s the two `.tex` files; `tests/test_dune_phase1_rates.py` pins the values, so a change of any input
that moves a quoted number fails the tests before it reaches the paper.

Annual, per kt-yr, ⁸B + hep, `ar40_marley1_allowed`:

| Cut | CC | ES | NC |
|---|---|---|---|
| E<sub>ν</sub> > 1 MeV | 2426 | 1281 | 28.8 |
| E<sub>ν</sub> > 5 MeV | 2416 | 1081 | 28.8 |
| T<sub>e</sub> > 5 MeV | 1210 | 360 | – |

**The paper's appendix A (CC 482, ES 141, NC 18.8 above E<sub>ν</sub> = 1 MeV) is wrong.** It was made on 2026-09-09 by an
intermediate version of `LOWE_RECONSTRUCTION_PUBLICATION/scripts/generate_snowglobes_solar_interactions.py` that took
SNOwGLoBES's `fluxes/solar_b16gs98_mixed.dat` as its flux. That file, built by hand for the analysis, is not a flux: its
header reads "Solar neutrino CC interaction spectrum … P_ee(E) taken from solar_bs05op_mixed.dat, cross-section from
xs_nue_Ar40_marley.dat", it holds 1531 CC events in the ν<sub>e</sub> column and nothing in the others. Folding it again
applies P<sub>ee</sub> twice: 1531 × ⟨P<sub>ee</sub>⟩ = 495 for CC (482 in the paper; the file was rebuilt on 2026-09-13), and NC gets
(1 + P<sub>ee</sub>)/2 = 0.66 of the true rate (0.68 in the paper); ES (141) is not explained in detail. The table's first version (2026-09-09, before the change)
had CC 1530 and NC 27.7, as the generator in that repository gives today with B16-GS98 component spectra (CC with
SNOwGLoBES's MARLEY table; ES there is all components, 1.67 × 10⁴, against ⁸B + hep here). Replace the appendix table
with `snufish_rates_table.tex`.
