# Benchmarks

Each benchmark isolates one link of the chain from the solar core to an
interaction in a detector, and fixes its inputs in
`benchmarks/<id>/spec.yaml`. Contributions differ only by the tool; named
**variants** carry model alternatives (solar model, Earth model, nuclear
model) so that the spread between models shows next to the spread between
tools. All specs are drafts: they may still change, and any change bumps
their `version`.

| id | Version | Link of the chain | Contributed by |
|---|---|---|---|
| [B1_ssm](#b1_ssm-standard-solar-models) | 0.1.0 | the source: solar models | (registry, no contributions) |
| [B2_sun](#b2_sun-msw-propagation-in-the-sun) | 0.2.0 | MSW propagation out of the Sun | snufish-reference, nufast-earth |
| [B3_earth](#b3_earth-earth-crossing) | 0.3.0 | crossing the Earth at night | snufish-reference, nufast-earth |
| [B4_xsec](#b4_xsec-cross-sections) | 0.1.0 | detection cross sections | snufish-reference, snowglobes, marley |
| [B5_rates](#b5_rates-interaction-rates) | 0.3.0 | interaction rates | snowglobes (full chain); SNUfish folds every B4 model |
| D | — | detector response | planned ([status.md](status.md)) |

Shared settings of B2 and B3: NuFIT 6.0, normal ordering
(sin²θ₁₂ = 0.307, sin²θ₁₃ = 0.02195, sin²θ₂₃ = 0.561, δ = 177°,
Δm²₂₁ = 7.49 × 10⁻⁵ eV², Δm²₃₁ = 2.534 × 10⁻³ eV²); G_F = 1.1663788 ×
10⁻⁵ GeV⁻² (PDG 2024), ħc = 197.3269804 MeV fm (CODATA 2018),
N_A = 6.02214076 × 10²³ mol⁻¹. The matter potential is V = √2 G_F N_e.

---

## B1_ssm: standard solar models

A registry of ten standard solar models in one format, written by
`scripts/import_ssm.py` from the published tables into
`benchmarks/B1_ssm/models.yaml` and `reference/ssm/<model>.dat`.

| Model id | Family | Composition | Flux errors | Flux correlations |
|---|---|---|---|---|
| `b16_gs98` (reference) | B16 | GS98 | yes | — |
| `b16_agss09met` | B16 | AGSS09met | yes | — |
| `bs05_op` | BS05 | GS98, OP opacities | — | — |
| `bs05_agsop` | BS05 | AGS05, OP opacities | — | — |
| `b23_gs98` | B23 / SF-III | GS98 | yes | yes |
| `b23_agss09` | B23 / SF-III | AGSS09 | yes | yes |
| `b23_c11` | B23 / SF-III | C11 | yes | yes |
| `b23_aag21` | B23 / SF-III | AAG21 | yes | yes |
| `b23_mb22m` | B23 / SF-III | MB22 (meteoritic) | yes | yes |
| `b23_mb22p` | B23 / SF-III | MB22 (photospheric) | yes | yes |

Per model: the flux of each of the eight components, its fractional error
and (B23) correlation matrix, the table of r/R_☉, log₁₀ n_e (N_A cm⁻³) and
the production density of each component per unit r/R_☉, the source file
and its SHA-256.

Conventions fixed by the spec:

- Beyond a table's last radius (B16 and BS05 stop at 0.5 R_☉),
  log₁₀ n_e = intercept + slope · r, fitted to the table for r > 0.4
  (`tail` in `models.yaml`, with its maximum residual). Below the first
  radius, n_e and the production densities are constant.
- Checks, run by `snufish validate` (B1 has no contributions: they run on
  the registry): fluxes positive, flux errors positive, correlation
  matrices symmetric with unit diagonal and positive semi-definite; each
  production profile integrates to 1 (to 10⁻⁶) and is never negative;
  n_e falls monotonically beyond r = 0.05; a fitted tail joins its table
  (to 0.01 in log₁₀ n_e).
- Spectral shapes are shared by all models (B5).

**Products** (`snufish build`): `B1_Fluxes` (flux, ratio to `b16_gs98`,
error), `B1_Profiles` (log n_e against radius), `B1_Production`
(production densities). Plots: `plotipus run b1`.

---

## B2_sun: MSW propagation in the Sun

Each contribution gives the mass-eigenstate fractions that leave the Sun,

  F_i(E, r₀) = P(νₑ produced at radius r₀ → νᵢ at the solar surface),

phase-averaged: the Sun–Earth distance averages all phases, so mass
eigenstates arrive incoherently. The exact pointwise F_i carries O(1/γ)
terms (γ ~ 10³, the adiabaticity at the MSW resonance) that oscillate with
the phase accumulated across the Sun and vanish over any energy
resolution; for these parameters F_i equals the adiabatic |V_eᵢ(r₀)|² to
O(10⁻⁶).

| Setting | Value |
|---|---|
| Quantities | `F1`, `F2`, `F3` |
| Grid `map` | E = 0.1–20 MeV, step 0.1 (200 points); r₀/R_☉ = 0–0.3, step 0.005 (61 points; 99 % of every flux is below 0.27) |
| Sun | R_☉ = 695,700 km (IAU 2015); radial path from r₀ to the surface |
| Variants | `b16_gs98` (required: the tool comparison), every other B1 model, and `exponential` (Bahcall's n_e = 245 exp(−10.54 r/R_☉) N_A cm⁻³, with the B16-GS98 production profiles) |
| Columns | `grid, variant, quantity, energy, radius, value` |
| Checks | values in [0, 1]; F₁ + F₂ + F₃ = 1 to 10⁻⁶ |

**Products**: `B2_Energy` (F_i against energy in radius bins) and
`B2_Average` (F_i averaged over each component's production profile, and
the daytime P_ee = Σᵢ F_i |U_eᵢ|²). Plots: `plotipus run b2`.

---

## B3_earth: Earth crossing

Each contribution gives P(νᵢ → νₑ) for a pure mass eigenstate νᵢ arriving
at the Earth and crossing it along the chord set by the nadir angle η.
Solar physics enters only through B2, so B3 compares Earth propagation
codes alone. P_iₑ depends only on the νₑ row of U (θ₁₂, θ₁₃): θ₂₃ and δ
must not change it.

| Setting | Value |
|---|---|
| Quantities | `P1e`, `P2e`, `P3e` |
| Grid `map` | E = 1–20 MeV, step 0.1 (191); cos η = 0–1, step 0.01 (101): energy structure point by point |
| Grid `exposure` | E = 1–20 MeV, step 0.5 (39); cos η = 0–1, step 0.001 (1001): fine enough for night averages (the night-weighted regeneration converges to ~10⁻³; the `map` step is off by up to ~15 %) |
| Earth | R_⊕ = 6371 km, detector at the surface |
| Columns | `grid, variant, quantity, energy, cos_nadir, value` |
| Checks | values in [0, 1]; P₁ₑ + P₂ₑ + P₃ₑ = 1 to 10⁻⁶; P_iₑ = |U_eᵢ|² at cos η = 0 to 10⁻⁶ |

Earth models, written out in the spec so that every tool solves the same
problem (copied from NuFast-Earth `src/Earth.cpp` @ 327586d):

| Variant | Required | Model |
|---|---|---|
| `prem_prob3` | yes | four constant shells as in Prob3++ (13.0, 11.3, 5.0, 3.3 g/cm³, Yₑ = 0.5): solvable exactly by every code; the tool comparison |
| `prem_four` | no | PREM polynomials of the four main regions, the outermost extended to the surface; Yₑ = 0.466 (core), 0.494 (mantle) |
| `prem_full` | no | full PREM, ten regions |
| `native` | no | the tool's own default Earth model, described in `meta.yaml` `settings.earth_model` |

Detector sites, for night averages with the annual exposure W(η; latitude)
of Lisi & Montanino (see [methods.md](methods.md#night-exposure)):

| Site | Latitude (°N) | Experiments |
|---|---|---|
| Kamioka | 36.48 | Super-K, Hyper-K |
| LNGS | 42.45 | Borexino |
| SURF | 44.356 | DUNE far detector |
| SNOLAB | 46.47 | SNO, SNO+ |
| Jiangmen | 22.12 | JUNO |

The `snufish-reference` contribution solves `prem_prob3` exactly and
`prem_four`, `prem_full` with a converged Magnus integration
([methods.md](methods.md#earth-crossing-b3-reference)).

**Products**: `B3_Energy` (P_iₑ and the regeneration P_iₑ − |U_eᵢ|²
against energy at selected nadir angles), `B3_Nadir` (against cos η in
energy bins), `B3_Map` (the full maps), `B3_Night` (night averages per
site). With B2: `B23_DayNight` (P_ee day and night and A_DN per tool,
solar model, Earth model, site and component). Plots: `plotipus run b3`
(B2 × B3 figures are in the `b2` list).

---

## B4_xsec: cross sections

Each contribution gives σ(E) per target for the channels the tool has, on
a fixed energy grid. B5 folds every contributed model into rates.

| Channel | Reaction | Target |
|---|---|---|
| `es_nue` | νₑ + e⁻ → νₑ + e⁻, all recoil energies | electron |
| `es_numu` | ν_μ + e⁻ → ν_μ + e⁻ | electron |
| `es_nutau` | ν_τ + e⁻ → ν_τ + e⁻ | electron |
| `cc_nue_ar40` | νₑ + ⁴⁰Ar → e⁻ + ⁴⁰K* | ⁴⁰Ar nucleus |
| `cc_nue_o16` | νₑ + ¹⁶O → e⁻ + ¹⁶F | ¹⁶O nucleus |
| `cc_nue_c13` | νₑ + ¹³C → e⁻ + ¹³N | ¹³C nucleus |
| `cc_nue_d` | νₑ + d → e⁻ + p + p | deuteron |

| Setting | Value |
|---|---|
| Grid `map` | E = 0.02–20 MeV, step 0.02 (1000 points; fine enough for pp, endpoint 0.42 MeV) |
| Constants | m_e = 0.51099895 MeV; sin²θ_W = 0.23857 (PDG 2024, MS-bar at Q² → 0, for the tree-level reference) |
| Columns | `grid, variant, quantity, energy, value` (cm² per target; NaN outside a tool's table) |
| Checks | values in [0, 10⁻³⁰], NaN allowed, never negative; σ(νₑe) > σ(ν_μe), σ(ν_τe) |

A tool contributes only the channels it has. Variants:

| Variant | Channel | Model |
|---|---|---|
| `default` (required) | all | the tool's own choice per channel |
| `es_bks` | ES | Bahcall, Kamionkowski & Sirlin 1995: electroweak, QCD and QED radiative corrections, all recoil energies (`snufish-reference`: −3.9 to −4.8 % for νₑ, +2.8 to +4.9 % for ν_μ,τ against its tree level) |
| `ar40_klmv` | ⁴⁰Ar | KLMV (Kolbe, Langanke, Martínez-Pinedo, Vogel), SNOwGLoBES table |
| `ar40_marley` | ⁴⁰Ar | MARLEY, allowed approximation, B(GT) from ⁴⁰Ar(p,n) (Bhattacharya 2009); SNOwGLoBES table, zero below 5 MeV |
| `ar40_marley1` | ⁴⁰Ar | MARLEY, B(GT) from ⁴⁰Ti β decay; SNOwGLoBES table, zero below 5 MeV |
| `ar40_marley2_bhattacharya2009` | ⁴⁰Ar | MARLEY 2.0.0 recommended: HF-CRPA continuum + B(GT) of Bhattacharya 2009 |
| `ar40_marley2_liu1998` | ⁴⁰Ar | MARLEY 2.0.0, HF-CRPA + B(GT) of Liu 1998 (⁴⁰Ti β decay) |
| `ar40_marley2_bhattacharya1998` | ⁴⁰Ar | MARLEY 2.0.0, HF-CRPA + B(GT) of Bhattacharya 1998 (⁴⁰Ti β decay) |
| `ar40_marley1_bhattacharya2009` | ⁴⁰Ar | MARLEY's v1 reaction file run by MARLEY 2.0.0, down to threshold |

The MARLEY contribution also writes `bgt_levels.parquet`: the default
model's cross section with one measured level's B(GT) raised by 1σ, for
every level with a measured uncertainty, used to propagate the B(GT)
uncertainty exactly (see [methods.md](methods.md#measured-nuclear-strengths)).

**Products**: `B4_Sigma` (σ and σ/E per tool, variant and channel). Plots:
in the `b45` list.

---

## B5_rates: interaction rates

Interaction rates per detector, channel and flux component before
detector response. SNUfish computes them itself for every B4 model and
every B1 solar model,

  dR/dE = N_targets Φ_c s_c(E) Σ_α P_eα(E) σ_α(E),
  P_eα = Σᵢ F_i |U_αᵢ|²,

with F_i from the B2 reference (daytime, averaged over the component's
production profile). Contributions to B5 are full-chain rates from tools
that fold fluxes themselves, compared with SNUfish's folding of the same
inputs.

| Setting | Value |
|---|---|
| Fluxes | shapes and lines in the spec (shared by all models; [sources.md](sources.md#spectral-shapes)); normalisations from B1 |
| Exposure | 1 kton-year, Julian year (3.15576 × 10⁷ s) |
| Detectors | `argon` (2.71349 × 10³² e⁻, 1.50146 × 10³¹ ⁴⁰Ar per kt; channels `es`, `cc_nue_ar40`); `water` (3.34285 × 10³² e⁻, 3.33472 × 10³¹ ¹⁶O per kt; `es`, `cc_nue_o16`) |
| Channels | `es` sums the three ES channels weighted with P_eα; CC uses P_ee. Thresholds: ⁴⁰Ar 1.504 MeV, ¹⁶O 15.4 MeV; below the B4 grid (0.02 MeV) σ = 0 (< 0.01 % of any rate) |
| Spectra | `linear` (0–20 MeV, 0.1 MeV) and `log` (0.05–20 MeV, 40 per decade) binnings, per MeV of neutrino energy |
| Totals | all energies and E_ν > 5 MeV |

Contributions (grid `totals`, threshold 0 and 5 MeV, quantities
`<detector>/<channel>/<component>` including `all`; interactions per
kton-year):

| Variant | Required | Inputs |
|---|---|---|
| `b16_gs98` | yes | SNUfish inputs for B16-GS98 |
| `bs05_op` | no | SNUfish inputs for BS05-OP |
| `b16_gs98_point_lines` | no | B16-GS98 with each line written as one point of the tool's flux table |
| `native` | no | the tool's own built-in solar flux (SNOwGLoBES: BS05-OP) |

**Products**: `B5_Spectrum`, `B5_Totals` (SNUfish's folding: solar model ×
tool × cross-section model × detector × channel × component, with the
fraction of the spectrum the cross-section table covers), `B5_DayNight`
(the same totals by day, by night and over the year, with A_DN, per site
and Earth model) and `B5_Chain` (tool totals, SNUfish's folding of the
same inputs, their ratio). Plots: `plotipus run b45`.

Night and annual totals are SNUfish's folding only (contributions stay
daytime): P_ee(night) = P_ee(day) + Σᵢ F_i R_i, with the B3 night excess
R_i = ⟨P_iₑ⟩_night − |U_eᵢ|² of the site from the `snufish-reference` B3
contribution (`night.earth_models` in the spec), interpolated on the B3
exposure grid and zero below it (1 MeV; pp and ⁷Be have no night effect
there). The rest of the flux is split between ν_μ and ν_τ as by day (their
ES cross sections are equal). Annual = (day + night)/2, equal exposures,
fluxes at 1 AU. On constant shells the folding agrees with the engine's
(exact solvers, own kernels) to 10⁻⁶ in A_DN; on the continuous models the
engine's NuFast-Earth night differs by its mean-density approximation
([crosschecks.md](crosschecks.md#nufast-earth-on-continuous-density); `tests/test_b5_night.py`).

---

## Combining benchmarks

- **B2 × B3 → day-night.** P_ee(day) = Σᵢ F_i |U_eᵢ|²,
  P_ee(night) = Σᵢ F_i ⟨P_iₑ⟩_night, A_DN = 2(N − D)/(N + D); written by
  `snufish build` as `B23_DayNight`.
- **B1 × B2 × B4 → B5.** Every B4 model folded with every B1 model and its
  B2 oscillations.
- **All of them → the engine.** `snufish.engine` adds the night, the
  detector response and the uncertainties ([methods.md](methods.md)).
