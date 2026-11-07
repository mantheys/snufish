# Methods

The physics and numerics behind the reference solvers, the build and the
engine. Each section names the module that implements it. Numbers quoted as
accuracies are those the tests check (`tests/`).

## Oscillation parameters

`snufish.spec.pmns` builds U in the PDG parametrisation from an
`oscillation` block (sin²θ₁₂, sin²θ₁₃, sin²θ₂₃, δ, Δm²₂₁, Δm²₃₁; normal
ordering). The parameter sets of `reference/oscillation/parameter_sets.yaml`
give sin²θ₁₂ and Δm²₂₁ with their errors; θ₁₃, θ₂₃, δ and Δm²₃₁ come from
the `defaults` block (NuFIT 6.0). `engine.parameters` merges a set with
custom values.

## MSW in the Sun (B2 reference)

`snufish.reference.sun`. In the flavour basis

  H = U diag(0, Δm²₂₁, Δm²₃₁) U† / 2E + diag(V, 0, 0),  V = √2 G<sub>F</sub> N<sub>e</sub>,

with N<sub>e</sub> = n<sub>e</sub> N<sub>A</sub> from the B2 solar-model table (or the analytic profile of the spec).
The reference gives the **adiabatic** fractions

  F<sub>i</sub>(E, r₀) = |V<sub>ei</sub>(r₀)|²,

with V the eigenvectors of H at the production point ordered by
eigenvalue: in normal ordering there is no level crossing, so the k-th
matter state becomes νₖ at the surface. For the B2 parameters the
propagation is deeply adiabatic (γ ~ 10³ at the resonance, crossing
probability ~ exp(−πγ/2)); O(1/γ) corrections oscillate with the phase
accumulated across the Sun and average out over any energy resolution,
leaving O(1/γ²) ~ 10⁻⁶. A staircase-density solver was tried and rejected:
its step-boundary kicks converge only like √step and were larger than the
effect.

**Production average.** For a flux component c,
F<sub>i</sub><sup>c</sup>(E) = Σ<sub>r</sub> w<sub>c</sub>(r) F<sub>i</sub>(E, r), with w<sub>c</sub> the fraction of the component's
flux produced in each radius cell (`snufish.solar.production_weights`,
from the B2 solar-model production densities; each profile integrates to 1). The
daytime survival probability is P<sub>ee</sub><sup>day</sup> = Σᵢ F<sub>i</sub> |U<sub>ei</sub>|².

NuFast-Earth's B2 contribution uses its `Calculate_Solar_Probability`
(adiabatic |V<sub>ei</sub>|² at one density, F₁ = 1 − F₂ − F₃ by construction).

## Earth crossing (B3 reference)

`snufish.reference.earth`. The chord to a surface detector at nadir
angle η has length 2R<sub>⊕</sub> cos η; `chord_segments` cuts it into ordered
segments of constant density and Yₑ at the shell boundaries. Each segment
contributes the exact propagator S<sub>k</sub> = exp(−iH<sub>k</sub> L<sub>k</sub>) (one matrix
exponential per segment, no stepping). A mass eigenstate νᵢ arriving at the
Earth is the column `U[:, i]`; after the chord its νₑ amplitude is
`(S U)[e, i]`, so

  P<sub>ie</sub> = |(S<sub>N</sub> ⋯ S<sub>1</sub> U)<sub>ei</sub>|².

This is exact for piecewise-constant models (`prem_prob3`). For the
polynomial models (`prem_four`, `prem_full`) `chord_regions` cuts the
chord at every region border and `probabilities_ie_regions` integrates
each piece with the fourth-order commutator-free Magnus scheme (Blanes &
Moan 2006): over a step h, with H₁, H₂ at the Gauss points
t = ½ ∓ √3/6,

  S = exp(−ih(α₁H₁ + α₂H₂)) exp(−ih(α₂H₁ + α₁H₂)),
  α₁,₂ = (3 ∓ 2√3)/12,

the right factor first. For constant density it is exactly the shell
propagator. Steps of 6.25 km (`CONVERGED_STEP_KM`) give P<sub>ie</sub> within
4 × 10⁻⁷ of a 1.5625 km solution over 43 chords and the 39 exposure
energies; the convergence is slowest at low energy, where the Δm²₃₁ mode
oscillates over ~2 km. On the `map` grid's energies in between it reaches
1.5 × 10⁻⁶ (5.4 × 10⁻⁷ at the exposure energies on all chords) (found by the nuSQuIDS contribution,
[crosschecks.md](crosschecks.md#peanuts-and-nusquids)). Independently, the exact solver on 1 km constant
shells agrees to 3 × 10⁻⁶. The tests check the matter potential against its
textbook value, chord lengths, the core-crossing threshold, unitarity, the
vacuum limit at the horizon, independence of θ₂₃ and δ, the
two-flavour constant-density formula, the Magnus scheme's exactness on
constant shells, its order and its agreement with thin shells.

### Local crust (`prem_crust1`, engine and calculator)

`snufish.crust`: PREM up to the local Moho, then the CRUST1.0 layers of
the site's 1° × 1° cell (constant density each, Yₑ = 0.494) to the surface
(`reference/earth/crust1_sites.yaml`). Still radial: the same column
everywhere along the chord. Solved by NuFast-Earth through the B3 driver's
`regions:FILE` model (one region per line: outer radius, Yₑ, density
polynomial), which given PREM's own regions reproduces `prem_full`
bit for bit. Like every continuous model of the engine's night, its
polynomial regions are cut into 50 km shells (`scan.SPLIT_KM`), so that
NuFast-Earth's mean density per crossing follows the profile.

### Crust along each chord (`prem_crust1_3d`, engine and calculator)

`snufish.earth3d`: along every night chord, the CRUST1.0 layer of the cell
each point lies under (the whole 1° × 1° grid,
`reference/earth/crust1_global.npz`, each cell's surface at the Earth's
radius), PREM under the local Moho (its lid continued up to it, as in
`prem_crust1`). The chords are the Sun's directions every 2 minutes over a
year (2026; low-precision solar coordinates and the Earth rotation angle)
from the site's latitude and longitude, binned in the 1001 cells of B3's
cos-nadir grid, whose weights stay W(η). In each cell the crust of its chords
is averaged at equal distance from the detector (near half) and from the
entry point (far half), which to first order in the density change is the
average of P over the chords (checked: ≤ 1.3 × 10⁻⁴ in P₂ₑ); the chord, cut
into pieces where the density changes by 0.05 g/cm³ or every 50 km, is
solved by NuFast-Earth's single-trajectory mode through the B3 driver's
`trajectories:FILE` model (one chord per cos η, pieces in the neutrino's
order). The chords of each site are cached in `build/data/earth3d`.

## Night exposure

`snufish.exposure`. The fraction of the night the Sun spends at nadir
angle η, per radian, for a detector at latitude λ: W(η; λ) of Lisi &
Montanino (hep-ph/9702343, table II), as implemented in NuFast-Earth
(`src/Solar.cpp`), with complete elliptic integrals by the AGM. It is
normalised to 1 over the night (η < π/2) and has integrable logarithmic
singularities at η = |λ − i| and λ + i (i = 0.4091 rad, the Earth's
axial tilt).
Averages over a nadir grid therefore use the exposure integrated over each
grid cell (`cell_weights`), not W sampled at grid points:

  ⟨P<sub>ie</sub>⟩<sub>night</sub>(E) = Σ<sub>cells</sub> w<sub>cell</sub> P<sub>ie</sub>(E, cos η<sub>cell</sub>).

This is why B3 has the fine `exposure` grid (cos η step 0.001). The tests
check agreement with NuFast-Earth, the normalisation, the absence of core
crossings near the poles and zero weight above the horizon.

## Day, night and the asymmetry

For each component (`snufish.build.combine_day_night`,
`snufish.engine.survival`):

  P<sub>ee</sub><sup>day</sup> = Σᵢ F<sub>i</sub> |U<sub>ei</sub>|²,  P<sub>ee</sub><sup>night</sup> = Σᵢ F<sub>i</sub> ⟨P<sub>ie</sub>⟩<sub>night</sub>,

and for a rate R, A<sub>DN</sub> = 2(R<sub>N</sub> − R<sub>D</sub>)/(R<sub>N</sub> + R<sub>D</sub>). The annual rate is
(R<sub>D</sub> + R<sub>N</sub>)/2. Below the B3 energy grid (1 MeV) the night probabilities
take their vacuum value |U<sub>ei</sub>|² (no Earth effect).

## Cross sections

### ν–e elastic scattering, tree level

`snufish.reference.xsec`:

  dσ/dT = (2G<sub>F</sub>² m<sub>e</sub> / π) [g₁² + g₂² (1 − T/E)² − g₁g₂ m<sub>e</sub> T / E²],

g₁ = ½ + s²<sub>W</sub> (νₑ: CC + NC), −½ + s²<sub>W</sub> (ν<sub>μ</sub>, ν<sub>τ</sub>: NC only), g₂ = s²<sub>W</sub>,
T<sub>max</sub> = 2E²/(m<sub>e</sub> + 2E), sin²θ<sub>W</sub> = 0.23857. `es_above(E, t)` integrates it
analytically over T > t (recoil thresholds).

### ν–e elastic scattering with radiative corrections (BKS)

`snufish.reference.radiative`: Bahcall, Kamionkowski & Sirlin, PRD 51,
6146 (1995), appendices A and B, with electroweak, QCD and QED corrections
and the inelastic ν e → ν e γ (photon not detected):
ρ = 1.0126, κₑ(T) = 0.9791 + 0.0097 I(T), κ<sub>μ</sub>(T) = 0.9970 − 0.00037 I(T),
sin²θ<sub>W</sub>(m<sub>Z</sub>) MS-bar = 0.2317. The QED functions diverge logarithmically at
the end point; the differential cross section is clipped at zero there
(the last ~10⁻³ of the recoil range). The engine uses it as a ratio to the
tree level, σ<sub>BKS</sub>(E; T > u T<sub>max</sub>)/σ<sub>tree</sub>(E; T > u T<sub>max</sub>), tabulated in E
and u (`ratio_table`), and reproduces the paper's averaged cross sections
([crosschecks.md](crosschecks.md)).

The engine offers three ES models: `bks` (default), `tree`, and
`snowglobes` (SNOwGLoBES's tables, as their ratio to tree level; BKS below
their 0.5 MeV start). The ES model range of a budget is BKS against
SNOwGLoBES; tree level is selectable but, as an approximation, not a model of the range.

### Charged current and neutral current

Tables (B4 contributions and `reference/xsec/nakamura2002.yaml`),
interpolated linearly, zero outside the table and below the reaction
threshold (⁴⁰Ar 1.504 MeV, d CC 1.442 MeV, d NC 2.224 MeV). Missing
values (NaN) count as zero, so a table that stops early gives a lower
bound; the build reports the covered fraction (`Coverage`). Tables zero
below 5 MeV (SNOwGLoBES's MARLEY tables) are selectable but kept out of
the model range.

## Fluxes

`snufish.fluxes`. Each continuum shape is normalised to unit area on its
own energy grid; lines carry their branching fractions (⁷Be 861.3 keV:
89.56 %, 384.3 keV: 10.44 %; pep 1.442 MeV). The flux of each component is
the B2 solar model's, or, for ⁸B on request, the measured SNO neutral-current
total flux, 5.25 × 10⁶ cm⁻² s⁻¹ ± 3.81 % (as Super-K applies it).

## Rate folding

For component c with flux Φ<sub>c</sub> and shape s<sub>c</sub>, per target:

- **CC** (νₑ only): dR/dE = N Φ<sub>c</sub> s<sub>c</sub>(E) P<sub>ee</sub>(E) σ(E).
- **ES**: dR/dE = N Φ<sub>c</sub> s<sub>c</sub>(E) [P<sub>ee</sub>(E) σ<sub>e</sub>(E) + (1 − P<sub>ee</sub>(E)) σ<sub>μ</sub>(E)],
  using ν<sub>μ</sub> and ν<sub>τ</sub> having the same NC cross section.
- **NC on deuterium**: flavour-blind, dR/dE = N Φ<sub>c</sub> s<sub>c</sub>(E) σ<sub>NC</sub>(E)
  (three active flavours; sterile mixing is not modelled).

Continua are integrated with trapezoid weights on the shape's grid (the
engine's `_quadrature`), lines as points. Rates are per kiloton-year with
the detector's targets per kt (B5 spec; JUNO's LAB in `export.APP_DETECTORS`).

The B5 build (`combine_rates`) folds in true neutrino energy with the B2
reference daytime oscillations, and with the B3 reference night excess of
each site for `B5_DayNight` ([benchmarks.md](benchmarks.md#b5-detector-b5_rates-interaction-rates-and-the-detector-response));
the engine adds the detector response below, and B5 part 2 (`combine_observed`)
passes the same daytime rates through each detector's published response.

## Observed energy

The engine reports spectra in **observed energy**:

- **ES**: the electron's kinetic energy T. For each neutrino energy the
  cross section into each recoil bin is σ(E; T in bin) =
  σ(E; T > T<sub>lo</sub>) − σ(E; T > T<sub>hi</sub>), exact for the tree-level formula and
  scaled bin by bin by the BKS ratio.
- **CC**: the visible energy E<sub>ν</sub> − Q (the electron plus de-excitation
  gammas, no neutron or binding losses): Q = 1.504 MeV (⁴⁰Ar), 15.42 MeV
  (¹⁶O), 1.442 MeV (d).
- **NC on deuterium**: the neutron's capture gamma, 6.25 MeV, whatever the
  neutrino's energy; the efficiency stands for capture × detection.

Bins: a first bin [0, 0.01 MeV], then log-spaced to 25 MeV with 16 display
bins per decade and 4 fine bins per display bin; the threshold is inserted
as a fine edge, so the cut is exact (`observed_edges`).

## Detector response

`engine._response` builds, per setup, a matrix [true bin, observed bin]
and an acceptance per observed bin:

- **Energy scale** k: observed = k × true (for the scale uncertainty).
- **Resolution**: Gaussian with σ(E) = √((a√E)² + (bE)²), or a published
  σ = c₀ + c₁√E + c₂E: Super-K's in E = E<sub>tot</sub> = T + m<sub>e</sub> for ES
  (`resolution_energy` "total"; SK IV: −0.05525, 0.3162, 0.04572), SNO's in
  E = T ("kinetic"; salt phase: −0.131, 0.383, 0.03731), the observed energy
  itself for CC; times a resolution scale. σ is taken at the true energy of
  each bin, as both experiments define it. What smears
  below zero goes to the first bin, above the last edge to the last bin.
- **Imported smearing matrix** (CSV) in place of the resolution: each fine
  true bin takes the row of the imported true bin holding its centre, and
  each imported observed bin is spread over the fine bins it overlaps. Its
  true axis is the observed-energy variable, or (CC) the neutrino energy.
- **Efficiency**: a plateau with a logistic turn-on
  ε(E) = ε₀ / (1 + exp(−(E − E₅₀)/w)), or an imported or published curve
  (linear interpolation; 0 below the first point, the last value above).
  The published Super-K IV curve is a step table read from the paper's
  figure (see [sources.md](sources.md#detectors)).
- **Threshold**: acceptance zero in bins below it.

A perfect detector (no resolution, flat efficiency 1, no threshold)
reproduces the true-energy rates (tested).

### Published responses (B5 part 2)

The B5 spec's `response` gives each detector one published response
(Super-K IV for water, SNO's salt phase for heavy water, Borexino Phase-II
for scintillator, DUNE's far detector for argon; numbers and sources in
[sources.md](sources.md#detector-responses)); `engine.published_response`
turns it into setup fields, and the calculator's presets take the same
values (`tests/test_b5_response.py`). `build.combine_observed` folds the
part 1 daytime rates (B2 reference F_i averaged over production, NuFIT 6.0,
the cross sections the spec names) through it with `engine.observed_rates`
on the spec's observed grid: 0–20 MeV in 0.01 MeV bins, true and observed
bins alike, so every preset threshold is a bin edge. The threshold is not
part of the spectrum; the rate above a threshold is the spectrum summed
over the bins above it. A contribution with its own response gives it as a
binned matrix and efficiency (`response.parquet`), which `response_tables`
turns into an imported matrix and efficiency curve for the same folding.

## Uncertainties

`snufish.engine.budget` (and `snufish.uncertainty` for the `snufish
budget` command). Two kinds are kept apart.

**Sampled** (Monte Carlo, fixed seed; a sampled σ from n draws is uncertain by
about 1/√(2n): 1000 draws on the benchmark pages and in the calculator, which
shows 400 at once and replaces them with 1000 computed in a background worker;
400 in `snufish budget` for now), each
reported as a standard deviation and combined in "total sampled", in the
order of the calculator's steps (B1 to B5):

- **Oscillation parameters** (B1): each parameter of the set drawn
  independently from a split normal (different σ below and above the
  central value) — no source publishes their correlations.
- **Solar fluxes** (B2): multipliers drawn from a multivariate normal with the
  model's fractional errors and, for B23, its published correlation
  matrix (Cholesky). BS05 publishes no errors: no flux row. With the SNO
  NC ⁸B flux, ⁸B is drawn independently with its 3.81 %. A single
  component's flux cancels in A<sub>DN</sub> and in the ratio, so it gets no row
  there.
- **Measured nuclear strengths** (B4, MARLEY 2 models): see below.
- **Statistics** (B5), when an exposure is given: Poisson, half the exposure by
  day and half by night, no backgrounds. For A<sub>DN</sub>,
  σ² = (4D/S²)² N + (4N/S²)² D with S = D + N in counts.
- **Detector** (B5): energy scale and resolution as half the difference of the
  quantity at ±1σ; the normalisation scales a rate (and cancels in A<sub>DN</sub>).
  Each is applied as one Gaussian draw per sample.

**Model ranges**, reported as [min, max] over the state-of-the-art
alternatives and never folded into a σ (the range depends on which models
exist, not on a probability), again in step order: solar model (B2), Earth
model (B3, night quantities only), cross-section model (B4, CC) or ES
radiative corrections (B4, ES). Legacy
models and approximations ([status-of-inputs.md](status-of-inputs.md),
`reference/status.yaml`) are left out; `budget(..., legacy=True)` adds a
`legacy spread` row per choice over every model, as context. A range that does not
move the quantity (e.g. the solar model when the only component's flux is
the measured one) is dropped.

### Measured nuclear strengths

For `ar40_marley2_bhattacharya2009` and `ar40_marley1_allowed`, each
measured bound-level B(GT) has a 1σ uncertainty in MARLEY's reaction file.
σ is linear in each B(GT), so the contribution's `bgt_levels.parquet` holds
one cross-section table per model and level with that level's B(GT) raised
by 1σ; the quantity's uncertainty is the quadrature sum of the shifts it
produces (levels independent).

## Analyses

### `snufish scan`

`snufish.scan`. For each Δm²₂₁ on a grid (default 4–10 × 10⁻⁵ eV², step
0.2), each parameter set, each Earth model and a site (default Kamioka),
for ⁸B with the solar model's production profile:

- daytime P<sub>ee</sub>(E) and its quadratic coefficients around 10 MeV
  (c₀, c₁, c₂ of a fit over 3–15 MeV), with the χ² against the SK + SNO
  measurement and its correlation matrix;
- the upturn P<sub>ee</sub>(4 MeV) − P<sub>ee</sub>(10 MeV);
- A<sub>DN</sub> of P<sub>ee</sub> (5–15 MeV, flux-weighted) and of the ES rate above the
  Super-K recoil threshold (3.49 MeV kinetic, tree level), compared with
  Super-K's measurement.

The B2 solver is used for the day and NuFast-Earth (validated against the
B3 reference) for the night.

### `snufish budget`

`snufish.uncertainty`. Budgets of the daytime ⁸B rates (true neutrino
energy, ES recoil threshold, no detector response) and the ES A<sub>DN</sub> for
several parameter sets (default `juno_2025`, `solar_global_2024`) and both
⁸B flux treatments (solar model, SNO NC), with the exact solvers or, with
`--tables`, the app tables.

## App tables

`snufish.export` and `engine.TableProbabilities`. The web page cannot run
the solvers, so `snufish export-app` tabulates them on a (sin²θ₁₂,
Δm²₂₁) grid (default 0.24–0.38 step 0.01; 3–11 × 10⁻⁵ eV² step 0.2):

- `day_<solar model>`: F₁, F₂ per component on 72 log-spaced energies
  (0.1–20 MeV, the component's part of it; lines at their own energies);
- `night_<Earth model>`: night-averaged P<sub>ie</sub> for every site.

The provider interpolates bilinearly in (sin²θ₁₂, Δm²₂₁), linearly in
log E (day) or E (night), and clamps (and counts) points outside the grid.
The tables are computed at the default θ₁₃, θ₂₃, δ and Δm²₃₁; θ₁₃ is
followed as ν₃ decouples: F₁,₂ and P₁ₑ,₂ₑ scale with cos²θ₁₃, F₃ and P₃ₑ
with sin²θ₁₃ (P<sub>ee</sub> = c₁₃⁴ P<sub>ee</sub><sup>(2ν)</sup> + s₁₃⁴, without the c₁₃² in the matter
potential); the others enter only through |U<sub>ei</sub>|². The tables reproduce
the exact solvers to 2 × 10⁻⁴ for rates and 1 % (3 × 10⁻⁴ absolute) for
A<sub>DN</sub>, and A<sub>DN</sub> within 1.6 % over sin²θ₁₃ = 0.015–0.03.

Each table is `<name>.json` (small arrays, an index) with `<name>.bin`
(large arrays, little-endian float32), read the same way by
`engine.read_table` and the web page.
