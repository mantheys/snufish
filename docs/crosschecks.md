# Cross-checks against published numbers

`python scripts/crosscheck.py` (add `--exact` for the B2 solver and NuFast-Earth instead of the app tables)
recomputes numbers that experiments and calculations have published, each with the inputs the paper states.
Two kinds of number are compared: **predictions** (the paper's own calculation: SNUfish should reproduce them)
and **measurements** (SNUfish's prediction for them, which should agree within the quoted error).
Day-night asymmetries are in the paper's convention, (D − N)/((D + N)/2).

In the calculator, **Result Templates** (at the top of the steps) sets every step to one of these and shows the
paper's number next to SNUfish's (all but the BKS cross sections, SNO's φ_CC/φ_ES and P_ee, which are not page quantities). The menu is grouped by result (rates, flux ratios, day-night asymmetry); each entry links its paper and,
where the paper prints the numbers for it, recomputes an official figure (Super-K figs. 49 and 52, JUNO fig. 3 and table 7,
SNO fig. 10, Borexino table II) as a Plotly preview and a plotipus figure (web/official.js).

The DUNE entries are predictions for a detector not yet built. Most count the electron of a νₑ CC event alone, its
de-excitation gammas undetected, as the papers do: the template imports a smearing matrix in neutrino energy
(`electron_smearing` in engine.py, `electronSmearing` in engine.js) that sends each ⁴⁰K level's share of the
MARLEY 2 cross section to T = E_ν − Q − E_level with σ = 7 % T. The page's own visible energy, E_ν − Q, counts the
gammas too and gives about twice the events above 5 MeV.

## Predictions: reproduced

| Source | Quantity | Published | SNUfish | Δ |
|---|---|---|---|---|
| BKS 1995, tab. VIII | ⟨σ_e⟩ ⁷Be 862 keV (10⁻⁴⁶ cm²) | 57.9 | 57.87 | 0.0 % |
| | ⟨σ_e⟩ pp, ⁸B, ¹³N, ¹⁵O | 11.6, 594, 45.8, 70.8 | 11.46, 598.5, 45.46, 70.26 | −1.2 to +0.8 % (spectra differ: Bahcall's vs B16's) |
| Borexino 1707.09279, tab. II | pp, ⁷Be, pep rates with B16-GS98 (cpd/100 t) | 131.1, 47.9, 2.74 | 131.8, 47.96, 2.756 | +0.5, +0.1, +0.6 % |
| Super-K 2312.12907, §VII D | Borexino oscillated/unoscillated, pp, pep, ⁷Be | 0.689, 0.614, 0.638 | 0.689, 0.612, 0.633 | ≤ 0.9 % (energy windows not given) |
| JUNO 2006.11760, tab. 1 | ⁸B ES, Δm² 4.8 and 7.5 × 10⁻⁵, all energies and > 2 MeV (cpd/kt) | 4.15, 2.76, 4.36, 2.90 | 4.139, 2.754, 4.343, 2.884 | −0.2 to −0.6 % |
| JUNO 2006.11760, tab. 7 | A_DN at Δm² 4.8 × 10⁻⁵ in 2–16, 5–16, 3–5, 2–3 MeV | −2.9, −3.4, −2.5, −2.1 % | −2.9, −3.5, −2.5, −2.2 % | within 0.13 pp (the table rounds to 0.1 pp; its statistical errors are 0.9–3.2 pp) |
| Super-K 2312.12907, §VIII | expected A_DN, SK-IV range, Δm² 6.1 × 10⁻⁵ | −2.38 % | −2.34 % | 1.7 % |
| | expected A_DN, SK-I range, Δm² 6.1 and 7.5 × 10⁻⁵ | −2.42, −1.72 % | −2.38, −1.70 % | 1.5, 1.3 % |
| Hajjar, Nairat & Beacom 2606.18347, tab. I | DUNE ⁸B νₑ CC events, electron T > 5 MeV, 20 kt·yr, NuFIT 6.0, SNO flux | 21,722 | 21,914 | +0.9 % |
| Capozzi, Li, Zhu & Beacom 1808.08232 | DUNE ⁸B νₑ CC events, T > 5 MeV, 100 kt·yr, Δm² 4.85 × 10⁻⁵ | 9.9 × 10⁴ / 0.88 = 1.125 × 10⁵ | 1.061 × 10⁵ | −5.7 % |
| | DUNE ⁸B ES events, T > 5 MeV, 100 kt·yr | 2.6 × 10⁴ / 0.81 = 3.21 × 10⁴ | 3.41 × 10⁴ | +6.2 % |
| | DUNE hep νₑ CC events, T > 11 MeV, 100 kt·yr | 150 | 155 | +3.3 % (hep flux 7.95 × 10³ here, 8.25 × 10³ there) |
| Ioannisian, Smirnov & Wyler 1702.06097, sec. IV | DUNE ⁸B νₑ CC events with E_ν > 11 MeV, 40 kt, one year | 27,000 | 27,871 | +3.2 % |
| | A_DN, E_ν > 11 MeV, Δm² 7.5 and 5.0 × 10⁻⁵ ("about 4 %" and "6.5 %" as N/D − 1) | −3.92, −6.30 % | −3.83, −6.75 % | 2.4, 7.2 % |

JUNO writes the tree-level cross section with g₁ ≈ 0.73, g₂ ≈ 0.23 (sin²θ_W = 0.23). SNUfish's tree level uses
0.23857 and comes out 2.2 % above JUNO's numbers; with radiative corrections (BKS, the default) it is within
0.6 %: the two shifts happen to cancel. SNUfish's Super-K asymmetries are 1.3–1.7 % smaller than
Super-K's because PREM ends in 3 km of ocean (see Investigated): with rock in its place they agree to −0.7 to +1.9 %.

Capozzi et al. count events outside (CC) or inside (ES) a 40° cone around the Sun that holds 88 % and 81 % of them;
the published number is their count divided by that fraction, and both are rounded, so the ±6 % (in opposite
directions for CC and ES) is within what the paper lets one reconstruct. Ioannisian et al. use an approximate cross
section (σ ∝ p_e E_e above 5.8 MeV) and do not state their oscillation parameters (NuFIT 6.0 here, with their Δm²);
their asymmetries are quoted as "about".

## Not reproduced

| Source | Quantity | Published | SNUfish | Note |
|---|---|---|---|---|
| Super-K 2312.12907, §VIII | expected A_DN, SK-I range, Δm² 4.8 × 10⁻⁵ | −3.84 % | −3.37 % (exact solvers: same) | 12.3 % off, while 6.1 and 7.5 × 10⁻⁵ agree to 1.7 %. θ13 = 0 gives −3.48 % (exact); not explained. The value is quoted "for reference" at the previously favoured Δm²; it may come from an older calculation. |
| Capozzi, Li, Zhu & Beacom 1808.08232 | DUNE A_DN, νₑ CC, electron T > 6 MeV, Δm² 4.85 × 10⁻⁵ (from D = 3.04 × 10⁴, N = 3.29 × 10⁴) | −7.90 % | −6.96 % (four-region PREM: −8.68 %) | 12 % off. At DUNE's energies the asymmetry follows the Earth's outer layers: the ten-region PREM, with its crust, and the four-region one, without, bracket the paper's value. The paper describes its Earth treatment only through its ref. 49. |
| JUNO 2006.11760, sec. 4.2 | expected A_DN, Δm² 7.5 × 10⁻⁵, 2–16 MeV | −1.6 % | −1.38 % | JUNO's own table 1 at this Δm² (1.44 day, 1.46 night) gives −1.4 % ± 0.7 % from rounding, consistent with SNUfish; the −1.6 % in the text is not. |

## Measurements: SNUfish's prediction

| Source | Quantity | Measured | SNUfish | Pull |
|---|---|---|---|---|
| Super-K 2312.12907 | events, 22.5 kt, 2970 days (fig. 28 efficiency, SNO NC flux) | 65,443 ± 1,005 | 64,541 | −0.9σ (the NC flux alone is ±3.8 %) |
| | ⁸B flux / SNO NC flux | 2.314/5.25 = 0.441 ± 0.009 | 0.433 | −0.9σ |
| SNO nucl-ex/0502021 | φ_CC/φ_NC | 0.340 −0.039 +0.037 | 0.334 | −0.2σ |
| | φ_ES/φ_NC | 0.476 ± 0.06 | 0.438 | −0.6σ |
| | φ_CC/φ_ES | 0.712 ± 0.087 | 0.762 | +0.6σ |
| SNO 1109.0763 | daytime P_ee(10 MeV) | 0.317 ± 0.018 | 0.326 | +0.5σ |
| Borexino 1709.00756 | ⁸B rate above 3.2 MeV, B16-GS98 flux (cpd/100 t) | 0.223 ± 0.016 | 0.216 | −0.4σ |

## Earth–Sun distance

Published day-night asymmetries are at 1 AU: experiments correct each event for the Earth–Sun distance. The flux
at the detector is not, and because a northern site's longest nights fall near perihelion, the eccentricity alone
makes the night flux larger. With **include the Earth–Sun distance** (`Setup(orbit=True)`), day and night rates are
scaled by the mean (1 AU/R)² over the site's days and nights (`exposure.orbital_factors`: a Kepler orbit with J2000
elements, sampled over a year, R from the detector: by night it is one Earth radius × cos(zenith) farther from the
Sun, −0.009 pp). Han et al. compute the same effect from an ephemeris
(arXiv:2607.24421, table 7.1: their flux asymmetry minus their survival-probability asymmetry):

| Site | Han et al. (pp) | SNUfish (pp) |
|---|---|---|
| Jiangmen (JUNO) | 0.347 | 0.349 |
| Kamioka | 0.645 | 0.650 |
| LNGS | 0.808 | 0.813 |
| SURF | 0.867 | 0.872 |
| SNOLAB | 0.939 | 0.944 |

Measured from the Earth's centre, SNUfish was 0.012–0.014 pp above at every site; the detector's position (the
diurnal parallax) accounts for 0.009 pp of it. The remaining 0.002–0.005 pp is below the precision of the table. For the ⁸B ES rate above 3.49 MeV
(B16-GS98, NuFIT 6.0, PREM, BKS, perfect resolution), the term takes A_DN from 1.54 % to 1.90 % at Jiangmen, 1.51 %
to 2.16 % at Kamioka and 1.46 % to 2.34 % at SURF: +23 to +60 % of the oscillation-only asymmetry. Left out:
nights near perihelion are also deeper (more core crossings); weighting the nadir exposure by (1 AU/R)² changes
A_DN by +0.05 % (Jiangmen) to +0.14 % (SURF) of itself. The 3D Earth (Han et al.: up to 0.2 pp, ~8 % of A_DN at
CallioLab, site dependent) is the crust along each chord here ([below](#crust-along-each-chord-3d)), without a 3D
mantle.

## Investigated

- **PREM's ocean.** Full PREM ends in 3 km of water (1.02 g/cm³), and the B3 detector sits at the surface, in it.
  The day-night asymmetry is most sensitive to the density just under the detector, so for continental sites
  (all of SNUfish's) PREM under-predicts it. With rock (2.6 g/cm³) in place of the ocean (a driver variant in the
  paper repository), Super-K's expected asymmetries went from 2.2–2.8 % above SNUfish's to −0.7 to +1.9 %:
  SK-IV range at 6.1 × 10⁻⁵, −2.314 % → −2.392 % (Super-K: −2.38 %); NuFast-Earth's mean density per crossing then,
  50 km shells now (−2.34 % with the ocean). DUNE's argon CC A_DN at SURF moves
  by +4.9 % of itself. `prem_prob3` and `prem_four` have no crust at all (3.3 and 3.8 g/cm³ at the surface) and
  give 14–33 % larger asymmetries: as a model range they measure the missing crust, not an Earth-model uncertainty.
- **Super-K at 4.8 × 10⁻⁵.** Super-K's 2014 paper (arXiv:1312.5176) expects −3.3 % at Δm² = 4.8 × 10⁻⁵
  (sin²θ12 = 0.342, sin²θ13 = 0.025, the same energy range); SNUfish gives −3.27 % there. The −3.84 % of the 2023
  paper disagrees with Super-K's own earlier calculation and with the Δm² dependence of its other two values; of the
  inputs SNUfish varies, only the crustless Earth models move A_DN by more than 4 % (mixing angles, θ13, crust,
  resolution, solar model: < 4 %).
- **JUNO at 7.5 × 10⁻⁵.** The −1.6 % of the text is not JUNO's table 1 (1.44 and 1.46 cpd/kt: −1.38 %, with
  rounding anywhere from −0.7 % to −2.1 %); SNUfish agrees with the table (−1.37 %).
- **SNOwGLoBES's MARLEY table has no Coulomb factor.** The allowed cross section from the (p,n) strengths of
  Bhattacharya et al. 2009 reproduces `xs_nue_Ar40_marley.dat` (`ar40_marley`) to 4–6 % *without* the Fermi
  function, and MARLEY's own calculation with the same strengths (`ar40_marley1_bhattacharya2009`) to 3 % *with*
  it: the SNOwGLoBES table is 35–40 % low at 8–14 MeV. With MARLEY's calculation SNUfish reproduces DEAP-3600's
  prediction (arXiv:2605.12769: ⟨σ⟩ = 1.67 × 10⁻⁴¹ cm² over E_ν = 12–14.5 MeV, 2.3 events): 1.60 × 10⁻⁴¹ cm²,
  2.24 events. The "factor 5–7 at 5 MeV" between nuclear models comes from this table and from tables cut at
  5 MeV; at the E_ν ≳ 9 MeV a 5 MeV DUNE threshold sees, the MARLEY calculations differ by 13 % (6.1–6.9 × 10⁻⁴² cm²
  at 10 MeV).

## ⁴⁰Ar: independent calculations

Folded over the ⁸B spectrum (Winter et al.), no threshold, 10⁻⁴² cm²:

| Calculation | ⟨σ⟩ | Source |
|---|---|---|
| MARLEY 2, B(GT) from ⁴⁰Ar(p,n) 2009 | 2.72 | SNUfish from MARLEY 2.0.0 |
| MARLEY 2, B(GT) from ⁴⁰Ti decay (Liu 1998 / Bhattacharya 1998) | 2.42 / 2.43 | SNUfish from MARLEY 2.0.0 |
| Shell model, Kostensalo, Suhonen & Zuber, g_A = 1.00(5) | 1.78(23) (1.725 from its table) | PRC 97, 034309 (2018) |
| the same with the free g_A = 1.27 | 2.64 | PRC 97, 034309 (2018), sec. III E |

With electrons above 5 MeV (gammas undetected), Suzuki & Honma's shell model (PRC 87, 014607 (2013),
[arXiv:1211.4078](https://arxiv.org/abs/1211.4078); its GT strength reproduces the (p,n) data) gives 14.05 ×
10⁻⁴³ cm² for the GT and Fermi transitions; MARLEY 2 with the (p,n) strengths gives 13.66 (−2.8 %,
`tests/test_ar40_models.py`). The calculations that use or reproduce the measured strengths agree; the
shell model with g_A = 1.00 is 27–35 % lower, and with the free g_A within the MARLEY 2 spread. How much the
Gamow–Teller operator is quenched in ⁴⁰Ar is the open question behind the state-of-the-art range for argon.

## Local crust

The CRUST1.0 column under each detector in place of PREM's ocean and average crust (`prem_crust1`) moves
the annual ⁸B A_DN (B23-MB22m, JUNO 2025, exact solvers on 50 km shells, `scripts/earth3d_literature.py --part
sites`), of itself:

| Site | ES in water, T > 3.49 MeV | CC on ⁴⁰Ar, E_vis > 5 MeV |
|---|---|---|
| Kamioka | +1.41 % | +1.05 % |
| LNGS | +2.13 % | +1.54 % |
| SURF | −1.71 % | −2.54 % |
| SNOLAB | +3.70 % | +2.78 % |
| Jiangmen | +2.84 % | +2.40 % |

SURF's crust is 49 km thick and lighter than the PREM mantle it replaces; the others gain dense rock where PREM
has ocean. (Before the night was cut into thin shells, NuFast-Earth's mean density per region crossing put
these at +1.5, +2.2, −2.4 (argon), +3.8 and +3.0 % (ES above 2 MeV).)

## Crust along each chord (3D)

`prem_crust1_3d` (`snufish.earth3d`) takes, at every point of a night chord within the crust, the layer of the
CRUST1.0 cell the point lies under (the whole 1° × 1° grid, `reference/earth/crust1_global.npz`), and PREM under
the local Moho. The chords are the Sun's directions every 2 minutes over 2026 at the site's latitude and
longitude (solar coordinates of the Astronomical Almanac, the Earth rotation angle); the nadir exposure stays
B3's W(η), so the model differs from `prem_crust1` by the crust alone. Each of the 1001 cells in cos η is
solved once, with the crust of its ~130 chords averaged at equal distance from the detector and from the entry
point, in NuFast-Earth's single-trajectory mode (the B3 driver's `trajectories:FILE`), the chord cut where the
density changes by 0.05 g/cm³ or every 50 km. Checks (`tests/test_earth3d.py`):

- the driver solves a chord in the neutrino's order (from the entry point), against the B3 reference
  propagator on an asymmetric chord, to 10⁻⁷;
- with the detector's column put everywhere, the chords give `prem_crust1` (Magnus, 10 km shells) to
  2 × 10⁻⁴ in P_iₑ, and A_DN within 0.05 % at 5, 10 and 15 MeV over the whole night;
- the time sampling of the Sun reproduces W(η) of Lisi & Montanino within 1 % per 0.1 in cos η;
- averaging the crust within a cell before solving, instead of averaging P over its chords: ≤ 1.3 × 10⁻⁴ in
  P₂ₑ at Kamioka (0.3 % of the regeneration at cos η = 0.05, 10⁻⁴ of it elsewhere), while single chords
  differ from each other by 3 × 10⁻⁴ to 6 × 10⁻³ (first order in the density change, so the average commutes);
- piece size: A_DN of ⁸B within 0.07 % of 10 km pieces at 4–20 MeV.

Against the local crust under the detector, the crust along each chord moves the annual A_DN by **−0.17 to
+0.16 %** of itself at the five sites (ES in water above 3.49 MeV: Kamioka −0.17 %, LNGS −0.05 %, SURF −0.09 %,
SNOLAB −0.04 %, Jiangmen +0.03 %; CC on ⁴⁰Ar above 5 MeV: 0.00, +0.05, +0.16, −0.01, +0.05 %). The far side
of a chord barely matters: its contribution to the regeneration is averaged out over the phases of the many
chords, as Ioannisian, Smirnov & Wyler and Bakhti & Smirnov find for structure far from the detector; what the
asymmetry sees is the crust near the detector, which `prem_crust1` already has. The two are the current Earth
models and their spread is B3's model range.

**Published numbers.** Han et al. ([arXiv:2607.24421](https://arxiv.org/abs/2607.24421), table 7.1) compute the
day-night asymmetry of the ⁸B νₑ flux (0.1–16 MeV, B16-GS98, PDG 2025 parameters) through PREM (Yₑ = 0.50 and
0.467) and through a 3D Earth, LITHO1.0 (crust and lithosphere to 320 km) on the SAW642AN mantle; the shift Δ is
"up to ∼8 %" of A_DN in their text, 6.3 % at CallioLab and at most 4.8 % at SNUfish's sites in their table.
Their 1D value is A^osc_DN − Δ (pp):

| Site | 1D, Han et al. | 1D, SNUfish (their Yₑ) | Δ, Han et al. (LITHO1.0 + SAW642AN) | local crust (`prem_crust1`) | crust along each chord (`prem_crust1_3d`) |
|---|---|---|---|---|---|
| Kamioka | 1.382 | 1.376 | +0.025 | +0.029 | +0.024 |
| LNGS | 1.352 | 1.347 | +0.001 | +0.044 | +0.041 |
| SURF | 1.342 | 1.331 | +0.049 | +0.001 | −0.003 |
| SNO (SNOLAB) | 1.329 | 1.323 | +0.064 | +0.070 | +0.069 |
| JUNO (Jiangmen) | 1.427 | 1.413 | +0.050 | +0.050 | +0.050 |

(`scripts/earth3d_literature.py --part han`; SNUfish's shifts are from `prem_full`, with B3's Yₑ.) The 1D
asymmetry is reproduced to 0.4–1 %. The 3D shift is reproduced to 0.005 pp at Kamioka, SNOLAB and Jiangmen,
and not at LNGS (+0.041 against +0.001 pp) and SURF (−0.003 against +0.049 pp): there LITHO1.0 and CRUST1.0
differ, or the SAW642AN mantle matters; the table does not separate the two. Most of Han et al.'s shift is the
crust near the detector, which SNUfish counts in both current models: the ~8 % is not on top of it. The
difference between two crust models, ~0.05 pp or 3–4 % of A_DN at LNGS and SURF, is larger than the spread of
SNUfish's two current models and is not in it: a second crust model (LITHO1.0) is the next step.

Bakhti & Smirnov ([arXiv:2001.08030](https://arxiv.org/abs/2001.08030), sec. IV; Hyper-K, ES with T > 6.5 MeV,
σ_E/E = 15 %, A_ND = N/D − 1, Δm²₂₁ = 7.5 × 10⁻⁵, θ₁₃ = 8.4°, θ₁₂ not stated: 0.307 here) find A_ND = 0.022 with
CRUST1.0 and "about 5 %" more with a PREM whose crust reaches the surface (no ocean). SNUfish
(`--part bakhti`, B16-GS98): 0.0201 with that PREM, 0.0195 with either CRUST1.0 model, 2.7 % smaller; with
PREM's ocean, 0.0193. The direction is reproduced, the size half; their absolute value is 11 % higher (first
order in the matter potential, θ₁₂ and fluxes not stated).

## NuFast-Earth on continuous density

NuFast-Earth replaces each crossing of a PREM region by the region's mean density along it. Against the B3
reference for continuous density (fourth-order Magnus, converged to 4 × 10⁻⁷), P_iₑ is off by up to
5.5 × 10⁻² (median 2–4 × 10⁻⁵ over the B3 grids), most through the core (cos η ≈ 0.95–1), while on constant shells
(`prem_prob3`) NuFast-Earth agrees with the exact solution to 9 × 10⁻⁸. Night-averaged, the ⁸B A_DN
(B16-GS98, B3 parameters, P_ee at the neutrino energy, as `B23_DayNight`):

| Earth model, site | 5 MeV | 10 MeV | 15 MeV |
|---|---|---|---|
| `prem_crust1`, Kamioka | −0.68 % | −0.70 % | −1.88 % |
| `prem_crust1`, SURF | −0.17 % | −1.27 % | −1.31 % |
| `prem_full`, Kamioka | −0.80 % | −0.78 % | −1.93 % |
| `prem_four`, SURF | +1.29 % | +0.90 % | +0.61 % |

(NuFast-Earth / reference − 1.) Energy by energy over 4–20 MeV the bias oscillates with energy, between
−5.1 % and +2.9 % for `prem_full` and −2.0 % and +4.3 % for `prem_four` across the five sites
(`B23_DayNight`, the two tools on the same Earth models); rates integrate it down to the table's size. Cutting each polynomial region into thin shells in the
regions file NuFast-Earth reads removes it (25 km: within 0.007 % of the reference at both sites; 10 km:
0.004 %), which also confirms the reference independently.

**The calculator's night is now on 50 km shells** (`scan.SPLIT_KM`; the app tables, `ExactProbabilities` and
`snufish scan`; `split_km=None` gives NuFast-Earth's own treatment, which its B3 contribution keeps). Against
10 km shells the night-averaged ⁸B A_DN at 4–20 MeV is then within 0.05 % (`prem_crust1` at Kamioka and SURF,
`prem_full`) and 0.10 % (`prem_four`), energy by energy; without the cut, 2.9–3.6 %; 25 km shells: 0.03 %,
for 1.4× the time of 50 km. The cost: a night grid takes 1.6× the driver time of the mean density per crossing
(0.42 against 0.27 s for `prem_crust1`); the tables keep their size (the night is averaged before it is
stored). The B3 row "mean density per region crossing" of the benchmark pages is the shift NuFast-Earth's own
treatment would put on the calculator's result: the exact solvers without and with the cut, the latter what the
tables hold.

## Found by these checks

- **θ13 in the app tables.** The interpolation tables are computed at the default θ13 but were fed every θ13 the
  budget samples: at θ13 = 0 the tables gave A_DN = −1.97 % against the exact −3.41 %. They now follow θ13
  as ν₃ decouples (P_ee = c₁₃⁴ P_ee^(2ν) + s₁₃⁴), within 1.6 % of the exact A_DN over sin²θ13 = 0.015–0.03.
  At NuFIT's θ13 error the sampled A_DN uncertainty was 5.0 % of A_DN instead of 4.6 %; rates were unaffected
  (< 10⁻³).
