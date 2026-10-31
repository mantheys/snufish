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

  H = U diag(0, Δm²₂₁, Δm²₃₁) U† / 2E + diag(V, 0, 0),  V = √2 G_F N_e,

with N_e = n_e N_A from the B1 table (or the analytic profile of the spec).
The reference gives the **adiabatic** fractions

  F_i(E, r₀) = |V_eᵢ(r₀)|²,

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
F_i^c(E) = Σ_r w_c(r) F_i(E, r), with w_c the fraction of the component's
flux produced in each radius cell (`snufish.solar.production_weights`,
from the B1 production densities; each profile integrates to 1). The
daytime survival probability is P_ee^day = Σᵢ F_i |U_eᵢ|².

NuFast-Earth's B2 contribution uses its `Calculate_Solar_Probability`
(adiabatic |V_eᵢ|² at one density, F₁ = 1 − F₂ − F₃ by construction).

## Earth crossing (B3 reference)

`snufish.reference.earth`. The chord to a surface detector at nadir
angle η has length 2R_⊕ cos η; `chord_segments` cuts it into ordered
segments of constant density and Yₑ at the shell boundaries. Each segment
contributes the exact propagator S_k = exp(−iH_k L_k) (one matrix
exponential per segment, no stepping). A mass eigenstate νᵢ arriving at the
Earth is the column `U[:, i]`; after the chord its νₑ amplitude is
`(S U)[e, i]`, so

  P_iₑ = |(S_N ⋯ S_1 U)_eᵢ|².

This is exact for piecewise-constant models (`prem_prob3`). For the
polynomial models (`prem_four`, `prem_full`) `chord_regions` cuts the
chord at every region border and `probabilities_ie_regions` integrates
each piece with the fourth-order commutator-free Magnus scheme (Blanes &
Moan 2006): over a step h, with H₁, H₂ at the Gauss points
t = ½ ∓ √3/6,

  S = exp(−ih(α₁H₁ + α₂H₂)) exp(−ih(α₂H₁ + α₁H₂)),
  α₁,₂ = (3 ∓ 2√3)/12,

the right factor first. For constant density it is exactly the shell
propagator. Steps of 6.25 km (`CONVERGED_STEP_KM`) give P_iₑ within
4 × 10⁻⁷ of a 1.5625 km solution over 43 chords and the 39 exposure
energies; the convergence is slowest at low energy, where the Δm²₃₁ mode
oscillates over ~2 km. Independently, the exact solver on 1 km constant
shells agrees to 3 × 10⁻⁶. The tests check the matter potential against its
textbook value, chord lengths, the core-crossing threshold, unitarity, the
vacuum limit at the horizon, independence of θ₂₃ and δ, the
two-flavour constant-density formula, the Magnus scheme's exactness on
constant shells, its order and its agreement with thin shells.

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

  ⟨P_iₑ⟩_night(E) = Σ_cells w_cell P_iₑ(E, cos η_cell).

This is why B3 has the fine `exposure` grid (cos η step 0.001). The tests
check agreement with NuFast-Earth, the normalisation, the absence of core
crossings near the poles and zero weight above the horizon.

## Day, night and the asymmetry

For each component (`snufish.build.combine_day_night`,
`snufish.engine.survival`):

  P_ee^day = Σᵢ F_i |U_eᵢ|²,  P_ee^night = Σᵢ F_i ⟨P_iₑ⟩_night,

and for a rate R, A_DN = 2(R_N − R_D)/(R_N + R_D). The annual rate is
(R_D + R_N)/2. Below the B3 energy grid (1 MeV) the night probabilities
take their vacuum value |U_eᵢ|² (no Earth effect).

## Cross sections

### ν–e elastic scattering, tree level

`snufish.reference.xsec`:

  dσ/dT = (2G_F² m_e / π) [g₁² + g₂² (1 − T/E)² − g₁g₂ m_e T / E²],

g₁ = ½ + s²_W (νₑ: CC + NC), −½ + s²_W (ν_μ, ν_τ: NC only), g₂ = s²_W,
T_max = 2E²/(m_e + 2E), sin²θ_W = 0.23857. `es_above(E, t)` integrates it
analytically over T > t (recoil thresholds).

### ν–e elastic scattering with radiative corrections (BKS)

`snufish.reference.radiative`: Bahcall, Kamionkowski & Sirlin, PRD 51,
6146 (1995), appendices A and B, with electroweak, QCD and QED corrections
and the inelastic ν e → ν e γ (photon not detected):
ρ = 1.0126, κₑ(T) = 0.9791 + 0.0097 I(T), κ_μ(T) = 0.9970 − 0.00037 I(T),
sin²θ_W(m_Z) MS-bar = 0.2317. The QED functions diverge logarithmically at
the end point; the differential cross section is clipped at zero there
(the last ~10⁻³ of the recoil range). The engine uses it as a ratio to the
tree level, σ_BKS(E; T > u T_max)/σ_tree(E; T > u T_max), tabulated in E
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
the B1 model's, or, for ⁸B on request, the measured SNO neutral-current
total flux, 5.25 × 10⁶ cm⁻² s⁻¹ ± 3.81 % (as Super-K applies it).

## Rate folding

For component c with flux Φ_c and shape s_c, per target:

- **CC** (νₑ only): dR/dE = N Φ_c s_c(E) P_ee(E) σ(E).
- **ES**: dR/dE = N Φ_c s_c(E) [P_ee(E) σ_e(E) + (1 − P_ee(E)) σ_μ(E)],
  using ν_μ and ν_τ having the same NC cross section.
- **NC on deuterium**: flavour-blind, dR/dE = N Φ_c s_c(E) σ_NC(E)
  (three active flavours; sterile mixing is not modelled).

Continua are integrated with trapezoid weights on the shape's grid (the
engine's `_quadrature`), lines as points. Rates are per kiloton-year with
the detector's targets per kt (B5 spec and `export.APP_DETECTORS`).

The B5 build (`combine_rates`) folds in true neutrino energy with the B2
reference daytime oscillations, and with the B3 reference night excess of
each site for `B5_DayNight` ([benchmarks.md](benchmarks.md#b5_rates-interaction-rates));
the engine adds the detector response below.

## Observed energy

The engine reports spectra in **observed energy**:

- **ES**: the electron's kinetic energy T. For each neutrino energy the
  cross section into each recoil bin is σ(E; T in bin) =
  σ(E; T > T_lo) − σ(E; T > T_hi), exact for the tree-level formula and
  scaled bin by bin by the BKS ratio.
- **CC**: the visible energy E_ν − Q (the electron plus de-excitation
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
- **Resolution**: Gaussian with σ(E) = √((a√E)² + (bE)²), or Super-K's
  σ = c₀ + c₁√E_tot + c₂E_tot with E_tot = T + m_e for ES (the SK-IV
  preset: −0.05525, 0.3162, 0.04572), times a resolution scale. What smears
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

## Uncertainties

`snufish.engine.budget` (and `snufish.uncertainty` for the `snufish
budget` command). Two kinds are kept apart.

**Sampled** (Monte Carlo, n = 400 draws by default, fixed seed), each
reported as a standard deviation and combined in "total sampled":

- **Oscillation parameters**: each parameter of the set drawn
  independently from a split normal (different σ below and above the
  central value) — no source publishes their correlations.
- **Solar fluxes**: multipliers drawn from a multivariate normal with the
  model's fractional errors and, for B23, its published correlation
  matrix (Cholesky). BS05 publishes no errors: no flux row. With the SNO
  NC ⁸B flux, ⁸B is drawn independently with its 3.81 %. A single
  component's flux cancels in A_DN and in the ratio, so it gets no row
  there.
- **Statistics**, when an exposure is given: Poisson, half the exposure by
  day and half by night, no backgrounds. For A_DN,
  σ² = (4D/S²)² N + (4N/S²)² D with S = D + N in counts.
- **Detector**: energy scale and resolution as half the difference of the
  quantity at ±1σ; the normalisation scales a rate (and cancels in A_DN).
  Each is applied as one Gaussian draw per sample.
- **Measured nuclear strengths** (MARLEY 2 models): see below.

**Model ranges**, reported as [min, max] over the state-of-the-art
alternatives and never folded into a σ (the range depends on which models
exist, not on a probability): cross-section model (CC), ES radiative
corrections (ES), Earth model (night quantities only), solar model. Legacy
models and approximations ([status-of-inputs.md](status-of-inputs.md),
`reference/status.yaml`) are left out; `budget(..., legacy=True)` adds a
`legacy spread` row per choice over every model, as context. A range that does not
move the quantity (e.g. the solar model when the only component's flux is
the measured one) is dropped.

### Measured nuclear strengths

For the MARLEY 2 models of νₑ–⁴⁰Ar, each measured bound-level B(GT) has a
1σ uncertainty in MARLEY's reaction file. σ is linear in each B(GT), so
the contribution's `bgt_levels.parquet` holds one cross-section table per
level with that level's B(GT) raised by 1σ; the quantity's uncertainty is
the quadrature sum of the shifts it produces (levels independent).

## Analyses

### `snufish scan`

`snufish.scan`. For each Δm²₂₁ on a grid (default 4–10 × 10⁻⁵ eV², step
0.2), each parameter set, each Earth model and a site (default Kamioka),
for ⁸B with the solar model's production profile:

- daytime P_ee(E) and its quadratic coefficients around 10 MeV
  (c₀, c₁, c₂ of a fit over 3–15 MeV), with the χ² against the SK + SNO
  measurement and its correlation matrix;
- the upturn P_ee(4 MeV) − P_ee(10 MeV);
- A_DN of P_ee (5–15 MeV, flux-weighted) and of the ES rate above the
  Super-K recoil threshold (3.49 MeV kinetic, tree level), compared with
  Super-K's measurement.

The B2 solver is used for the day and NuFast-Earth (validated against the
B3 reference) for the night.

### `snufish budget`

`snufish.uncertainty`. Budgets of the daytime ⁸B rates (true neutrino
energy, ES recoil threshold, no detector response) and the ES A_DN for
several parameter sets (default `juno_2025`, `solar_global_2024`) and both
⁸B flux treatments (solar model, SNO NC), with the exact solvers or, with
`--tables`, the app tables.

## App tables

`snufish.export` and `engine.TableProbabilities`. The web page cannot run
the solvers, so `snufish export-app` tabulates them on a (sin²θ₁₂,
Δm²₂₁) grid (default 0.24–0.38 step 0.01; 3–11 × 10⁻⁵ eV² step 0.2):

- `day_<solar model>`: F₁, F₂ per component on 72 log-spaced energies
  (0.1–20 MeV, the component's part of it; lines at their own energies);
- `night_<Earth model>`: night-averaged P_iₑ for every site.

The provider interpolates bilinearly in (sin²θ₁₂, Δm²₂₁), linearly in
log E (day) or E (night), and clamps (and counts) points outside the grid.
The tables are computed at the default θ₁₃, θ₂₃, δ and Δm²₃₁; θ₁₃ is
followed as ν₃ decouples: F₁,₂ and P₁ₑ,₂ₑ scale with cos²θ₁₃, F₃ and P₃ₑ
with sin²θ₁₃ (P_ee = c₁₃⁴ P_ee^(2ν) + s₁₃⁴, without the c₁₃² in the matter
potential); the others enter only through |U_eᵢ|². The tables reproduce
the exact solvers to 2 × 10⁻⁴ for rates and 1 % (3 × 10⁻⁴ absolute) for
A_DN, and A_DN within 1.6 % over sin²θ₁₃ = 0.015–0.03.

Each table is `<name>.json` (small arrays, an index) with `<name>.bin`
(large arrays, little-endian float32), read the same way by
`engine.read_table` and the web page.
