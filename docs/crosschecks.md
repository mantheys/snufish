# Cross-checks against published numbers

`python scripts/crosscheck.py` (add `--exact` for the B2 solver and NuFast-Earth instead of the app tables)
recomputes numbers that experiments and calculations have published, each with the inputs the paper states.
Two kinds of number are compared: **predictions** (the paper's own calculation: SNUfish should reproduce them)
and **measurements** (SNUfish's prediction for them, which should agree within the quoted error).
Day-night asymmetries are in the paper's convention, (D − N)/((D + N)/2).

In the calculator, **Reproduce a published number** (above step 0) sets every step to one of these and shows the
paper's number next to SNUfish's (all but the BKS cross sections, SNO's φ_CC/φ_ES and P_ee, which are not page quantities). The menu is grouped by result (rates, flux ratios, day-night asymmetry); each entry links its paper and,
where the paper prints the numbers for it, recomputes an official figure (Super-K figs. 49 and 52, JUNO fig. 3 and table 7,
SNO fig. 10, Borexino table II) as a Plotly preview and a plotipus figure (web/official.js).

## Predictions: reproduced

| Source | Quantity | Published | SNUfish | Δ |
|---|---|---|---|---|
| BKS 1995, tab. VIII | ⟨σ_e⟩ ⁷Be 862 keV (10⁻⁴⁶ cm²) | 57.9 | 57.87 | 0.0 % |
| | ⟨σ_e⟩ pp, ⁸B, ¹³N, ¹⁵O | 11.6, 594, 45.8, 70.8 | 11.46, 598.5, 45.46, 70.26 | −1.2 to +0.8 % (spectra differ: Bahcall's vs B16's) |
| Borexino 1707.09279, tab. II | pp, ⁷Be, pep rates with B16-GS98 (cpd/100 t) | 131.1, 47.9, 2.74 | 131.8, 47.96, 2.756 | +0.5, +0.1, +0.6 % |
| Super-K 2312.12907, §VII D | Borexino oscillated/unoscillated, pp, pep, ⁷Be | 0.689, 0.614, 0.638 | 0.689, 0.612, 0.633 | ≤ 0.9 % (energy windows not given) |
| JUNO 2006.11760, tab. 1 | ⁸B ES, Δm² 4.8 and 7.5 × 10⁻⁵, all energies and > 2 MeV (cpd/kt) | 4.15, 2.76, 4.36, 2.90 | 4.139, 2.754, 4.343, 2.884 | −0.2 to −0.6 % |
| JUNO 2006.11760, tab. 7 | A_DN at Δm² 4.8 × 10⁻⁵ in 2–16, 5–16, 3–5, 2–3 MeV | −2.9, −3.4, −2.5, −2.1 % | −2.8, −3.4, −2.5, −2.1 % | within the table's rounding |
| Super-K 2312.12907, §VIII | expected A_DN, SK-IV range, Δm² 6.1 × 10⁻⁵ | −2.38 % | −2.32 % | 2.5 % |
| | expected A_DN, SK-I range, Δm² 6.1 and 7.5 × 10⁻⁵ | −2.42, −1.72 % | −2.37, −1.67 % | 2.3, 2.6 % |

JUNO writes the tree-level cross section with g₁ ≈ 0.73, g₂ ≈ 0.23 (sin²θ_W = 0.23). SNUfish's tree level uses
0.23857 and comes out 2.2 % above JUNO's numbers; with radiative corrections (BKS, the default) it is within
0.6 %: the two shifts happen to cancel. Super-K's expected asymmetries come from its amplitude fit, which weights
the zenith-angle shape by energy bin; SNUfish's is the plain rate asymmetry, ~2.5 % smaller in every case.

## Not reproduced

| Source | Quantity | Published | SNUfish | Note |
|---|---|---|---|---|
| Super-K 2312.12907, §VIII | expected A_DN, SK-I range, Δm² 4.8 × 10⁻⁵ | −3.84 % | −3.32 % (exact solvers: same) | 13.5 % off, while 6.1 and 7.5 × 10⁻⁵ agree to 2.5 %. θ13 = 0 gives −3.48 % (exact); not explained. The value is quoted "for reference" at the previously favoured Δm²; it may come from an older calculation. |
| JUNO 2006.11760, sec. 4.2 | expected A_DN, Δm² 7.5 × 10⁻⁵, 2–16 MeV | −1.6 % | −1.38 % | JUNO's own table 1 at this Δm² (1.44 day, 1.46 night) gives −1.4 % ± 0.7 % from rounding, consistent with SNUfish; the −1.6 % in the text is not. |

## Measurements: SNUfish's prediction

| Source | Quantity | Measured | SNUfish | Pull |
|---|---|---|---|---|
| Super-K 2312.12907 | events, 22.5 kt, 2970 days (fig. 28 efficiency, SNO NC flux) | 65,443 ± 1,005 | 64,538 | −0.9σ (the NC flux alone is ±3.8 %) |
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
CallioLab, site dependent) is not modelled: SNUfish's Earth models are radial (PREM variants).

## Investigated

- **PREM's ocean.** Full PREM ends in 3 km of water (1.02 g/cm³), and the B3 detector sits at the surface, in it.
  The day-night asymmetry is most sensitive to the density just under the detector, so for continental sites
  (all of SNUfish's) PREM under-predicts it. With rock (2.6 g/cm³) in place of the ocean (a driver variant in the
  paper repository), Super-K's expected asymmetries go from 2.2–2.8 % above SNUfish's to −0.7 to +1.9 %:
  SK-IV range at 6.1 × 10⁻⁵, −2.314 % → −2.392 % (Super-K: −2.38 %). DUNE's argon CC A_DN at SURF moves
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

## Found by these checks

- **θ13 in the app tables.** The interpolation tables are computed at the default θ13 but were fed every θ13 the
  budget samples: at θ13 = 0 the tables gave A_DN = −1.97 % against the exact −3.41 %. They now follow θ13
  as ν₃ decouples (P_ee = c₁₃⁴ P_ee^(2ν) + s₁₃⁴), within 1.6 % of the exact A_DN over sin²θ13 = 0.015–0.03.
  At NuFIT's θ13 error the sampled A_DN uncertainty was 5.0 % of A_DN instead of 4.6 %; rates were unaffected
  (< 10⁻³).
