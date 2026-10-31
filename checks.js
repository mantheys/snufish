// Published numbers the page can reproduce with one selection (the same as scripts/crosscheck.py and
// docs/crosschecks.md): each entry sets every step to the paper's inputs and states what the paper found.
// published.kind: "rate" (in published.unit, a key of the page's UNITS), "events" (in the exposure of step 5),
// "ratio" (to the unoscillated rate) or "adn" (in the paper's convention (D - N)/mean, as a fraction).
// arxiv: the paper (linked in the page); figure: the official figure recreated with it (official.js);
// electron: count the electron of a CC event alone (gammas undetected), with this fractional resolution.

import * as engine from "./engine.js";

export const DAYS = 365.25; // = the B5 spec's seconds per year / 86400
export const UNITS = { kt: [1, "per kt·yr"], t: [1e-3, "per t·yr"], kg: [1e-6, "per kg·yr"], g: [1e-9, "per g·yr"],  // x per kt yr
                       ktday: [1 / DAYS, "per kt·day"], cpd100t: [0.1 / DAYS, "per 100 t·day"] };
// Super-K IV, arXiv:2312.12907: resolution eq. 9; threshold table IV; 22.5 kt fiducial (fig. 28); 2970 days live
// (sec. V A 1); energy scale +-0.48 % (table II); resolution +-3 % (sec. IV A 3); other rate systematics +-1.1 % (table IV)
export const SK4_RESOLUTION = [-0.05525, 0.3162, 0.04572];
// the experiments' presets (the page adds its opening example, the thumb)
export const PRESETS = {
  // Borexino Phase-II (arXiv:1707.09279): interaction rates over all recoil energies, in counts per day per 100 t
  borexino: { unit: "cpd100t", detector: "scintillator_pc", channel: "es", site: "LNGS", threshold: 0, "res-model": "quadrature",
              "res-a": 0.05, "res-b": 0, "eff-model": "parametric", eff: 100, "eff-e50": 0, mass: 0.0713, years: +(1291.51 / DAYS).toFixed(4),
              "unc-scale": 0, "unc-res": 0, "unc-norm": 0, components: ["Be7"], quantity: "rate", period: "annual" },
  // JUNO 8B (arXiv:2006.11760): 2 MeV recoil threshold, 3 %/sqrt(E), SNO NC 8B flux, energy scale 0.3 %, efficiency 1 %
  juno: { unit: "ktday", detector: "scintillator_lab", channel: "es", site: "Jiangmen", threshold: 2.0, "res-model": "quadrature",
          "res-a": 0.03, "res-b": 0, "eff-model": "parametric", eff: 100, "eff-e50": 0, mass: "", years: "",
          "unc-scale": 0.3, "unc-res": 0, "unc-norm": 1, components: ["B8", "hep"], b8: "sno_nc", quantity: "rate", period: "annual" },
  // SNO phases I and II (arXiv:1109.0763): 770 t fiducial D2O, T_eff > 3.5 MeV, 277.3 + 391.4 days, energy scale 0.41 %
  sno: { unit: "kt", detector: "heavy_water", channel: "cc_nue_d", site: "SNOLAB", threshold: 3.5, "res-model": "quadrature",
         "res-a": 0, "res-b": 0, "eff-model": "parametric", eff: 100, "eff-e50": 0, mass: 0.770, years: +((277.3 + 391.4) / DAYS).toFixed(4),
         "unc-scale": 0.41, "unc-res": 0, "unc-norm": 0, components: ["B8", "hep"], quantity: "rate", period: "annual" },
  // SNO salt phase (nucl-ex/0502021): the CC rate over the unoscillated one above T_eff = 5.5 MeV, = phi_CC / phi_NC
  sno_salt: { unit: "kt", detector: "heavy_water", channel: "cc_nue_d", site: "SNOLAB", threshold: 5.5, "res-model": "quadrature",
              "res-a": 0, "res-b": 0, "eff-model": "parametric", eff: 100, "eff-e50": 0, mass: 0.770, years: +(391.4 / DAYS).toFixed(4),
              "unc-scale": 0, "unc-res": 0, "unc-norm": 0, components: ["B8", "hep"], b8: "sno_nc", quantity: "ratio", period: "annual" },
  // DUNE far detector, public numbers only: 4 x 10 kt fiducial LAr, 5 MeV detected-energy threshold and ~20 % resolution
  // (supernova-burst paper, arXiv:2008.06647); 100 kt yr as in Capozzi, Li, Zhu & Beacom (arXiv:1808.08232)
  dune: { unit: "kt", detector: "argon", channel: "cc_nue_ar40", site: "SURF", threshold: 5.0, "res-model": "quadrature",
          "res-a": 0, "res-b": 20, "eff-model": "parametric", eff: 100, "eff-e50": 0, mass: 40, years: 2.5,
          "unc-scale": 0, "unc-res": 0, "unc-norm": 0, components: ["B8", "hep"], b8: "sno_nc", quantity: "rate", period: "annual" },
  // Hyper-K design report (arXiv:1805.04163): 187 kt fiducial per tank, 4.5 MeV kinetic threshold, scale 0.5 %, resolution 0.6 %
  hyperk: { unit: "kt", detector: "water", channel: "es", site: "Kamioka", threshold: 4.5, "res-model": "sk4", "eff-model": "parametric",
            eff: 100, "eff-e50": 0, mass: 187, years: 10, "unc-scale": 0.5, "unc-res": 0.6, "unc-norm": 0, components: ["B8", "hep"],
            quantity: "rate", period: "annual" },
  sk4: { unit: "kt", detector: "water", channel: "es", site: "Kamioka", threshold: 3.49, "res-model": "sk4", "eff-model": "curve:sk4_final",
         eff: 100, "eff-e50": 0, components: ["B8", "hep"], b8: "sno_nc", quantity: "rate", period: "annual",
         mass: 22.5, years: +(2970 / 365.25).toFixed(3), "unc-scale": 0.48, "unc-res": 3, "unc-norm": 1.1 },
};

export const NOMINAL_XSEC = ["ar40_marley2_bhattacharya2009", "default"]; // the first available is selected by default
// every field a check may leave untouched, at its default: a check sets the whole page
export const CHECK_BASE = { set: "nufit60_global", solar: "b23_gs98", b8: "model", es: "bks", earth: "prem_full", "res-model": "quadrature",
                            "res-a": 0, "res-b": 0, "eff-model": "parametric", eff: 100, "eff-e50": 0, "eff-width": 0.5, mass: "", years: "",
                            "unc-scale": 0, "unc-res": 0, "unc-norm": 0, quantity: "rate", period: "annual", unit: "kt", orbit: false };

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

const number = (v, fallback = 0) => { const x = parseFloat(v); return Number.isFinite(x) ? x : fallback; };

export function checkSetup(inputs, check) {
  // {setup, quantity, set}: what the calculator computes for a check (applyCheck and readSetup in app.js), without the page
  const { preset, ...values } = check.values, v = { ...CHECK_BASE, ...PRESETS[preset], ...values };
  const models = v.channel === "es" ? [] : inputs.xsecModels(v.channel);
  const xsec = models.includes(v.xsec) ? v.xsec : NOMINAL_XSEC.find((m) => models.includes(m)) || models[0] || "default";
  let efficiency = null;
  if (check.window) efficiency = { id: `window:${check.window[0]}-${check.window[1]}`, x: [check.window[0], check.window[1] - 1e-3, check.window[1]], y: [1, 1, 0] };
  else if (v["eff-model"].startsWith("curve:")) {
    const name = v["eff-model"].slice(6), c = inputs.data.efficiency_curves[name];
    efficiency = { id: v["eff-model"], x: c.x, y: c.y, name: c.label, curve: name };
  }
  const mass = number(v.mass), years = number(v.years);
  const setup = engine.makeSetup({
    solar_model: v.solar, components: v.components, b8_flux: v.b8, site: v.site, earth_model: v.earth, detector: v.detector,
    channel: v.channel, xsec_model: xsec, es_model: v.es, period: v.period, threshold: number(v.threshold),
    resolution_a: number(v["res-a"]), resolution_b: number(v["res-b"]) / 100, resolution_poly: v["res-model"] === "sk4" ? SK4_RESOLUTION : [],
    efficiency: number(v.eff, 100) / 100, efficiency_e50: number(v["eff-e50"]), efficiency_width: number(v["eff-width"], 0.5),
    smearing_table: check.electron ? engine.electronSmearing(inputs, v.channel, xsec, check.electron) : null, efficiency_table: efficiency,
    energy_scale_error: number(v["unc-scale"]) / 100, resolution_error: number(v["unc-res"]) / 100,
    normalisation_error: number(v["unc-norm"]) / 100, exposure: mass > 0 && years > 0 ? mass * years : null, orbit: v.orbit,
  });
  return { setup, quantity: v.quantity, set: v.set };
}

export function reproduced(check, central, exposure) {
  // SNUfish's number in the paper's terms: a rate in published.unit, events in the exposure, A_DN as (D - N)/mean
  const p = check.published;
  return { rate: () => central * UNITS[p.unit][0], events: () => central * exposure, ratio: () => central, adn: () => -central }[p.kind]();
}

const FIELD = { parameter_set: "set", solar_model: "solar", earth_model: "earth", es_model: "es", xsec_model: "xsec" };

export function currentSetup(inputs, check) {
  // the check with every legacy input or approximation (reference/status.yaml) replaced by what supersedes it:
  // {setup, quantity, set, flagged}, flagged as engine.notCurrent's entries with `by`, the replacement or null. A
  // paper's own oscillation parameters (a "reproduction" set) are kept: they are the scenario the number answers
  // (A_DN at a stated Δm²), not an outdated input.
  const paper = checkSetup(inputs, check);
  const flagged = engine.notCurrent(inputs, paper.setup, paper.quantity, paper.set)
    .map((c) => ({ ...c, by: c.status === "reproduction" ? null : c.superseded_by }));
  const values = { ...check.values };
  for (const c of flagged) if (c.by) values[FIELD[c.category]] = c.by;
  return { ...checkSetup(inputs, { ...check, values }), flagged };
}
