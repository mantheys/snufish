# State of the art, legacy and approximations

SNUfish offers ten solar models, seven oscillation parameter sets, four
Earth models, three ν–e cross sections and nine ν<sub>e</sub>–⁴⁰Ar models.
They are not equals. Some are the current best calculations and
measurements and compete with each other; some have been superseded and are
kept because published numbers were computed with them; some are
simplifications of a current input. Only the first group says anything
about the uncertainty of a prediction today. This page records which is
which and why, from the literature as of November 2026. The machine-readable
version is [reference/status.yaml](../reference/status.yaml); the engine,
the calculator, the benchmark pages and `snufish status` read it.

| Status | Meaning | How SNUfish treats it |
|---|---|---|
| **state of the art** (`current`) | The latest calculation or measurement. Where several exist they compete. | Their spread is the model range of a budget. |
| **legacy** | Superseded by a later calculation or measurement of the same thing. | Selectable and labelled; out of the model ranges; shown apart as a "legacy spread" (context). |
| **approximation** | A simplified version of a current input. | As legacy: its difference from the current input is the error of the approximation. |
| **as used in a paper** (`reproduction`) | The parameter values a reproduced paper states. | Used by the Result Templates only. |

A difference between a legacy input and the state of the art is an outdated
input, not an uncertainty: folding it into an error bar inflates it, and
quoting a legacy result as current biases it. Deviations between
state-of-the-art inputs are the ones that matter, and the only ones
SNUfish reports as model ranges.

## What we have learned

1. **The tools agree; the inputs do not.** NuFast-Earth and the SNUfish
   reference agree to 10⁻⁸, the two radiative-correction calculations of
   ν–e scattering to 0.1 %. Every spread that matters comes from physics
   inputs.
2. **Most of the large spreads were outdated inputs, not uncertainties.**
   The factor 5–7 between ⁴⁰Ar tables at 5 MeV (SNOwGLoBES tables cut at
   5 MeV and without the Coulomb factor), A<sub>DN</sub> up to 40 % high (Earth
   models without a crust), +6.5 % on the ⁸B flux (B16's older nuclear
   rates).
3. **Solar composition: the open model uncertainty of the fluxes.** B23
   with MB22 against AAG21: ⁸B −16 %, ⁷Be −8 %, CNO −30 %. The neutrino data
   prefer MB22 (AAG21 disfavoured by up to 2.5σ on CNO), not decisively.
4. **⁴⁰Ar: how much the Gamow–Teller strength is quenched, about 37 %.**
   MARLEY 2 with the measured strengths and the shell model of Suzuki &
   Honma agree to 3 %; the shell model of Kostensalo et al. with g<sub>A</sub> =
   1.00 is 27–35 % lower, and with the free g<sub>A</sub> it agrees. The three
   measured strength sets differ by 11 % among themselves. A cross-section
   measurement at a stopped-pion source would settle it.
5. **Earth: the crust under the detector matters at a few per cent; 3D is
   not yet computed.** The CRUST1.0 column moves A<sub>DN</sub> by −2.4 % (SURF)
   to +3.8 % (SNOLAB). The crust where neutrinos enter and the 3D mantle
   (up to ~8 % in the literature) are missing, so there is no Earth range yet.
6. **Oscillations: JUNO now fixes Δm²₂₁ and θ₁₂.** Solar data alone give
   Δm²₂₁ about 1.5σ lower: a physics question, not a choice of input.

The model ranges, state of the art against everything SNUfish offers
(B23-MB22m, JUNO 2025, PREM with the local crust, annual rates):

| Observable | Choice | State of the art | With legacy and approximations |
|---|---|---|---|
| ⁸B + hep ES in water, T > 3.49 MeV | solar model | −15.9 % (AAG21) | −19.3 % to +10.6 % |
| | ES cross section | +0.02 % | +2.8 % (tree level) |
| ⁸B CC on ⁴⁰Ar, E<sub>vis</sub> > 5 MeV | ⁴⁰Ar nuclear model | −36.6 % (shell model, g<sub>A</sub> = 1.00) | −37 % to +1.8 % |
| | solar model | −16.0 % | −19.4 % to +10.6 % |
| ⁷Be ES in scintillator | solar model | −7.8 % | −11.5 % to +0.6 % |
| A<sub>DN</sub>, ⁸B ES at Kamioka | Earth model | none (one current model): 1.52 % | 1.50 % to 2.07 % |
| A<sub>DN</sub>, ⁸B CC on ⁴⁰Ar at SURF | Earth model | none: 2.84 % | 2.84 % to 4.02 % |

## Solar models

**State of the art: B23 with MB22 (meteoritic and photospheric scales) and
B23 with AAG21.** B23 (Herrera & Serenelli,
[doi:10.5281/zenodo.10174172](https://doi.org/10.5281/zenodo.10174172))
is the current generation of standard solar models, with the nuclear rates
of Solar Fusion III (Rev. Mod. Phys. 97, 035002 (2025)). It is computed for
five compositions. Two are recent 3D NLTE determinations of the solar
photosphere that disagree with each other: Magg et al. 2022 (MB22, A&A
661, A140, [arXiv:2203.02255](https://arxiv.org/abs/2203.02255)), high
metallicity, Z/X ≈ 0.0225, in agreement with helioseismology; and Asplund,
Amarsi & Grevesse 2021 (AAG21, A&A 653, A141,
[arXiv:2105.01661](https://arxiv.org/abs/2105.01661)), low metallicity.
That disagreement is the solar composition (abundance) problem, open since
2009. Solar neutrinos now take part in it: with the Borexino CNO rate,
the global analysis of Gonzalez-Garcia, Maltoni, Pinheiro & Serenelli
(JHEP 02 (2024) 064, [arXiv:2311.16226](https://arxiv.org/abs/2311.16226))
finds B23-MB22 compatible with the data (1.0σ on all fluxes, 1.4σ on CNO)
and B23-AAG21 disfavoured (1.9σ and 2.5σ), not excluded. NuFIT 6.0 adopts
B23-MB22 (meteoritic) as its reference model
([arXiv:2410.05380](https://arxiv.org/abs/2410.05380)). The calculator
defaults to B23-MB22m; the range MB22–AAG21 is the solar-model
uncertainty.

**Legacy.** B23-GS98 (Grevesse & Sauval 1998) and B23-AGSS09 (Asplund et
al. 2009): the same solar physics with the older abundance compilations,
which MB22 and AAG21 respectively supersede (MB22 has a Z/X close to
GS98's; AAG21 is the AGSS09 group's revision). B23-C11 (Caffau et al.
2011, intermediate metallicity) has not been revised. B16 (Vinyoles et al.
2017, [arXiv:1611.09867](https://arxiv.org/abs/1611.09867)) and BS05
(Bahcall, Serenelli & Basu 2005) are previous generations, with older
nuclear rates; B16-GS98 is what Borexino (2018) and Super-K (2024) compared
with, so it stays for their numbers. B16-GS98's ⁸B flux is 6.5 % above
B23-MB22m's.

**Not included.** The 2025 composition revisions (Lodders & Bergemann;
[arXiv:2503.05402](https://arxiv.org/abs/2503.05402)) have no published
standard solar model yet.

## Oscillation parameters

**State of the art.** JUNO's first result (59 days,
[arXiv:2511.14593](https://arxiv.org/abs/2511.14593)) is the most precise
measurement of Δm²₂₁ and θ₁₂ and dominates any global fit. NuFIT 6.1
(Esteban et al., [arXiv:2601.09791](https://arxiv.org/abs/2601.09791),
eq. 3.1) includes it: sin²θ₁₂ = 0.3096 −0.0073 +0.0057, Δm²₂₁ = 7.530
−0.097 +0.096 × 10⁻⁵ eV² (added as `nufit61_global`; θ₁₃, θ₂₃, δ and Δm²₃₁
stay at the NuFIT 6.0 values used for every set). The solar-only sets
(all solar, SK + SNO; Super-K, [arXiv:2312.12907](https://arxiv.org/abs/2312.12907))
are also current: they are the other side of the solar–reactor comparison
of Δm²₂₁ (6.1 against 7.5 × 10⁻⁵ eV², about 1.5σ). That difference is a
physics question SNUfish is built to look at (`snufish scan`), not a choice
between inputs, so the calculator does not fold it into a range either.

**Legacy.** NuFIT 6.0 (before JUNO; superseded by 6.1), KamLAND 2013 (the
reactor input before JUNO; less precise in both parameters than JUNO's 59
days) and solar + KamLAND 2024 (its reactor side superseded by JUNO).

## Earth

**State of the art: PREM with the local crust (`prem_crust1`).** PREM
(Dziewonski & Anderson 1981) remains the reference Earth for neutrino
propagation, but its top 24 km are an average crust ending in 3 km of
ocean, and the day-night asymmetry is most sensitive to the density the
neutrinos cross last. `prem_crust1` keeps PREM under the Moho and puts the
CRUST1.0 column of the detector's 1° × 1° cell above it (Laske et al.
2013; `reference/earth/crust1_sites.yaml`): continental crust 30–49 km
thick at the five sites. A<sub>DN</sub> of ⁸B moves by −2.4 % (SURF, whose
49 km crust is lighter than the mantle PREM puts there) to +3.8 % (SNOLAB)
of itself ([crosschecks.md](crosschecks.md)). It is solved by NuFast-Earth
like PREM (the driver's `regions:` model), checked to reproduce PREM
exactly when given PREM's regions.

Still not modelled, so still not a range: the crust where a chord enters
the Earth (the column under the detector stands for the whole surface)
and the 3D mantle, which move A<sub>DN</sub> by up to ~8 % at some sites
(Han et al.; Bakhti & Smirnov, [arXiv:2001.08030](https://arxiv.org/abs/2001.08030)).
With one state-of-the-art Earth model the calculator reports no Earth
range; that is a missing uncertainty, not a small one.

**Approximations.** `prem_full` (PREM's ocean and average crust under
every detector), `prem_four` (the four main PREM regions, the mantle
extended to the surface) and `prem_prob3` (four constant shells). The last
two have no crust: A<sub>DN</sub> of ⁸B comes out about 40 % and 20 % above
`prem_full`. `prem_full` stays the B3 reference model and `prem_prob3` the
B3 tool comparison (every solver can do it exactly).

## ν–e elastic scattering

**State of the art: BKS and SNOwGLoBES (Marciano & Parsa).** The O(α)
corrections of Bahcall, Kamionkowski & Sirlin (PRD 51, 6146 (1995),
[astro-ph/9502003](https://arxiv.org/abs/astro-ph/9502003)) give the
electron-recoil spectrum the solar experiments use; SNOwGLoBES's tables are
the radiatively corrected total cross sections of Marciano & Parsa (J.
Phys. G 29, 2629 (2003)). They agree to 0.1 %. The most precise
calculation today is Tomalak & Hill (PRD 101, 033006 (2020),
[arXiv:1907.03379](https://arxiv.org/abs/1907.03379)): it reproduces the
electron spectrum of the earlier O(α) work and puts the theory uncertainty
at 0.2–0.4 % (the hadronic contribution). It is not implemented; at the
solar precision the BKS–Marciano-Parsa range already bounds it.

**Approximation.** Tree level: about 2 % above the corrected cross section
for ⁸B, 3–4 % at the highest recoil energies.

## Cross sections on nuclei

**⁴⁰Ar, state of the art: MARLEY 2 with the three sets of measured
Gamow–Teller strengths, and the shell model of Kostensalo, Suhonen & Zuber.**
At solar energies the cross section is dominated by Gamow–Teller
transitions to bound ⁴⁰K levels, whose strengths are measured, in
⁴⁰Ar(p,n) (Bhattacharya et al. 2009) and in the mirror ⁴⁰Ti β decay (Liu
et al. 1998; Bhattacharya et al. 1998); the measurements do not agree.
MARLEY 2.0.0 (2026) combines each with an HF-CRPA continuum (Gardiner, PRC
103, 044604 (2021), [arXiv:2010.02393](https://arxiv.org/abs/2010.02393);
Gardiner et al., [arXiv:2604.26801](https://arxiv.org/abs/2604.26801)).
Kostensalo, Suhonen & Zuber (PRC 97, 034309 (2018), table I;
`reference/xsec/kostensalo2018.yaml`) compute every transition in the
shell model instead, with a quenched g<sub>A</sub> = 1.00(5): their ⁸B-folded
cross section, 1.78(23) × 10⁻⁴² cm², is 27–35 % below the MARLEY 2
calculations (2.42–2.72), and with the free g<sub>A</sub> = 1.27 (2.64) it falls
inside them. The shell model of Suzuki & Honma (PRC 87, 014607 (2013)),
whose Gamow–Teller strength reproduces the (p,n) data, agrees with MARLEY 2
to 3 % on the cross section with electrons above 5 MeV, the one number it
publishes ([crosschecks.md](crosschecks.md)). The state-of-the-art range,
the four of them, is now about 37 % on the ⁸B rate: the quenching of the
Gamow–Teller strength in ⁴⁰Ar is unsettled, and a direct measurement (a
LArTPC at a stopped-pion source) would settle it.

The shell-model table is coarse (5 MeV steps); interpolated log-log in
E − Q it reproduces the paper's folded value to 3 %. Suzuki & Shimizu
(PRC 108, 014611 (2023), [arXiv:2304.11358](https://arxiv.org/abs/2304.11358))
confirm Suzuki & Honma's Gamow–Teller cross sections to 5 % with a chiral
effective interaction but publish no table; neither shell-model σ(E) of
that group is in SNUfish.

**⁴⁰Ar, legacy.** MARLEY's v1 model (allowed approximation over all
levels), SNOwGLoBES's 2018 MARLEY tables (zero below 5 MeV, and without the
Coulomb factor: [crosschecks.md](crosschecks.md)), KLMV (Kolbe, Langanke,
Martínez-Pinedo & Vogel 2003, RPA) and SNOwGLoBES's default table (the
Gil-Botella & Rubbia / KLMV era). The RPA calculations predate the measured
strengths that dominate at solar energies.

**¹⁶O.** Kolbe, Langanke & Vogel (PRD 66, 013007 (2002)), as tabulated by
SNOwGLoBES: the only model here, so current by default and without a range.

**Deuterium.** Nakamura et al. (Nucl. Phys. A 707, 561 (2002)), ±1 %, used
by SNO; the effective-field-theory calculation of Butler, Chen & Kong
agrees to about 1 %. Current.

## Other inputs

- **⁸B spectrum.** Winter et al. 2006, the shape every solar experiment
  uses, is current. Longfellow et al. (PRC 107, L032801 (2023)) measured it
  again with trapped ions; it is not yet a variant (see
  [status.md](status.md), spectral-shape variants).
- **Measured ⁸B flux.** SNO's neutral-current flux as Super-K applies it is
  current.
- **Solvers.** The SNUfish reference solvers and NuFast-Earth
  ([arXiv:2511.04735](https://arxiv.org/abs/2511.04735)) agree to 10⁻⁸ on
  B3; the tools are not a source of spread, the inputs are.

## Where it shows

- **Calculator.** Every selector lists the state-of-the-art choices first
  and labels the others (`· legacy`, `· approximation`); a note under each
  control gives the reason and what supersedes it. The result says whether
  every input is current; if not, which are not and what that means. Model
  ranges are the state-of-the-art spread; the spread with legacy models
  and approximations is listed apart, greyed in the uncertainty plot and
  marked `legacy spread` in the budget table and the download. The default
  setup is current (JUNO 2025, B23-MB22m, PREM with the local crust, BKS, MARLEY 2). Result
  Templates use each paper's own inputs, which are usually legacy, and say
  so.
- **Home page.** The table of every input and its status (from
  `data/inputs.json`).
- **Benchmark pages.** Legacy models and approximations are labelled in
  every legend; the overview counts state-of-the-art ranges only.
- **Command line.** `snufish status` prints the table; `snufish budget`
  and `snufish scan` print a note for any legacy input they are given; the
  Python engine's `status`, `not_current` and `budget(..., legacy=True)`
  give the same.

To change a status, edit [reference/status.yaml](../reference/status.yaml)
with the reason and its reference, then `snufish export-app --inputs-only`.
