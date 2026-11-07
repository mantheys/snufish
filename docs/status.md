# Status: missing pieces, limitations and open questions

All benchmark specs are drafts. This page lists what is not implemented,
what is approximate, and what has to be decided before the specs are
frozen. It is the to-do list for contributors: pick an item, and say so in
an issue.

## Not implemented

### Benchmarks

| Item | Where | Notes |
|---|---|---|
| **Part 2 contributions to B5** | B5 spec | The spec takes observed rates with the published responses or a tool's own (`response.parquet`), and SNUfish folds every published response (`B5_Observed`), but no tool has contributed yet. SNOwGLoBES's smeared output would be the first, with its own detector configurations (matrices in neutrino energy, also for ES, which the engine's imported matrices take for CC only). |
| **Night and A<sub>DN</sub> in B5 part 2** | B5 spec | Observed spectra are daytime; the engine has night and A<sub>DN</sub> through any response, the benchmark does not. |
| **Night and annual rates in B5 contributions** | B5 spec | SNUfish's folding has them (`B5_DayNight`, per site and Earth model); B5 contributions (full-chain tools) are daytime only. |
| **Non-adiabatic Sun solver** | B2 spec | A validated solver (e.g. adiabatic-basis integration with phase averaging) to measure the O(1/γ²) corrections the adiabatic reference neglects. |
| **ES with recoil thresholds in B4** | B4 spec | σ(E; T > T<sub>min</sub>) for detector thresholds is not a benchmark quantity (the engine computes it). |
| **Spectral-shape variants** | B2 spec | The Ortiz et al. ⁸B shape and the ⁷Be line widths as shape variants; all solar models share one set of shapes now. |
| **Solar-model flux correlations in B5** | B2 spec | The B23 correlation matrices are used by `snufish budget` and the engine, not by the B5 build. |

### Tools

| Tool | Status |
|---|---|
| PEANUTS | B2 (every solar model) and B3 `prem_prob3`. Not `prem_four`, `prem_full`: its Earth models are even polynomials in r and PREM's have odd powers. Not `native`: on non-constant shells its analytical evolutor is first order and breaks unitarity by up to 10⁻³. Its hard-coded matter potential is 3.6 × 10⁻⁴ (Sun) and 1.8 × 10⁻⁵ (Earth) above the specs' constants ([crosschecks.md](crosschecks.md#peanuts-and-nusquids)) |
| nuSQuIDS | B3 `prem_prob3`, `prem_four`, `prem_full`; `native` (its own spline PREM) is in the wrapper but not yet run. No B2: no production-profile or phase averaging (a pointwise numerical solution from r₀, about 60 CPU-hours per solar model on the B2 grid) |
| SNUfish reference | repository URL in its catalogue entry; no DOI yet: the release files (CITATION.cff, .zenodo.json, docs/release.md) are prepared, no version is tagged or archived |
| Full-chain rate tools other than SNOwGLoBES | none yet |
| Other cross-section models | no alternatives for ¹⁶O (SNOwGLoBES only); ¹³C CC is in B4 but no detector or engine channel uses it; NC on ⁴⁰Ar only from SNOwGLoBES's table (unpublished QRPA, labelled an approximation, no visible-energy model: cut in E<sub>ν</sub> only); no NC on ¹⁶O |
| More ⁴⁰Ar shell-model tables | Kostensalo, Suhonen & Zuber (2018) is in (a published table, 5 MeV steps); Suzuki & Honma (2013) / Suzuki & Shimizu (2023) publish no σ(E) table, only a folded value (reproduced by MARLEY 2 to 3 %). A finer KSZ table, or σ(E) from the Suzuki group, would remove the 3 % interpolation error and add a calculation ([status-of-inputs.md](status-of-inputs.md)) |
| Tomalak & Hill ES cross section | the most precise ν–e calculation (0.2–0.4 %), but no tables are published: [arXiv:1907.03379](https://arxiv.org/abs/1907.03379) v2 ships a Mathematica notebook (the formulas of its app. K, example values at ω = 0.3 GeV only). A contribution needs Mathematica or a port of the notebook. BKS and Marciano & Parsa bound it at the solar precision |
| 3D Earth | Two current Earth models make B3's range: `prem_crust1` (the CRUST1.0 column of each site above PREM, radial) and `prem_crust1_3d` (the CRUST1.0 crust along every night chord, solved chord by chord with NuFast-Earth's single-trajectory mode); they differ by ≤ 0.17 % of A<sub>DN</sub>. Missing: a 3D mantle (Han et al. use SAW642AN) and a second crust model (LITHO1.0): Han et al.'s 3D shifts differ from SNUfish's by ~0.05 pp (3–4 % of A<sub>DN</sub>) at LNGS and SURF ([crosschecks.md](crosschecks.md#crust-along-each-chord-3d)), more than the current range |

### Physics scope

- **Normal ordering and neutrinos only.** No inverted ordering, no
  antineutrinos (B2 and B3 state `neutrinos_only`).
- **Standard three-flavour oscillations only.** No sterile neutrinos,
  non-standard interactions or decay.
- **No correlations between oscillation parameters.** They are sampled
  independently: no source publishes them.
- **No backgrounds.** Statistical errors are Poisson on the signal alone.
- **Day and night exposure set by hand.** By default the annual rate is
  (D + N)/2 and the statistics split the exposure in halves; `Setup.night_fraction`
  sets another share (SOLAR: 0.507 at SURF, a constant of its configuration).
  The share is not derived from the site's latitude, and the calculator
  always uses halves.
- **Earth–Sun distance optional, as day and night averages only.** By
  default fluxes are at 1 AU (the convention of published A<sub>DN</sub>);
  `Setup(orbit=True)` scales day and night rates by the site's mean
  (1 AU/R)² ([crosschecks.md](crosschecks.md#earthsun-distance)). Not
  modelled: deeper nights near perihelion (< 0.2 % of A<sub>DN</sub>), time-resolved
  seasonal spectra; the 3D crust (`prem_crust1_3d`) uses the Sun's directions but not their
  distance.
- **B3's Earth models end in PREM's 3 km of ocean.** The engine and the
  calculator default to `prem_crust1` (the CRUST1.0 column of each site
  above PREM's Moho, [crosschecks.md](crosschecks.md#local-crust)) and offer
  `prem_crust1_3d` (the crust along each chord), but the B3 benchmark has no
  crust variant: its detector sits in the ocean, which shifts A<sub>DN</sub> by −2.5 %
  to +3.7 % against the local crust at the five sites.
- **Detector at the surface.** B3 sets the detector depth to 0.
- **CC visible energy is E<sub>ν</sub> − Q** with no neutron, binding or quenching
  losses; NC on deuterium deposits 6.25 MeV (capture on ²H in pure D₂O),
  so SNO's salt phase (capture on ³⁵Cl) is not modelled for NC.
- **Radial path out of the Sun.** Irrelevant while propagation is
  adiabatic; the reference does not measure the effect yet.

## Known approximations

| Approximation | Size | Where |
|---|---|---|
| Adiabatic F<sub>i</sub> in B2 | O(10⁻⁶) for the B2 parameters | `reference/sun.py` |
| App tables instead of exact solvers | 2 × 10⁻⁴ (rates), 1 % (A<sub>DN</sub>) | `engine.TableProbabilities` |
| PREM's continuous regions cut into 50 km shells for NuFast-Earth (the engine's night for `prem_four`, `prem_full`, `prem_crust1`; without the cut, NuFast-Earth's mean density per crossing is off by up to 2 % in ⁸B A<sub>DN</sub>) | ⁸B A<sub>DN</sub> within 0.05 % (0.1 % `prem_four`) of 10 km shells at 4–20 MeV ([crosschecks.md](crosschecks.md#nufast-earth-on-continuous-density)) | `scan.SPLIT_KM` |
| `prem_crust1_3d`: the crust of the ~130 chords in each of the 1001 nadir cells averaged before solving; chords in pieces of near-constant density | ≤ 1.3 × 10⁻⁴ in P₂ₑ (≤ 0.3 % of the regeneration); A<sub>DN</sub> within 0.07 % of 10 km pieces | `earth3d` |
| θ₁₃ in the app tables followed by ν₃ decoupling | within 1.6 % of the exact A<sub>DN</sub> over sin²θ₁₃ = 0.015–0.03 | `engine.TableProbabilities` |
| ⁸B shape truncated at 15.2 MeV (true endpoint ~16.5 MeV) | ~10⁻⁴ of the flux; matters above 15 MeV (⁸B background to hep) | `reference/ssm/shapes/` |
| B16 and BS05 density beyond 0.5 R<sub>☉</sub> | exponential tail fit, residual ≤ 0.0033 in log₁₀ n<sub>e</sub> | `models.yaml` `tail` |
| Cross sections below the B4 grid (0.02 MeV) | < 0.01 % of any rate | B5 spec |
| NaN in a cross-section table counted as zero | a lower bound; `Coverage` reports the covered fraction | build, engine |
| Reference Magnus step on continuous PREM (6.25 km) | P_iₑ within 1.5 × 10⁻⁶ of a 1.5625 km step (nuSQuIDS agrees with the finer one to 10⁻⁸; [crosschecks.md](crosschecks.md#peanuts-and-nusquids)) | `reference/earth.py` `CONVERGED_STEP_KM` |
| BKS QED end-point divergence clipped | last ~10⁻³ of the recoil range | `reference/radiative.py` |
| Super-K IV efficiency read from a figure | 0.08 % in efficiency | `reference/detectors/efficiency_curves.yaml` |
| Hyper-K resolution | Super-K IV's as a stand-in | calculator preset |
| SNO resolution and efficiencies | the salt-phase resolution (nucl-ex/0502021, eq. A3) is in the B5 response and the `sno_salt` preset; no CC efficiency curve is published (taken as 1); the phases I + II preset (`sno`) has no resolution | B5 spec, calculator presets |
| CC visible energy E<sub>ν</sub> − Q | for d(νₑ, e⁻)pp the electron shares E<sub>ν</sub> − Q with the two protons: SNUfish's T for SNO CC is too high, and its rate above 5.5 MeV with it | engine, B5 part 2 |
| SNO salt resolution at low energy | eq. A3 is negative below T = 0.11 MeV and taken as no smearing there: an artefact in the heavy-water ES spectrum below ~0.3 MeV, far under the 5.5 MeV threshold it was fitted for | B5 spec |
| Borexino resolution | "~50 keV at 1 MeV" scaled with √E (photostatistics); its analysis uses a full response model (scaled Poisson in N_p, quenching, Cherenkov light) not reduced to σ(E) | B5 spec |
| DUNE response | 20 % at every energy and no efficiency below or above the 5 MeV step: no solar-neutrino response is published | B5 spec, calculator preset |
| Super-K IV efficiency on CC ¹⁶O | the fig. 28 curve (⁸B ES) applied to every channel of water, CC ¹⁶O included (4 × 10⁻⁵ per kt·yr: hep only) | B5 spec |
| JUNO preset | no energy-dependent fiducial volume, muon-veto dead time or non-linearity | calculator preset |

## Data to check

- DUNE solar rate tables (thesis ch. 3, paper app. A;
  [dune-solar-tables.md](dune-solar-tables.md)): SNOwGLoBES-style tables are reproduced with
  `ar40_marley1_allowed` (MARLEY v1.2.1's cross section), `nu_threshold`, `nc_ar40` and
  `night_fraction`; the thesis's T<sub>e</sub> > 8 and 10 MeV CC values (+16 %, −28 %)
  are not reproduced. The paper's appendix A (CC 482, ES 141, NC 18.8) came
  from a rate spectrum folded as a flux (P<sub>ee</sub> applied twice); the paper's
  rates now come from `scripts/dune_phase1_rates.py`
  ([dune-solar-tables.md](dune-solar-tables.md#phase-i-paper)).
- SOLAR's Earth density model: set in its NuFast-Earth Python binding, which
  is outside its repository; `night_mode="solar"` matches its depth, latitude
  and nadir PDF but not necessarily its Earth.
- SOLAR's Sun: P<sub>ee</sub> from production at one density, ρY<sub>e</sub> = 90 g/cm³
  (`rhoYe_sun`, "Prob3++ match"), against the ⁸B production profile here:
  −0.6 % on the CC rate above E<sub>ν</sub> = 5 MeV at Δm²₂₁ = 6 × 10⁻⁵. Not an option
  in the engine.

- Jiangmen latitude 22.12°: the JUNO paper gives 22° N; the hundredths are
  not yet checked against a source.
- SNOwGLoBES's 2018 MARLEY table is 35–40 % low at 8–14 MeV: it appears
  to lack the Coulomb (Fermi) factor ([crosschecks.md](crosschecks.md#investigated)).
  It stays selectable and is kept out of the ⁴⁰Ar model range (it is also
  zero below 5 MeV).

## Published numbers not reproduced

From [crosschecks.md](crosschecks.md):

- Super-K's expected A<sub>DN</sub> for the SK-I range at Δm²₂₁ = 4.8 × 10⁻⁵ eV²:
  −3.84 % published, −3.37 % here (12.3 % off) while 6.1 and
  7.5 × 10⁻⁵ eV² agree to 1.7 %; Super-K's own 2014 paper expects −3.3 %
  there, as SNUfish does.
- Capozzi, Li, Zhu & Beacom's DUNE CC A<sub>DN</sub> at 4.85 × 10⁻⁵ eV²: −7.90 %
  published, −6.96 % here; the ten- and four-region PREM bracket it.
- JUNO's −1.6 % expected A<sub>DN</sub> at 7.5 × 10⁻⁵ eV² in its text, against
  −1.4 % from its own table 1 and −1.38 % here.

## Open questions before freezing the specs

- **B3**: extend the energy grid down to 0.1 MeV for pp and ⁷Be (Earth
  effects are tiny there)? Add `prem_crust1` per site as a variant?
- **B4**: add σ(E; T > T<sub>min</sub>) for the detectors' ES thresholds?
- **B5**: take the full Winter et al. ⁸B tail before using rates above
  15 MeV; night and annual quantities in contributions; a second response
  per detector (Hyper-K, JUNO, SNO+) as variants of part 2.
- **B2 (solar models)**: shape variants; use the B23 correlations in B5 rate
  uncertainties.
- **B2**: a non-adiabatic solver; radial path against the true line of
  sight for off-centre production.

## Housekeeping

- CI runs ruff, validation, build, the tests on Python 3.10 and 3.12 and
  the `b2`, `b3`, `b45` plots. It builds the NuFast-Earth driver and
  the app tables (`export-app`, cached on the inputs and the code), so no
  test is skipped, including `test_web_engine.py` (the page's engine against
  the Python one). The `scan` and `budget` commands themselves are not run.
- Pushes to `main` publish the page (`web/deploy.sh`) once lint and tests
  pass. plotipus is pinned to a commit in `pyproject.toml`; the page serves
  the wheel of that commit.
- No release on PyPI; the package version is 0.1.0. A first citable release (v0.2.0) is prepared in docs/release.md, not tagged.
