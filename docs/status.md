# Status: missing pieces, limitations and open questions

All benchmark specs are drafts. This page lists what is not implemented,
what is approximate, and what has to be decided before the specs are
frozen. It is the to-do list for contributors: pick an item, and say so in
an issue.

## Not implemented

### Benchmarks

| Item | Where | Notes |
|---|---|---|
| **D: detector response library** | `benchmarks/README.md` | Smearing, efficiency and thresholds per detector as a benchmark of their own. The engine has a generic response (Gaussian or Super-K resolution, logistic or imported efficiency, imported smearing matrices) and one published curve (Super-K IV), but no contributed or validated detector responses. |
| **Night and annual rates in B5** | B5 spec | B5 folds daytime oscillations only; the night (from B3) is in the engine and the calculator but not in the benchmark or its products. |
| **Observed spectra in B5** | B5 spec | B5 rates are in true neutrino energy before detector response; observed spectra wait for D. |
| **Converged reference for continuous Earth models** | B3 spec | The reference is exact for piecewise-constant shells (`prem_prob3`) only. `prem_four` and `prem_full` have one contribution (NuFast-Earth) and no reference to compare it with; a converged sliced solution is planned. |
| **Non-adiabatic Sun solver** | B2 spec | A validated solver (e.g. adiabatic-basis integration with phase averaging) to measure the O(1/γ²) corrections the adiabatic reference neglects. |
| **Radiative corrections in the B4 reference** | B4 spec | BKS is implemented (`snufish.reference.radiative`) and used by the engine, but the `snufish-reference` B4 contribution is tree level only. |
| **ES with recoil thresholds in B4** | B4 spec | σ(E; T > T_min) for detector thresholds is not a benchmark quantity (the engine computes it). |
| **Spectral-shape variants** | B1 spec | The Ortiz et al. ⁸B shape and the ⁷Be line widths as shape variants; all solar models share one set of shapes now. |
| **B1 checks in the validator** | B1 spec | B1 has no contributions; its checks (profile normalisation, falling density) run in `tests/test_ssm.py`, not in `snufish validate`. |
| **B1 flux correlations in B5** | B1 spec | The B23 correlation matrices are used by `snufish budget` and the engine, not by the B5 build. |

### Tools

| Tool | Status |
|---|---|
| nuSQuIDS | catalogue entry only (draft, fields `null`); no B2 or B3 contribution |
| PEANUTS | catalogue entry only (draft, fields `null`); no contribution, although its data directory supplies the B16 and BS05 tables |
| SNUfish reference | no repository URL in its catalogue entry until the repository is public |
| Full-chain rate tools other than SNOwGLoBES | none yet |
| Other cross-section models | no alternatives for ¹⁶O (SNOwGLoBES only); ¹³C CC is in B4 but no detector or engine channel uses it; no NC on ⁴⁰Ar or ¹⁶O |
| More ⁴⁰Ar shell-model tables | Kostensalo, Suhonen & Zuber (2018) is in (a published table, 5 MeV steps); Suzuki & Honma (2013) / Suzuki & Shimizu (2023) publish no σ(E) table, only a folded value (reproduced by MARLEY 2 to 3 %). A finer KSZ table, or σ(E) from the Suzuki group, would remove the 3 % interpolation error and add a calculation ([status-of-inputs.md](status-of-inputs.md)) |
| Tomalak & Hill ES cross section | the most precise ν–e calculation (0.2–0.4 %); BKS and Marciano & Parsa bound it at the solar precision |
| 3D Earth | `prem_crust1` puts the CRUST1.0 column of each site above PREM's Moho, but stays radial. Next: per night direction (the Sun's position over a year at the site's latitude and longitude), the chord's entry point and its CRUST1.0 column, solved with NuFast-Earth's single-trajectory mode, and a 3D mantle model; then a second current Earth model, and an Earth range. Until then the Earth range is empty (one state-of-the-art model) |

### Physics scope

- **Normal ordering and neutrinos only.** No inverted ordering, no
  antineutrinos (B2 and B3 state `neutrinos_only`).
- **Standard three-flavour oscillations only.** No sterile neutrinos,
  non-standard interactions or decay.
- **No correlations between oscillation parameters.** They are sampled
  independently: no source publishes them.
- **No backgrounds.** Statistical errors are Poisson on the signal alone.
- **Equal day and night exposure.** The annual rate is (D + N)/2 and the
  statistics split the exposure in halves, at every latitude.
- **Earth–Sun distance optional, as day and night averages only.** By
  default fluxes are at 1 AU (the convention of published A_DN);
  `Setup(orbit=True)` scales day and night rates by the site's mean
  (1 AU/R)² ([crosschecks.md](crosschecks.md#earthsun-distance)). Not
  modelled: deeper nights near perihelion (< 0.2 % of A_DN), time-resolved
  seasonal spectra, and the 3D Earth (radial PREM variants only).
- **PREM ends in 3 km of ocean.** The B3 detector sits in it, which
  under-predicts A_DN at continental sites; a crust variant exists only in
  an investigation driver ([crosschecks.md](crosschecks.md#investigated)).
- **Detector at the surface.** B3 sets the detector depth to 0.
- **CC visible energy is E_ν − Q** with no neutron, binding or quenching
  losses; NC on deuterium deposits 6.25 MeV (capture on ²H in pure D₂O),
  so SNO's salt phase (capture on ³⁵Cl) is not modelled for NC.
- **Radial path out of the Sun.** Irrelevant while propagation is
  adiabatic; the reference does not measure the effect yet.

## Known approximations

| Approximation | Size | Where |
|---|---|---|
| Adiabatic F_i in B2 | O(10⁻⁶) for the B2 parameters | `reference/sun.py` |
| App tables instead of exact solvers | 2 × 10⁻⁴ (rates), 1 % (A_DN) | `engine.TableProbabilities` |
| θ₁₃ in the app tables followed by ν₃ decoupling | within 1.6 % of the exact A_DN over sin²θ₁₃ = 0.015–0.03 | `engine.TableProbabilities` |
| ⁸B shape truncated at 15.2 MeV (true endpoint ~16.5 MeV) | ~10⁻⁴ of the flux; matters above 15 MeV (⁸B background to hep) | `reference/ssm/shapes/` |
| B16 and BS05 density beyond 0.5 R_☉ | exponential tail fit, residual ≤ 0.0033 in log₁₀ n_e | `models.yaml` `tail` |
| Cross sections below the B4 grid (0.02 MeV) | < 0.01 % of any rate | B5 spec |
| NaN in a cross-section table counted as zero | a lower bound; `Coverage` reports the covered fraction | build, engine |
| BKS QED end-point divergence clipped | last ~10⁻³ of the recoil range | `reference/radiative.py` |
| Super-K IV efficiency read from a figure | 0.08 % in efficiency | `reference/detectors/efficiency_curves.yaml` |
| Hyper-K resolution | Super-K IV's as a stand-in | calculator preset |
| SNO resolution and efficiencies | not included (the paper gives only extra smearing terms) | calculator preset |
| JUNO preset | no energy-dependent fiducial volume, muon-veto dead time or non-linearity | calculator preset |

## Data to check

- Jiangmen latitude 22.12°: the JUNO paper gives 22° N; the hundredths are
  not yet checked against a source.
- SNOwGLoBES's 2018 MARLEY table is 35–40 % low at 8–14 MeV: it appears
  to lack the Coulomb (Fermi) factor ([crosschecks.md](crosschecks.md#investigated)).
  It stays selectable and is kept out of the ⁴⁰Ar model range (it is also
  zero below 5 MeV).

## Published numbers not reproduced

From [crosschecks.md](crosschecks.md):

- Super-K's expected A_DN for the SK-I range at Δm²₂₁ = 4.8 × 10⁻⁵ eV²:
  −3.84 % published, −3.32 % here (13.5 % off) while 6.1 and
  7.5 × 10⁻⁵ eV² agree to 2.5 %; Super-K's own 2014 paper expects −3.3 %
  there, as SNUfish does.
- Capozzi, Li, Zhu & Beacom's DUNE CC A_DN at 4.85 × 10⁻⁵ eV²: −7.90 %
  published, −6.87 % here; the ten- and four-region PREM bracket it.
- JUNO's −1.6 % expected A_DN at 7.5 × 10⁻⁵ eV² in its text, against
  −1.4 % from its own table 1 and −1.38 % here.

## Open questions before freezing the specs

- **B3**: which reference for the continuous Earth models? Extend the
  energy grid down to 0.1 MeV for pp and ⁷Be (Earth effects are tiny
  there)?
- **B4**: add σ(E; T > T_min) for the detectors' ES thresholds? Put BKS in
  the reference?
- **B5**: take the full Winter et al. ⁸B tail before using rates above
  15 MeV; add night and annual rates per site; add observed spectra once D
  exists.
- **B1**: shape variants; use the B23 correlations in B5 rate
  uncertainties.
- **B2**: a non-adiabatic solver; radial path against the true line of
  sight for off-centre production.

## Housekeeping

- CI runs the tests, validation, build and the `b1`, `b2`, `b3`, `b45`
  plots. It does not build the NuFast-Earth driver, so the tests that need
  it or the app tables (`test_engine.py` table tests, the scan,
  `test_web_engine.py`) are skipped there, and `scan`, `budget` and
  `export-app` are not exercised.
- No release on PyPI; the package version is 0.1.0.
