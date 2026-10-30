# Sources

Where every input comes from. The data files themselves carry the same
information next to the numbers (`source`, `retrieved`, `method`,
checksums); this page collects it. The web page shows the sources of each
calculator step behind its "i" button (`web/sources.js`) and lists them all
on its home page.

Which of these inputs are the state of the art, which are legacy and which
are approximations: [status-of-inputs.md](status-of-inputs.md).

Rules for adding data ([reference/README.md](../reference/README.md)):
every file has a source (DOI or arXiv id), the table or figure, the
retrieval date, the method (`table` or `digitised`) and a licence.
Digitised values are flagged in every plot that uses them. Catalogue fields
are filled from the tool's own repository or paper, never from memory.

## Solar models

`reference/ssm/<model>.dat`, `benchmarks/B1_ssm/models.yaml`, written by
`scripts/import_ssm.py` (retrieved 2026-10-28; per-model SHA-256 of the
source file in `models.yaml`).

| Family | Paper | Obtained from |
|---|---|---|
| B16 (GS98, AGSS09met) | Vinyoles et al., ApJ 835, 202 (2017), [arXiv:1611.09867](https://arxiv.org/abs/1611.09867) | [PEANUTS](https://github.com/michelelucente/PEANUTS) `Data/` @ 39ef11f (public B16 tables, `fluxes_b16.dat`) |
| BS05 (OP, AGS-OP) | Bahcall, Serenelli & Basu, ApJ 621, L85 (2005), [astro-ph/0412440](https://arxiv.org/abs/astro-ph/0412440) | PEANUTS `Data/` @ 39ef11f (zone fractions converted to densities) |
| B23 / SF-III (GS98, AGSS09, C11, AAG21, MB22m, MB22p) | Herrera & Serenelli, Standard Solar Models B23 / SF-III v1.2, [doi:10.5281/zenodo.10174172](https://doi.org/10.5281/zenodo.10174172); cite also Magg et al., A&A 661, A140 (2022) and Solar Fusion III, Rev. Mod. Phys. 97, 035002 (2025) | [Zenodo record 10822316](https://zenodo.org/records/10822316), `SolarModels_ICE2023_v1.2.zip` (sha256 382037d7…), CC-BY-4.0 |

B23 provides flux uncertainties and their correlation matrices; B16 provides
uncertainties only; BS05 neither.

## Spectral shapes

`reference/ssm/shapes/`, from PEANUTS `Data/` @ 39ef11f (retrieved
2026-10-28, method `table`), each normalised to unit area by SNUfish.

| Component | Source | Endpoint |
|---|---|---|
| pp | J. N. Bahcall, Phys. Rev. C 56, 3391 (1997) | 0.42341 MeV |
| hep | J. N. Bahcall, Phys. Rev. C 56, 3391 (1997) | 18.784 MeV |
| ⁸B | W. T. Winter et al., Phys. Rev. C 73, 025503 (2006), with shape uncertainty | table truncated at 15.2–15.3 MeV (true ~16.5 MeV) |
| ¹³N | Bahcall & Ulrich, Rev. Mod. Phys. 60, 297 (1988) | 1.199 MeV |
| ¹⁵O | Bahcall & Ulrich (1988) (file header says N13: a copy slip in PEANUTS) | 1.732 MeV |
| ¹⁷F | Bahcall & Ulrich (1988) | 1.740 MeV |
| ⁷Be | lines 861.3 keV (89.56 %), 384.3 keV (10.44 %) | — |
| pep | line 1.442 MeV | — |

## Oscillation parameters

`reference/oscillation/parameter_sets.yaml`. Normal ordering; errors are
1σ, `[minus, plus]`.

| Set | Δm²₂₁ (10⁻⁵ eV²) | sin²θ₁₂ | Source |
|---|---|---|---|
| defaults (θ₁₃, θ₂₃, δ, Δm²₃₁) | — | — | NuFIT 6.0, [arXiv:2410.05380](https://arxiv.org/abs/2410.05380), table 1 (IC19 w/o SK-atm, NO) |
| `nufit61_global` | 7.530 −0.097 +0.096 | 0.3096 −0.0073 +0.0057 | NuFIT 6.1 with the first JUNO data, [arXiv:2601.09791](https://arxiv.org/abs/2601.09791), eq. 3.1 |
| `nufit60_global` | 7.49 ± 0.19 | 0.307 −0.011 +0.012 | NuFIT 6.0 |
| `juno_2025` | 7.50 ± 0.12 | 0.3092 ± 0.0087 | JUNO, [arXiv:2511.14593](https://arxiv.org/abs/2511.14593) (59 days) |
| `kamland_2013` | 7.54 −0.18 +0.19 | 0.316 −0.026 +0.034 | KamLAND, Phys. Rev. D 88, 033001 (2013), as quoted in arXiv:2312.12907 fig. 47 |
| `solar_global_2024` | 6.10 −0.81 +0.95 | 0.306 ± 0.013 | Super-K, [arXiv:2312.12907](https://arxiv.org/abs/2312.12907), all solar |
| `sk_sno_2024` | 6.10 −0.75 +1.04 | 0.305 ± 0.014 | Super-K, arXiv:2312.12907, SK + SNO |
| `solar_kamland_2024` | 7.50 −0.18 +0.19 | 0.307 ± 0.012 | Super-K, arXiv:2312.12907, solar + KamLAND |

The calculator's published checks add the parameter values stated by each
paper they reproduce (`PAPER_SETS` in `web/checks.js`).

## Earth

| Input | Source |
|---|---|
| PREM | Dziewonski & Anderson, Phys. Earth Planet. Inter. 25, 297 (1981) |
| `prem_prob3`, `prem_four`, `prem_full` | copied from NuFast-Earth `src/Earth.cpp` @ 327586d |
| Yₑ = 0.466 (core), 0.494 (mantle) | hep-ph/0002149, as in NuFast-Earth |
| Night exposure W(η; λ) | Lisi & Montanino, [hep-ph/9702343](https://arxiv.org/abs/hep-ph/9702343), table II, as implemented in NuFast-Earth `src/Solar.cpp` |
| Kamioka 36.48°, LNGS 42.45°, SNOLAB 46.47° | hep-ph/9702343, fig. 3 |
| SURF 44.356° | [arXiv:1707.02322](https://arxiv.org/abs/1707.02322), table 1 |
| Jiangmen 22.12° | JUNO site; 22° N in [arXiv:2006.11760](https://arxiv.org/abs/2006.11760) sec. 2.1 (the hundredths not yet checked) |

## Cross sections

| Channel | Model | Source |
|---|---|---|
| ES, all flavours | tree level, sin²θ_W = 0.23857 | Standard Model; PDG 2024 (SNUfish reference, B4) |
| ES, all flavours | BKS radiative corrections | Bahcall, Kamionkowski & Sirlin, PRD 51, 6146 (1995), [astro-ph/9502003](https://arxiv.org/abs/astro-ph/9502003), appendices A and B |
| ES, all flavours | SNOwGLoBES tables (from 0.5 MeV) | [SNOwGLoBES](https://github.com/SNOwGLoBES/snowglobes) `xscns/` |
| νₑ ⁴⁰Ar CC | KLMV | Kolbe, Langanke, Martínez-Pinedo & Vogel, as tabulated by SNOwGLoBES (`xs_nue_Ar40_klmv.dat`) |
| νₑ ⁴⁰Ar CC | MARLEY (SNOwGLoBES 2018 tables, zero below 5 MeV) | [arXiv:2101.11867](https://arxiv.org/abs/2101.11867); B(GT): Bhattacharya et al., PRC 80, 055501 (2009) (`marley`), ⁴⁰Ti β decay (`marley1`; SNOwGLoBES does not say which measurement) |
| νₑ ⁴⁰Ar CC | MARLEY 2.0.0 (HF-CRPA + measured B(GT)) | MARLEY 2.0.0 (31 July 2026), [doi:10.5281/zenodo.21880925](https://doi.org/10.5281/zenodo.21880925); Gardiner, PRC 103, 044604 (2021); B(GT): Bhattacharya 2009, Liu et al. PRC 58, 2677 (1998), Bhattacharya et al. PRC 58, 3677 (1998) |
| νₑ ¹⁶O, ¹³C CC | SNOwGLoBES tables | SNOwGLoBES `xscns/` |
| νₑ d CC, ν d NC | Nakamura et al., Nucl. Phys. A 707, 561 (2002), [nucl-th/0201062](https://arxiv.org/abs/nucl-th/0201062), table 1 (AV18, ±1 %) | `reference/xsec/nakamura2002.yaml`; SNOwGLoBES's `xs_nue_d.dat` is the same table from 5 MeV |

SNOwGLoBES tables were taken from the fork
`github.com/mantheys/snowglobes` @ 6fa928e; MARLEY from its v2.0.0 tag.

## Detectors

Targets per kiloton:

| Detector | Targets per kt | Source |
|---|---|---|
| `argon` | 2.71349 × 10³² e⁻, 1.50146 × 10³¹ ⁴⁰Ar | natural argon, 99.60 % ⁴⁰Ar, M = 39.948 g/mol (B5 spec) |
| `water` | 3.34285 × 10³² e⁻, 3.33472 × 10³¹ ¹⁶O | H₂O, M = 18.015 g/mol, 99.757 % ¹⁶O (B5 spec) |
| `scintillator_pc` | 3.307 × 10³² e⁻ | Borexino pseudocumene + PPO, [arXiv:1707.09279](https://arxiv.org/abs/1707.09279) |
| `scintillator_lab` | 3.38 × 10³² e⁻ | JUNO LAB, arXiv:2006.11760 |
| `heavy_water` | 3.007 × 10³² e⁻, 6.014 × 10³¹ d | D₂O, 99.92 % isotopic purity ([arXiv:1109.0763](https://arxiv.org/abs/1109.0763)), M = 20.03 g/mol |

Calculator presets (`PRESETS` in `web/app.js`), from published numbers
only:

| Preset | Source | What it sets |
|---|---|---|
| Super-K IV | arXiv:2312.12907 | 22.5 kt, 2970 days, 3.49 MeV kinetic threshold, resolution eq. 9, fig. 28 efficiency, scale ±0.48 %, resolution ±3 %, rate ±1.1 %, SNO NC ⁸B flux |
| Hyper-K (one tank) | [arXiv:1805.04163](https://arxiv.org/abs/1805.04163) | 187 kt, 10 years, 4.5 MeV, scale ±0.5 %, resolution ±0.6 % (Super-K IV's resolution as a stand-in) |
| DUNE far detector | [arXiv:2008.06647](https://arxiv.org/abs/2008.06647), [arXiv:1808.08232](https://arxiv.org/abs/1808.08232) | 40 kt LAr, 100 kt·yr, 5 MeV, 20 % resolution, MARLEY 2 |
| SNO phases I + II | arXiv:1109.0763 | 770 t D₂O, 3.5 MeV, 277.3 + 391.4 days, scale ±0.41 % |
| SNO salt | [nucl-ex/0502021](https://arxiv.org/abs/nucl-ex/0502021) | φ_CC/φ_NC above 5.5 MeV, 391.4 days |
| Borexino Phase-II | arXiv:1707.09279 | 71.3 t, 1291.51 days, all recoil energies, ~5 %/√E |
| JUNO ⁸B | arXiv:2006.11760 | 2 MeV, 3 %/√E, scale ±0.3 %, efficiency ±1 %, SNO NC ⁸B flux |

Efficiency curves (`reference/detectors/efficiency_curves.yaml`):

| Curve | Source | Method |
|---|---|---|
| `sk4_final` | Super-K IV final sample, arXiv:2312.12907 fig. 28 | marker positions read from the figure's vector PostScript in the arXiv source (`096.eps`): exact to the drawing precision (0.08 % in efficiency), axes calibrated on the tick marks |

## Measurements

`reference/measurements/solar.yaml`:

| Entry | Measurement | Source |
|---|---|---|
| `sk_day_night` | Super-K ⁸B ES A_DN = −2.86 ± 0.85 (stat) ± 0.32 (syst) % in SK convention, all phases, 3.49 MeV kinetic threshold | arXiv:2312.12907, sec. VIII |
| `sk_sno_pee_quadratic` | daytime ⁸B P_ee(E) = c₀ + c₁(E − 10) + c₂(E − 10)², c = (0.308, −0.0044, 0.0016), with errors and correlations, valid 3–15 MeV | arXiv:2312.12907, table VIII |
| `borexino_rates` | pp 134, ⁷Be 48.3, pep 2.43 cpd/100 t with errors, inverse covariance, and Borexino's B16-GS98 predictions | arXiv:1707.09279, table II (Nature 562, 505 (2018)); covariance as used in arXiv:2312.12907 sec. VII D |
| `sno_cc_nc` | φ_CC/φ_NC = 0.340 ± 0.023 (stat) −0.031 +0.029 (syst), T_eff > 5.5 MeV | nucl-ex/0502021, sec. XI |
| `sk4_events` | 65,443 ⁸B + hep ES events in 3.49–19.49 MeV, 22.5 kt, 2970 days | arXiv:2312.12907, sec. V B |
| measured ⁸B flux | 5.25 × 10⁶ cm⁻² s⁻¹ ± 3.81 % (SNO NC, as Super-K applies it) | arXiv:2312.12907, fig. 42 (`B8_MEASURED` in `snufish/export.py`) |

## Tools

`catalogue/tools/<tool>.yaml`:

| Tool | Benchmarks | Version used | Status |
|---|---|---|---|
| [SNUfish reference](../catalogue/tools/snufish-reference.yaml) | B2, B3, B4 | 0.1.0 | verified |
| [NuFast-Earth](https://github.com/PeterDenton/NuFast-Earth) (Denton & Parke, [arXiv:2511.04735](https://arxiv.org/abs/2511.04735)) | B2, B3 | 1.2.0-3-g327586d (git submodule) | verified |
| [SNOwGLoBES](https://github.com/SNOwGLoBES/snowglobes) | B4, B5 | git 6fa928e | verified |
| [MARLEY](https://github.com/MARLEY-MC/marley) ([arXiv:2101.11867](https://arxiv.org/abs/2101.11867)) | B4 | 2.0.0 | verified |
| nuSQuIDS | B2, B3 (planned) | — | draft entry, no contribution |
| PEANUTS ([arXiv:2303.15527](https://arxiv.org/abs/2303.15527)) | B1, B2, B3 (planned) | — | draft entry, no contribution (its data directory supplies the B16 and BS05 tables) |

Notes on each tool's wrapper (what it computes, what it assumes) are in
its catalogue entry and in `contributions/<tool>/scripts/`.

## Software

| Package | Used for |
|---|---|
| [plotipus](https://github.com/mantheys/plotipus) | figures (command line and in the browser) |
| NumPy, pandas, PyArrow, PyYAML | the Python package |
| [Plotly.js](https://plotly.com/javascript/) | interactive figures in the page |
| [Pyodide](https://pyodide.org) | plotipus in the browser |
| [hyparquet-writer](https://github.com/hyparam/hyparquet-writer), [fflate](https://github.com/101arrowz/fflate) | Parquet and zip downloads |
