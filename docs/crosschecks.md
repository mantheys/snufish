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
elements, sampled over a year). Han et al. compute the same effect from an ephemeris
(arXiv:2607.24421, table 7.1: their flux asymmetry minus their survival-probability asymmetry):

| Site | Han et al. (pp) | SNUfish (pp) |
|---|---|---|
| Jiangmen (JUNO) | 0.347 | 0.359 |
| Kamioka | 0.645 | 0.659 |
| LNGS | 0.808 | 0.821 |
| SURF | 0.867 | 0.880 |
| SNOLAB | 0.939 | 0.951 |

SNUfish is 0.012–0.014 pp above at every site, a common offset not yet explained (Han et al. use the 2026 ephemeris
and their survival-probability asymmetry is itself weighted by (1 AU/R)²). For the ⁸B ES rate above 3.49 MeV
(B16-GS98, NuFIT 6.0, PREM, BKS, perfect resolution), the term takes A_DN from 1.54 % to 1.90 % at Jiangmen, 1.51 %
to 2.16 % at Kamioka and 1.46 % to 2.34 % at SURF: +23 to +60 % of the oscillation-only asymmetry. Left out:
nights near perihelion are also deeper (more core crossings); weighting the nadir exposure by (1 AU/R)² changes
A_DN by +0.05 % (Jiangmen) to +0.14 % (SURF) of itself. The 3D Earth (Han et al.: up to 0.2 pp, ~8 % of A_DN at
CallioLab, site dependent) is not modelled: SNUfish's Earth models are radial (PREM variants).

## Found by these checks

- **θ13 in the app tables.** The interpolation tables are computed at the default θ13 but were fed every θ13 the
  budget samples: at θ13 = 0 the tables gave A_DN = −1.97 % against the exact −3.41 %. They now follow θ13
  as ν₃ decouples (P_ee = c₁₃⁴ P_ee^(2ν) + s₁₃⁴), within 1.6 % of the exact A_DN over sin²θ13 = 0.015–0.03.
  At NuFIT's θ13 error the sampled A_DN uncertainty was 5.0 % of A_DN instead of 4.6 %; rates were unaffected
  (< 10⁻³).
