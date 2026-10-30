// Published numbers the page can reproduce with one selection (the same as scripts/crosscheck.py and
// docs/crosschecks.md): each entry sets every step to the paper's inputs and states what the paper found.
// published.kind: "rate" (in published.unit, a key of the page's UNITS), "events" (in the exposure of step 5),
// "ratio" (to the unoscillated rate) or "adn" (in the paper's convention (D - N)/mean, as a fraction).
// arxiv: the paper (linked in the page); figure: the official figure recreated with it (official.js);
// electron: count the electron of a CC event alone (gammas undetected), with this fractional resolution.

// the selector's groups: by result, the experiment in each label
export const RESULTS = { rate: "Interaction rates", events: "Interaction rates", ratio: "Rate ÷ no oscillation (flux ratios)",
                         adn: "Day-night asymmetry" };

// oscillation parameters as stated in the papers (errors: NuFIT 6.0's, for the sampled band)
const nufitErrors = { dm2_21_eV2: [1.9e-6, 1.9e-6], sin2_theta12: [0.011, 0.012] };
const paper = (label, s12, s13, dm2, source) => ({
  label, kind: "paper", source,
  sin2_theta12: { value: s12, error: nufitErrors.sin2_theta12 }, dm2_21_eV2: { value: dm2, error: nufitErrors.dm2_21_eV2 },
  sin2_theta13: { value: s13, error: [0.00056, 0.00056] },
});
export const PAPER_SETS = {
  paper_borexino: paper("Borexino 2017 inputs (Δm² 7.50 × 10⁻⁵)", 0.306, 0.02166, 7.50e-5, "as quoted in arXiv:2312.12907 sec. VII D"),
  paper_juno_48: paper("JUNO 2020 ⁸B paper, Δm² 4.8 × 10⁻⁵", 0.307, 0.0212, 4.8e-5, "arXiv:2006.11760 (PDG 2018 mixing)"),
  paper_juno_75: paper("JUNO 2020 ⁸B paper, Δm² 7.5 × 10⁻⁵", 0.307, 0.0212, 7.5e-5, "arXiv:2006.11760 (PDG 2018 mixing)"),
  paper_sk_48: paper("Super-K 2023, Δm² 4.8 × 10⁻⁵", 0.305, 0.0220, 4.8e-5, "arXiv:2312.12907 sec. VIII"),
  paper_sk_61: paper("Super-K 2023 solar best fit, Δm² 6.1 × 10⁻⁵", 0.305, 0.0220, 6.1e-5, "arXiv:2312.12907 sec. VIII"),
  paper_sk_75: paper("Super-K 2023, Δm² 7.5 × 10⁻⁵", 0.305, 0.0220, 7.5e-5, "arXiv:2312.12907 sec. VIII"),
  paper_dune_capozzi: paper("DUNE solar study 2019 (Capozzi et al.), Δm² 4.85 × 10⁻⁵", 0.308, 0.02195, 4.85e-5,
                            "arXiv:1808.08232 (θ13 not stated: NuFIT 6.0's)"),
  paper_dune_isw_50: paper("DUNE day-night study 2017 (Ioannisian et al.), Δm² 5.0 × 10⁻⁵", 0.307, 0.02195, 5.0e-5,
                           "arXiv:1702.06097 (θ12, θ13 not stated: NuFIT 6.0's)"),
  paper_dune_isw_75: paper("DUNE day-night study 2017 (Ioannisian et al.), Δm² 7.5 × 10⁻⁵", 0.307, 0.02195, 7.5e-5,
                           "arXiv:1702.06097 (θ12, θ13 not stated: NuFIT 6.0's)"),
};

const JUNO = { preset: "juno" };
const SK1 = { preset: "sk4", threshold: 4.49, quantity: "adn" };
const SNO_ES = { preset: "sno_salt", channel: "es" };
const DUNE = { preset: "dune", components: ["B8"] }, MARLEY = { xsec: "ar40_marley2_bhattacharya2009" };
const CAPOZZI = { ...DUNE, set: "paper_dune_capozzi", threshold: 5, mass: 40, years: 2.5 }; // 100 kt yr, SNO NC 8B flux
const CAPOZZI_SOURCE = { source: "Capozzi, Li, Zhu & Beacom, arXiv:1808.08232", arxiv: "1808.08232" };

export const CHECKS = [
  { id: "bx_pp", group: "Borexino", label: "pp rate, B16-GS98 prediction",
    values: { preset: "borexino", solar: "b16_gs98", components: ["pp"] },
    published: { kind: "rate", unit: "cpd100t", value: 131.1 }, source: "Borexino arXiv:1707.09279, table II", arxiv: "1707.09279", figure: "bx2" },
  { id: "bx_be7", group: "Borexino", label: "⁷Be rate, B16-GS98 prediction",
    values: { preset: "borexino", solar: "b16_gs98", components: ["Be7"] },
    published: { kind: "rate", unit: "cpd100t", value: 47.9 }, source: "Borexino arXiv:1707.09279, table II", arxiv: "1707.09279", figure: "bx2" },
  { id: "bx_pep", group: "Borexino", label: "pep rate, B16-GS98 prediction",
    values: { preset: "borexino", solar: "b16_gs98", components: ["pep"] },
    published: { kind: "rate", unit: "cpd100t", value: 2.74 }, source: "Borexino arXiv:1707.09279, table II", arxiv: "1707.09279", figure: "bx2" },
  ...[["pp", 0.689, 0.165], ["pep", 0.614, 1.0], ["Be7", 0.638, 0.25]].map(([c, value, t]) => ({
    id: `bx_ratio_${c}`, group: "Borexino", label: `${{ pp: "pp", pep: "pep", Be7: "⁷Be" }[c]} oscillated ÷ unoscillated`,
    values: { preset: "borexino", solar: "b16_gs98", set: "paper_borexino", components: [c], threshold: t, quantity: "ratio" },
    published: { kind: "ratio", value }, source: "Borexino's inputs, as quoted by Super-K arXiv:2312.12907 sec. VII D", arxiv: "2312.12907", figure: "bx2",
    note: `The energy window is not given; T > ${t} MeV here.` })),
  { id: "bx_b8", group: "Borexino", label: "⁸B rate above 3.2 MeV (measured)",
    values: { preset: "borexino", solar: "b16_gs98", set: "paper_borexino", components: ["B8"], threshold: 2.6, "res-a": 0.045,
              "eff-e50": 3.2, "eff-width": 0.12 },
    published: { kind: "rate", unit: "cpd100t", value: 0.223, minus: 0.016, plus: 0.016, measured: true },
    source: "Borexino arXiv:1709.00756", arxiv: "1709.00756", note: "The 3.2 MeV cut as a steep logistic turn-on; B16-GS98 ⁸B flux." },

  ...[["paper_juno_48", 0, 4.15], ["paper_juno_48", 2, 2.76], ["paper_juno_75", 0, 4.36], ["paper_juno_75", 2, 2.90]].map(([set, t, value]) => ({
    id: `juno_${set.slice(-2)}_${t}`, group: "JUNO", label: `⁸B rate, Δm² ${set.endsWith("48") ? "4.8" : "7.5"} × 10⁻⁵, ${t ? `T > ${t} MeV` : "all energies"}`,
    values: { ...JUNO, set, threshold: t }, published: { kind: "rate", unit: "ktday", value },
    source: "JUNO arXiv:2006.11760, table 1 (day + night)", arxiv: "2006.11760", figure: "juno3",
    note: "JUNO's tree-level cross section with sin²θ_W = 0.23; within 0.6 % of the radiatively corrected one (the default)." })),
  ...[[2, 16, -0.029], [5, 16, -0.034], [3, 5, -0.025], [2, 3, -0.021]].map(([lo, hi, value]) => ({
    id: `juno_adn_${lo}_${hi}`, group: "JUNO", label: `A_DN, ${lo}–${hi} MeV, Δm² 4.8 × 10⁻⁵`,
    values: { ...JUNO, set: "paper_juno_48", threshold: lo, quantity: "adn" }, window: [lo, hi],
    published: { kind: "adn", value }, source: "JUNO arXiv:2006.11760, table 7", arxiv: "2006.11760", figure: "juno7" })),
  { id: "juno_adn_75", group: "JUNO", label: "A_DN, 2–16 MeV, Δm² 7.5 × 10⁻⁵ (not reproduced)",
    values: { ...JUNO, set: "paper_juno_75", threshold: 2, quantity: "adn" }, window: [2, 16],
    published: { kind: "adn", value: -0.016 }, source: "JUNO arXiv:2006.11760, sec. 4.2", arxiv: "2006.11760", figure: "juno7",
    note: "JUNO's own table 1 at this Δm² (1.44 by day, 1.46 by night) gives −1.4 % ± 0.7 % from its rounding, as SNUfish does; the −1.6 % of the text does not follow from it." },

  { id: "sk_events", group: "Super-K IV", label: "⁸B + hep events in 2970 days (measured)",
    values: { preset: "sk4", set: "paper_sk_61" },
    published: { kind: "events", value: 65443, minus: Math.hypot(388, 925), plus: Math.hypot(390, 925), measured: true },
    source: "Super-K arXiv:2312.12907, sec. V", arxiv: "2312.12907", note: "With the SNO NC ⁸B flux (±3.8 %, sampled)." },
  { id: "sk_flux", group: "Super-K IV", label: "⁸B flux ÷ SNO NC flux (measured)",
    values: { preset: "sk4", set: "paper_sk_61", quantity: "ratio" },
    published: { kind: "ratio", value: 2.314 / 5.25, minus: 0.009, plus: 0.009, measured: true },
    source: "Super-K arXiv:2312.12907 (2.314 × 10⁶) over SNO NC (5.25 × 10⁶)", arxiv: "2312.12907", note: "Super-K's error only; the SNO NC flux adds ±3.8 %." },
  { id: "sk_adn4", group: "Super-K IV", label: "Expected A_DN, SK-IV, Δm² 6.1 × 10⁻⁵",
    values: { preset: "sk4", set: "paper_sk_61", quantity: "adn" },
    published: { kind: "adn", value: -0.0238 }, source: "Super-K arXiv:2312.12907, sec. VIII", arxiv: "2312.12907", figure: "sk49",
    note: "Super-K's amplitude fit weights the zenith-angle shape by energy bin; this is the plain rate asymmetry (~2.5 % smaller)." },
  ...[["paper_sk_61", -0.0242], ["paper_sk_75", -0.0172], ["paper_sk_48", -0.0384]].map(([set, value]) => ({
    id: `sk1_${set.slice(-2)}`, group: "Super-K IV",
    label: `Expected A_DN, SK-I range (T > 4.49 MeV), Δm² ${{ 48: "4.8", 61: "6.1", 75: "7.5" }[set.slice(-2)]} × 10⁻⁵${set.endsWith("48") ? " (not reproduced)" : ""}`,
    values: { ...SK1, set }, published: { kind: "adn", value }, source: "Super-K arXiv:2312.12907, sec. VIII", arxiv: "2312.12907", figure: "sk52",
    note: set.endsWith("48")
      ? "13.5 % off, while 6.1 and 7.5 × 10⁻⁵ agree to 2.5 %; the exact solvers give the same, θ13 = 0 only −3.48 %. Quoted \"for reference\" at the previously favoured Δm²: perhaps an older calculation."
      : "With Super-K IV's response above 4.49 MeV." })),

  { id: "sno_cc_nc", group: "SNO", label: "φ_CC / φ_NC, salt phase (measured)", values: { preset: "sno_salt" },
    published: { kind: "ratio", value: 0.340, minus: 0.039, plus: 0.037, measured: true }, source: "SNO nucl-ex/0502021", arxiv: "nucl-ex/0502021", figure: "sno10" },
  { id: "sno_es_nc", group: "SNO", label: "φ_ES / φ_NC, salt phase (measured)", values: SNO_ES,
    published: { kind: "ratio", value: 2.35 / 4.94, minus: 0.06, plus: 0.06, measured: true }, source: "SNO nucl-ex/0502021 (2.35 / 4.94)", arxiv: "nucl-ex/0502021", figure: "sno10" },

  { id: "dune_cc", group: "DUNE", label: "⁸B νe CC events, electron T > 5 MeV, 100 kt·yr (Capozzi et al. 2019)",
    values: { ...CAPOZZI, ...MARLEY }, electron: 0.07, published: { kind: "events", value: 9.9e4 / 0.88 }, ...CAPOZZI_SOURCE,
    note: "The electron alone (gammas undetected), 7 % resolution. The paper counts 9.9 × 10⁴ events outside a 40° cone that holds 88 % of them (both rounded): 1.125 × 10⁵ in all." },
  { id: "dune_es", group: "DUNE", label: "⁸B ES events, T > 5 MeV, 100 kt·yr (Capozzi et al. 2019)",
    values: { ...CAPOZZI, channel: "es", "res-b": 7 }, published: { kind: "events", value: 2.6e4 / 0.81 }, ...CAPOZZI_SOURCE,
    note: "The paper counts 2.6 × 10⁴ events inside a 40° cone that holds 81 % of them (both rounded): 3.2 × 10⁴ in all." },
  { id: "dune_hep", group: "DUNE", label: "hep νe CC events, electron T > 11 MeV, 100 kt·yr (Capozzi et al. 2019)",
    values: { ...CAPOZZI, ...MARLEY, components: ["hep"], threshold: 11 }, electron: 0.07, published: { kind: "events", value: 150 },
    ...CAPOZZI_SOURCE, note: "The paper's hep flux is 8.25 × 10³ cm⁻² s⁻¹, B23-GS98's here 7.95 × 10³ (3.8 % fewer events)." },
  { id: "dune_adn", group: "DUNE", label: "A_DN, νe CC, electron T > 6 MeV, Δm² 4.85 × 10⁻⁵ (Capozzi et al. 2019; not reproduced)",
    values: { ...CAPOZZI, ...MARLEY, threshold: 6, quantity: "adn" }, electron: 0.07, published: { kind: "adn", value: (3.04 - 3.29) / 3.165 },
    ...CAPOZZI_SOURCE, note: "From the paper's D = 3.04 × 10⁴ and N = 3.29 × 10⁴ signal events. At DUNE's energies the asymmetry follows the Earth's outer layers: −6.9 % with the ten-region PREM, −8.7 % with the four-region one (no crust); the paper does not describe its Earth model beyond citing its method (ref. 49)." },
  { id: "dune_hnb", group: "DUNE", label: "⁸B νe CC events, electron T > 5 MeV, 20 kt·yr (Hajjar et al. 2026)",
    values: { ...DUNE, ...MARLEY, threshold: 5, mass: 20, years: 1 }, electron: 0.07, published: { kind: "events", value: 21722 },
    source: "Hajjar, Nairat & Beacom, arXiv:2606.18347, table I", arxiv: "2606.18347",
    note: "NuFIT 6.0 and the SNO NC ⁸B flux (the paper takes the flux from SNO); the electron alone with 7 % resolution, over the (p,n) strengths MARLEY 2 also uses." },
  { id: "dune_isw", group: "DUNE", label: "⁸B νe CC events with Eν > 11 MeV, 40 kt in a year (Ioannisian et al. 2017)",
    values: { ...DUNE, set: "paper_dune_isw_75", threshold: 11 - 1.504, "res-b": 0, mass: 40, years: 1 },
    published: { kind: "events", value: 27000 }, source: "Ioannisian, Smirnov & Wyler, arXiv:1702.06097, sec. IV", arxiv: "1702.06097",
    note: "Eν > 11 MeV as visible energy above 11 − 1.504 MeV, unsmeared. The paper's cross section is an approximation (σ ∝ p_e E_e above 5.8 MeV) and its oscillation parameters are not stated." },
  ...[["paper_dune_isw_75", "7.5", 0.04], ["paper_dune_isw_50", "5.0", 0.065]].map(([set, dm2, excess]) => ({
    id: `dune_isw_adn_${dm2[0]}`, group: "DUNE", label: `A_DN, Eν > 11 MeV, Δm² ${dm2} × 10⁻⁵ (Ioannisian et al. 2017)`,
    values: { ...DUNE, set, threshold: 11 - 1.504, "res-b": 0, quantity: "adn" }, published: { kind: "adn", value: -excess / (1 + excess / 2) },
    source: "Ioannisian, Smirnov & Wyler, arXiv:1702.06097, sec. IV", arxiv: "1702.06097",
    note: `The paper's "about ${100 * excess} %" night excess N/D − 1, here as (D − N)/mean.` })),
];
