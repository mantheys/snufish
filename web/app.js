// SNUfish page: controls, computation (engine.js on the tables in data/) and display.
import * as engine from "./engine.js";
import { budgetPlot, distributionPlot, spectrumPlot } from "./plots.js";
import { forStep, render as renderSources } from "./sources.js";
import { CHECKS, PAPER_SETS } from "./checks.js";

const DATA = "data/";
const N_DRAWS = 400, SEED = 1;
const CHANNELS = { es: "Elastic scattering on electrons", cc_nue_ar40: "νe CC on ⁴⁰Ar", cc_nue_o16: "νe CC on ¹⁶O",
                   cc_nue_d: "νe CC on deuterium", nc_d: "NC on deuterium (all flavours)" };
const DETECTORS = { argon: "Liquid argon", water: "Water", scintillator_pc: "Liquid scintillator: pseudocumene (Borexino)",
                    scintillator_lab: "Liquid scintillator: LAB (JUNO)", heavy_water: "Heavy water, D₂O (SNO)" };
const XSEC = {
  ar40_marley2_bhattacharya2009: "MARLEY 2 (recommended): HF-CRPA + B(GT) from (p,n), 2009",
  ar40_marley2_liu1998: "MARLEY 2: HF-CRPA + B(GT) from ⁴⁰Ti decay (Liu 1998)",
  ar40_marley2_bhattacharya1998: "MARLEY 2: HF-CRPA + B(GT) from ⁴⁰Ti decay (Bhattacharya 1998)",
  ar40_marley1_bhattacharya2009: "MARLEY v1 model, B(GT) from (p,n) (run by MARLEY 2)",
  default: "SNOwGLoBES default", ar40_klmv: "SNOwGLoBES: KLMV",
  ar40_marley: "SNOwGLoBES: MARLEY, B(GT) from (p,n) (zero below 5 MeV)",
  ar40_marley1: "SNOwGLoBES: MARLEY, B(GT) from ⁴⁰Ti decay (zero below 5 MeV)",
};
const NOMINAL_XSEC = ["ar40_marley2_bhattacharya2009", "default"]; // the first available is selected by default
const EARTH = { prem_full: "PREM, ten regions", prem_four: "PREM, four regions", prem_prob3: "Four shells (Prob3++)" };
const KINDS = { reactor: "Reactor", solar: "Solar", global: "Global fits", paper: "As used in a paper" };
const ORDER = ["pp", "pep", "hep", "Be7", "B8", "N13", "O15", "F17"];
const DAYS = 365.25; // = the B5 spec's seconds per year / 86400
const UNITS = { kt: [1, "per kt·yr"], t: [1e-3, "per t·yr"], kg: [1e-6, "per kg·yr"], g: [1e-9, "per g·yr"],  // x per kt yr
                ktday: [1 / DAYS, "per kt·day"], cpd100t: [0.1 / DAYS, "per 100 t·day"] };
const THUMB_GRAMS = 20; // a thumb, as water: an order of magnitude
// Super-K IV, arXiv:2312.12907: resolution eq. 9; threshold table IV; 22.5 kt fiducial (fig. 28); 2970 days live
// (sec. V A 1); energy scale +-0.48 % (table II); resolution +-3 % (sec. IV A 3); other rate systematics +-1.1 % (table IV)
const SK4_RESOLUTION = [-0.05525, 0.3162, 0.04572];
const PRESETS = {
  // the opening example: a thumb held up to the Sun, every solar neutrino, ES on its electrons, a perfect detector
  thumb: { detector: "water", channel: "es", site: "Kamioka", threshold: 0, "res-model": "quadrature", "res-a": 0, "res-b": 0,
           "eff-model": "parametric", eff: 100, "eff-e50": 0, mass: "", years: "", "unc-scale": 0, "unc-res": 0, "unc-norm": 0,
           components: ORDER, quantity: "rate", period: "annual", unit: "g" },
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
const PRESET_NOTES = {
  thumb: `A thumb, as ${THUMB_GRAMS} g of water: every solar flux component, elastic scattering on its electrons, `
       + "no threshold and a perfect detector, averaged over day and night. Change any setting to start from it.",
  custom: "",
  borexino: "Borexino Phase-II as published (arXiv:1707.09279): pseudocumene with 3.307 × 10³¹ electrons per 100 t, its "
          + "71.3 t fiducial mass over 1291.51 days, ~50 keV resolution at 1 MeV, and rates over all recoil energies. Choose pp, ⁷Be "
          + "or pep alone to compare with its measurement. With the BKS radiative corrections and B16-GS98 the rates come out "
          + "within 0.6 % of Borexino's own predictions for all three (tree level: 3.5 % above).",
  juno: "JUNO ⁸B study (arXiv:2006.11760): LAB with 3.38 × 10³² electrons per kt, a 2 MeV recoil threshold, 3 %/√E resolution, "
      + "the SNO NC ⁸B flux, energy scale ±0.3 % and efficiency ±1 %. Not included: its energy-dependent fiducial volume, the 48 % "
      + "muon-veto dead time and the scintillator non-linearity. All energies, this reproduces its 4.36 counts per day per kt to 2 %.",
  sno: "SNO phases I and II (arXiv:1109.0763): νe CC on deuterium in 770 t of fiducial D₂O (r < 550 cm), T_eff > 3.5 MeV, "
     + "277.3 + 391.4 days live, energy scale ±0.41 %. Not included: SNO's resolution function (the paper gives only extra "
     + "smearing terms) and its efficiencies. The CC cross section is Nakamura et al. 2002 down to its 1.44 MeV threshold. "
     + "Switch the channel to NC on deuterium for the neutral-current rate (set its neutron efficiency).",
  sno_salt: "SNO salt phase (nucl-ex/0502021): the CC rate on deuterium above T_eff = 5.5 MeV over the rate without oscillations, "
          + "which is SNO's φ_CC/φ_NC (both fluxes inferred for an undistorted ⁸B spectrum). The total flux and the detector "
          + "normalisation cancel; statistics are for 770 t and 391.4 live days without backgrounds or efficiencies. No "
          + "resolution is applied (T_eff is smeared by ~ 0.4 √E in SNO), which moves the ratio by under 0.1 %.",
  dune: "DUNE far detector from published numbers only: four 10 kt fiducial liquid-argon modules at SURF, νe CC on ⁴⁰Ar "
      + "(MARLEY 2), a 5 MeV detected-energy threshold and a 20 % energy-independent resolution (DUNE's supernova-burst paper, "
      + "arXiv:2008.06647: \"realistic energy resolution is closest to the 20 % level\"), and 100 kt·yr as in Capozzi et al. "
      + "(arXiv:1808.08232), who assume 7 % (set b = 7). Visible energy here is Eν − 1.504 MeV (gammas included); Capozzi et al. "
      + "count the electron alone. No efficiency, backgrounds or detector uncertainties: none is published for solar neutrinos.",
  hyperk: "Hyper-K, one tank (design report, arXiv:1805.04163): 187 kt fiducial, 4.5 MeV kinetic threshold, energy scale ±0.5 % "
        + "and resolution ±0.6 %, 10 years. Its resolution is not published as a function and is expected to be better than "
        + "Super-K's: Super-K IV's is used as a conservative stand-in. Kamioka's latitude is used (Tochibora is 0.12° south). "
        + "Efficiencies are not included: the report's 130 events a day above 4.5 MeV include them.",
  sk4: "Super-K IV as published (arXiv:2312.12907): resolution, threshold, fiducial mass, live time and detector uncertainties. "
     + "Its selection efficiency (fig. 28, final sample) is read from the figure's vector PostScript in the arXiv source. "
     + "With it the energy-scale effect on the rate is ±0.76 % (Super-K: ±0.8 %, table IV; ±0.48 % without it) and the ⁸B + hep events in "
     + "2970 days come out within 1.5 % of the 65,443 Super-K extracted, with the SNO NC flux.",
};

const $ = (id) => document.getElementById(id);
// In a hosted view (a claude.ai artifact) the page cannot start downloads, load Python from a CDN, or keep the
// setup in the address: those controls are hidden there and the files below say how to run the site locally.
const HOSTED = document.querySelector('meta[name="snufish-host"]')?.content === "artifact";
const app = { inputs: null, tables: null, result: null, timer: null, running: false, again: false,
              worker: null, rendered: [], renderId: 0, imports: { smearing: null, efficiency: null } };

// ------------------------------------------------------------------ loading

async function loadTable(name) {
  const meta = await (await fetch(`${DATA}${name}.json`)).json();
  const response = await fetch(`${DATA}${meta.bin}`);
  if (!response.ok) throw new Error(`could not load ${meta.bin} (${response.status})`);
  if (meta.encoding === "base64") { // hosted copies keep the float32 tables as base64 text
    const text = atob((await response.text()).trim()), bytes = new Uint8Array(text.length);
    for (let i = 0; i < text.length; i++) bytes[i] = text.charCodeAt(i);
    return { meta, buffer: bytes.buffer };
  }
  return { meta, buffer: await response.arrayBuffer() };
}

function option(value, label, selected = false) {
  const o = document.createElement("option");
  o.value = value; o.textContent = label; o.selected = selected;
  return o;
}

function fillSelect(select, entries, value) {
  select.replaceChildren(...entries.map(([v, l]) => option(v, l, v === value)));
  if (!entries.some(([v]) => v === value) && entries.length) select.value = entries[0][0];
}

function buildControls() {
  const d = app.inputs.data;
  Object.assign(d.parameter_sets.sets, PAPER_SETS); // the papers' own values, for the published checks
  const groups = {};
  for (const c of CHECKS) (groups[c.group] ||= []).push(c);
  $("check").replaceChildren(option("", "None: set the steps by hand", true), ...Object.entries(groups).map(([name, list]) => {
    const group = document.createElement("optgroup");
    group.label = name;
    list.forEach((c) => group.append(option(c.id, c.label)));
    return group;
  }));
  const set = $("set");
  for (const [kind, label] of Object.entries(KINDS)) {
    const group = document.createElement("optgroup");
    group.label = label;
    for (const [name, info] of Object.entries(d.parameter_sets.sets)) if (info.kind === kind) group.append(option(name, info.label));
    if (group.children.length) set.append(group);
  }
  set.value = "juno_2025";
  const solar = $("solar"), families = {};
  for (const [name, info] of Object.entries(d.solar_models)) (families[info.label.split(" ")[0]] ||= []).push([name, info.label]);
  for (const [family, models] of Object.entries(families)) {
    const group = document.createElement("optgroup");
    group.label = family;
    models.forEach(([name, label]) => group.append(option(name, label)));
    solar.append(group);
  }
  solar.value = "b23_gs98";
  $("components").replaceChildren(...ORDER.map((c, i) => {
    const label = document.createElement("label");
    label.style.setProperty("--dot", `var(--series-${i + 1})`);
    label.innerHTML = `<input type="checkbox" name="components" value="${c}" ${c === "B8" ? "checked" : ""}><span>${engine.DISPLAY[c]}</span>`;
    return label;
  }));
  fillSelect($("site"), Object.entries(d.sites).map(([s, info]) => [s, `${s} (${info.latitude_deg.toFixed(1)}° N)`]), "Kamioka");
  fillSelect($("earth"), d.earth_models.map((e) => [e, EARTH[e] || e]), "prem_full");
  fillSelect($("detector"), Object.keys(d.detectors).map((k) => [k, DETECTORS[k] || k]), "water");
}

// ------------------------------------------------------------------ controls

const radio = (name) => document.querySelector(`input[name="${name}"]:checked`).value;
const setRadio = (name, value) => { const el = document.querySelector(`input[name="${name}"][value="${value}"]`); if (el) el.checked = true; };

const number = (id, fallback = 0) => { const v = parseFloat($(id).value); return Number.isFinite(v) ? v : fallback; };

function exposure() {
  const mass = number("mass"), years = number("years");
  return mass > 0 && years > 0 ? mass * years : null;
}

function readSetup() {
  return engine.makeSetup({
    solar_model: $("solar").value,
    components: [...document.querySelectorAll('input[name="components"]:checked')].map((x) => x.value),
    b8_flux: radio("b8"), site: $("site").value, earth_model: $("earth").value, detector: $("detector").value,
    channel: $("channel").value, xsec_model: $("xsec").value || "default", es_model: radio("es"),
    period: radio("period"), threshold: number("threshold"), resolution_a: number("res-a"),
    resolution_b: number("res-b") / 100, resolution_poly: $("res-model").value === "sk4" ? SK4_RESOLUTION : [],
    efficiency: number("eff", 100) / 100, efficiency_e50: number("eff-e50"), efficiency_width: number("eff-width", 0.5),
    smearing_table: $("res-model").value === "import" ? app.imports.smearing : null,
    efficiency_table: efficiencyTable(),
    energy_scale_error: number("unc-scale") / 100, resolution_error: number("unc-res") / 100,
    normalisation_error: number("unc-norm") / 100, exposure: exposure(),
  });
}

function efficiencyTable() {
  // the imported curve, or a published one ("curve:<name>" of inputs.efficiency_curves), or none
  const v = $("eff-model").value;
  if (v === "import") return app.imports.efficiency;
  if (!v.startsWith("curve:")) return null;
  const name = v.slice(6), c = app.inputs.data.efficiency_curves[name];
  return { id: v, x: c.x, y: c.y, name: c.label, curve: name };
}

function sync() {
  // offer only what applies: channels of the target, threshold for ES, nuclear models for CC, the Earth only at night
  const d = app.inputs.data, detector = $("detector").value;
  const channels = Object.keys(d.detectors[detector].channels);
  fillSelect($("channel"), channels.map((c) => [c, CHANNELS[c] || c]), $("channel").value);
  const es = $("channel").value === "es";
  $("es-row").hidden = !es;
  $("res-ab").hidden = $("res-model").value !== "quadrature";
  $("smear-import").hidden = $("res-model").value !== "import";
  const effImport = $("eff-model").value === "import", effCurve = $("eff-model").value.startsWith("curve:");
  $("eff-import").hidden = !effImport;
  $("eff-parametric").hidden = $("eff-parametric-hint").hidden = effImport || effCurve;
  if (app.imports.smearing) app.imports.smearing.true_axis = $("smear-neutrino").checked ? "neutrino" : "observed";
  $("preset-note").textContent = PRESET_NOTES[$("preset").value];
  $("threshold-label").textContent = es ? "Threshold on the electron kinetic energy T (MeV)" : "Threshold on the visible energy (MeV)";
  const q = d.visible_offset_MeV[$("channel").value];
  $("observable-note").textContent = es
    ? "Observed: the recoil electron's kinetic energy T."
    : `Observed: the visible energy E_ν − Q (Q = ${q} MeV; electron and de-excitation gammas, no neutron or binding losses).`;
  const exp = exposure();
  $("exposure-note").textContent = exp ? `Exposure ${fmt(exp)} kt·yr (half by night).` : "Set both for a statistical error.";
  const models = es ? [] : app.inputs.xsecModels($("channel").value);
  const keep = models.includes($("xsec").value) ? $("xsec").value : NOMINAL_XSEC.find((m) => models.includes(m)) || models[0];
  const ordered = [...Object.keys(XSEC).filter((m) => models.includes(m)), ...models.filter((m) => !(m in XSEC))];
  fillSelect($("xsec"), ordered.map((m) => [m, XSEC[m] || m]), keep);
  $("xsec-row").hidden = models.length < 2;
  const comps = [...document.querySelectorAll('input[name="components"]:checked')].map((x) => x.value);
  $("b8-row").hidden = !comps.includes("B8");
  $("period-row").hidden = radio("quantity") === "adn";
  $("unit-row").hidden = radio("quantity") !== "rate";
  const night = engine.needsNight(radio("quantity"), radio("period"));
  $("site").disabled = $("earth").disabled = !night;
  $("earth-note").textContent = night
    ? "Neutrinos cross the Earth at night; the site's latitude sets the path lengths through it."
    : "Not used: daytime neutrinos do not cross the Earth. Choose a night or annual rate, or the day-night asymmetry.";
  const p = d.parameter_sets.sets[$("set").value], dm = p.dm2_21_eV2, s = p.sin2_theta12;
  $("set-info").innerHTML = `Δm²₂₁ = ${(dm.value * 1e5).toFixed(2)} <span title="1σ">(−${(dm.error[0] * 1e5).toFixed(2)} +${(dm.error[1] * 1e5).toFixed(2)})</span> × 10⁻⁵ eV²<br>
    sin²θ₁₂ = ${s.value.toFixed(4)} (−${s.error[0].toFixed(4)} +${s.error[1].toFixed(4)})<br>
    ${p.sin2_theta13 ? `sin²θ₁₃ = ${p.sin2_theta13.value}; θ₂₃, δ, Δm²₃₁` : "θ₁₃, θ₂₃, δ, Δm²₃₁"}: NuFIT 6.0 · ${p.source}`;
  const check = CHECKS.find((c) => c.id === $("check").value);
  $("check-note").textContent = check ? `${check.source}.${check.note ? ` ${check.note}` : ""} Change any setting to leave the check.`
    : "Sets every step to a paper's inputs and shows its number next to SNUfish's.";
}

// ------------------------------------------------------------------ URL state

const KEYS = { set: "set", solar: "solar", site: "site", earth: "earth", detector: "target", channel: "channel",
               xsec: "xsec", preset: "preset", threshold: "threshold", "res-model": "resolution", "res-a": "a", "res-b": "b",
               eff: "eff", "eff-e50": "e50", "eff-width": "width", mass: "mass", years: "years", "unc-scale": "dscale",
               "unc-res": "dres", "unc-norm": "dnorm", "eff-model": "efficiency", unit: "unit", check: "check" };
const RADIOS = { b8: "b8", es: "es", quantity: "q", period: "period" };

function saveHash() {
  if (HOSTED) return;
  const p = new URLSearchParams();
  for (const [id, key] of Object.entries(KEYS)) if ($(id).value) p.set(key, $(id).value);
  for (const [name, key] of Object.entries(RADIOS)) p.set(key, radio(name));
  p.set("components", readSetup().components.join(","));
  history.replaceState(null, "", `#${p}`);
}

function loadHash() {
  if (HOSTED) return;
  const p = new URLSearchParams(location.hash.slice(1));
  if (!p.size) return;
  if (p.has("target")) { $("detector").value = p.get("target"); sync(); }
  if (p.has("channel")) { $("channel").value = p.get("channel"); sync(); }
  for (const [id, key] of Object.entries(KEYS)) if (p.has(key) && id !== "detector" && id !== "channel") $(id).value = p.get(key);
  for (const [name, key] of Object.entries(RADIOS)) if (p.has(key)) setRadio(name, p.get(key));
  if (p.has("components")) {
    const chosen = p.get("components").split(",");
    document.querySelectorAll('input[name="components"]').forEach((x) => { x.checked = chosen.includes(x.value); });
  }
  if (p.get("check")) applyCheck(p.get("check")); // a published check sets everything (and its energy window)
}

// ------------------------------------------------------------------ computing

function status(text, error = false) {
  $("status").textContent = text;
  $("status").classList.toggle("error", error);
}

const SUPERSCRIPT = { "-": "⁻", 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹" };
const power = (e) => `10${String(e).split("").map((ch) => SUPERSCRIPT[ch]).join("")}`;
const grouped = (v, decimals) => v.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

function fmt(value, error) {
  // a value alone to 3-4 significant figures; with an error, both to the error's two significant figures;
  // from 1e5 on and below 1e-2, in scientific notation with a common power of ten
  const big = Math.abs(value) >= 1e5 || (value !== 0 && Math.abs(value) < 1e-2);
  const e = big ? Math.floor(Math.log10(Math.abs(value))) : 0, k = 10 ** e;
  if (!(error > 0) || !Number.isFinite(error)) {
    if (big) return `${(value / k).toFixed(2)} × ${power(e)}`;
    return value.toLocaleString("en-US", { maximumSignificantDigits: Math.abs(value) >= 1000 ? 4 : 3 });
  }
  const decimals = Math.max(0, 1 - Math.floor(Math.log10(error / k)));
  if (big) return `(${(value / k).toFixed(decimals)} ± ${(error / k).toFixed(decimals)}) × ${power(e)}`;
  return `${grouped(value, decimals)} ± ${grouped(error, decimals)}`;
}

const signed = (v) => (v === 0 ? "±0" : `${v > 0 ? "+" : "−"}${Math.abs(v) < 0.1 ? Math.abs(v).toPrecision(2) : Math.abs(v).toFixed(1)}`);

function measuredBand(setup, quantity) {
  // a published measurement of what is computed, in the engine's units (per kt yr, or a fraction), or null
  const meas = app.inputs.data.measurements;
  if (quantity === "adn" && setup.channel === "es" && setup.site === "Kamioka" && Math.abs(setup.threshold - 3.49) < 0.01) {
    const m = meas.sk_day_night, e = Math.hypot(m.stat, m.syst);
    return { value: -m.value, minus: e, plus: e, label: "Super-K ±1σ", source: "Super-K, arXiv:2312.12907" };
  }
  const borexino = meas.borexino_rates?.measured, c = setup.components;
  if (quantity === "rate" && borexino && setup.detector === "scintillator_pc" && setup.channel === "es" && setup.threshold === 0
      && c.length === 1 && borexino[c[0]]) {
    const m = borexino[c[0]], k = UNITS.cpd100t[0]; // cpd/100 t -> per kt yr
    return { value: m.value / k, minus: Math.hypot(m.stat, m.sys[0]) / k, plus: Math.hypot(m.stat, m.sys[1]) / k,
             label: "Borexino ±1σ", source: "Borexino Phase-II, arXiv:1707.09279" };
  }
  const sk = meas.sk4_events;
  if (quantity === "rate" && sk && setup.detector === "water" && setup.channel === "es" && setup.period === "annual"
      && Math.abs(setup.threshold - sk.threshold_MeV) < 0.01 && setup.efficiency_table?.curve === "sk4_final"
      && c.includes("B8") && c.every((x) => x === "B8" || x === "hep")) {
    const exposure = sk.fiducial_kt * sk.days / DAYS; // kt yr
    return { value: sk.events / exposure, minus: Math.hypot(sk.stat[0], sk.syst) / exposure, plus: Math.hypot(sk.stat[1], sk.syst) / exposure,
             label: "Super-K IV ±1σ", source: `Super-K IV, ${sk.events.toLocaleString("en-US")} events in 2970 days, arXiv:2312.12907` };
  }
  const sno = meas.sno_cc_nc;
  if (quantity === "ratio" && sno && setup.channel === "cc_nue_d" && c.includes("B8") && Math.abs(setup.threshold - sno.threshold_MeV) < 0.01) {
    return { value: sno.value, minus: Math.hypot(sno.stat, sno.syst[0]), plus: Math.hypot(sno.stat, sno.syst[1]),
             label: "SNO salt ±1σ", source: `SNO salt phase φ_CC/φ_NC, ${sno.source}` };
  }
  return null;
}

function measuredLine(r) {
  const m = measuredBand(r.setup, r.quantity);
  if (!m || r.check?.published.measured) return "";
  const central = r.rows[0].Central, pull = (central - m.value) / (central > m.value ? m.minus : m.plus);
  const [v, lo, hi] = [m.value, m.minus, m.plus].map((x) => x * r.scale);
  const decimals = Math.max(0, 1 - Math.floor(Math.log10(Math.min(lo, hi)))); // both errors to two significant figures
  const shown = Math.abs(v) >= 1e5 || Math.abs(v) < 1e-2 ? `${fmt(v)} −${fmt(lo)} +${fmt(hi)}` : `${v.toFixed(decimals)} −${lo.toFixed(decimals)} +${hi.toFixed(decimals)}`;
  return `<div class="sub thumb-line">Measured (${m.source}): ${shown} ${r.unit};
    the prediction is ${Math.abs(pull).toFixed(1)}σ ${pull > 0 ? "above" : "below"} it (measurement error only).</div>`;
}

function checkBand(r) {
  // the selected check's measurement, in the engine's units (per kt yr, or a fraction), for the histogram
  const p = r.check?.published;
  if (!p?.measured) return null;
  const k = { rate: () => 1 / UNITS[p.unit][0], events: () => 1 / r.setup.exposure, ratio: () => 1 }[p.kind]();
  return { value: p.value * k, minus: p.minus * k, plus: p.plus * k, label: `${r.check.group} ±1σ` };
}

function publishedLine(r) {
  // the selected published check: the paper's number next to this one (a measurement with its pull)
  const c = r.check;
  if (!c) return "";
  const p = c.published, central = r.rows[0].Central;
  let ours, shown, unit = "";
  if (p.kind === "rate") { ours = central * UNITS[p.unit][0]; unit = ` ${UNITS[p.unit][1]}`; }
  else if (p.kind === "events") { ours = central * r.setup.exposure; unit = " events"; }
  else if (p.kind === "ratio") ours = central;
  else ours = -central; // A_DN in the papers' (D - N)/mean
  const minus = (text) => text.replace("-", "−");
  const digits = (v, n = 4) => (p.kind === "events" ? Math.round(v).toLocaleString("en-US")
    : p.kind === "adn" ? minus(`${(100 * v).toFixed(2)} %`) : minus(Number(v.toPrecision(n)).toString()));
  const diff = p.kind === "adn" ? `${signed(100 * (ours - p.value))} points, ${signed(100 * (ours / p.value - 1))} %` : `${signed(100 * (ours / p.value - 1))} %`;
  if (p.measured) {
    const pull = (ours - p.value) / (ours > p.value ? p.plus : p.minus);
    shown = `Measured: <b>${digits(p.value)}</b> −${digits(p.minus, 2)} +${digits(p.plus, 2)}${unit} · SNUfish <b>${digits(ours)}</b>${unit} (${diff}), `
          + `${Math.abs(pull).toFixed(1)}σ ${pull > 0 ? "above" : "below"} it`;
  } else shown = `Published: <b>${digits(p.value)}</b>${unit} · SNUfish <b>${digits(ours)}</b>${unit} (${diff})`;
  const convention = p.kind === "adn" ? " A_DN here in the paper's convention (D − N)/mean, the opposite sign of the headline's." : "";
  return `<div class="sub check-line"><b>${c.group}: ${c.label}</b> (${c.source}). ${shown}.${convention}</div>`;
}

function describe(setup, quantity) {
  const comps = setup.components.map((c) => engine.DISPLAY[c]).join(", ");
  const response = [];
  if (setup.threshold > 0) response.push(`${setup.channel === "es" ? "T" : "E_vis"} > ${setup.threshold} MeV`);
  if (setup.resolution_a > 0 || setup.resolution_b > 0 || setup.resolution_poly.length || setup.smearing_table) response.push("smeared");
  if (setup.efficiency < 1 || setup.efficiency_e50 > 0 || setup.efficiency_table) response.push("efficiency");
  const what = CHANNELS[setup.channel] + (response.length ? `, ${response.join(", ")}` : "");
  if (quantity === "ratio") return `${setup.period[0].toUpperCase()}${setup.period.slice(1)} rate ÷ rate without oscillations · ${comps} · ${what}`;
  return quantity === "adn" ? `Day-night asymmetry 2(N−D)/(N+D) · ${comps} · ${what} · ${setup.site}`
                            : `${setup.period[0].toUpperCase()}${setup.period.slice(1)} rate · ${comps} · ${what}`;
}

function schedule() {
  clearTimeout(app.timer);
  app.timer = setTimeout(run, 120);
}

async function run() {
  if (app.running) { app.again = true; return; }
  app.running = true;
  try {
    do { app.again = false; await compute(); } while (app.again);
  } finally { app.running = false; }
}

async function compute() {
  const setup = readSetup(), quantity = radio("quantity"), d = app.inputs.data;
  saveHash();
  if ($("res-model").value === "import" && !app.imports.smearing) { status("⚠ Choose a smearing-matrix file (step 5).", true); return; }
  if ($("eff-model").value === "import" && !app.imports.efficiency) { status("⚠ Choose an efficiency file (step 5).", true); return; }
  try { engine.check(app.inputs, setup, quantity); } catch (error) { status(`⚠ ${error.message}`, true); return; }
  const night = engine.needsNight(quantity, setup.period);
  // A rate's solar-model range needs only the fluxes (one table); A_DN, where a single flux cancels,
  // needs every model's density profile (all day tables).
  const solarRange = quantity === "adn" ? "full" : "fluxes";
  const needed = [...(solarRange === "full" ? Object.keys(d.solar_models) : [setup.solar_model]).map((m) => `day_${m}`),
                  ...(night ? d.earth_models.map((e) => `night_${e}`) : [])].filter((n) => !app.tables.has(n));
  if (needed.length) {
    status(`Downloading ${needed.length} table${needed.length > 1 ? "s" : ""}…`);
    try { await app.tables.ensure(needed); } catch (error) { status(`Could not load the tables: ${error.message}`, true); return; }
  }
  status("Computing…");
  await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 0)));
  const t0 = performance.now(), params = engine.parameters(app.inputs, $("set").value);
  app.tables.clamped = 0;
  const { rows, samples } = engine.budget(app.inputs, app.tables, setup, params, quantity, { n: N_DRAWS, seed: SEED, solarRange });
  const spectra = engine.spectra(app.inputs, app.tables, setup, params, { n: N_DRAWS, seed: SEED, night });
  const flux = engine.fluxSummary(app.inputs, app.tables, setup, engine.oscillation(params));
  const ms = performance.now() - t0;
  const [scale, unit] = { adn: [100, "%"], ratio: [1, "of the unoscillated rate"] }[quantity] || UNITS[$("unit").value];
  const [spectrumScale, spectrumUnit] = quantity === "ratio" ? UNITS.kt : [scale, unit]; // the ratio's spectrum: the rate's
  const live = setup.exposure ? (setup.period === "annual" || quantity === "adn" ? setup.exposure : setup.exposure / 2) : null;
  const check = CHECKS.find((c) => c.id === $("check").value) || null;
  app.result = { setup, quantity, rows, samples, spectra, scale, unit, spectrumScale, spectrumUnit, live, set: $("set").value, ms, flux, check };
  render();
  setTimeout(thumb, 0); // the all-components example, after the result is on screen
  if (app.rendered.length || !$("plotipus").hidden) renderPlotipus(); // keep the plotipus figures in step
  const notes = [];
  if (app.tables.clamped) notes.push(`${app.tables.clamped} sampled points fell outside the tables and were moved to their edge.`);
  const fluxSampled = rows.some((r) => r.Source.includes("flux"));
  const allMeasured = setup.components.length === 1 && setup.components[0] === "B8" && setup.b8_flux === "sno_nc";
  if (!fluxSampled && !allMeasured && !(quantity === "adn" && setup.components.length === 1))
    notes.push("This solar model publishes no flux uncertainties: no flux error is sampled.");
  status(notes.join(" ")); // the timing goes in the result box (render)
  $("download").disabled = $("share").disabled = $("render").disabled = false;
}

// Target densities (g/cm^3), for the cross-section area of a 1 kt cube: water; liquid argon at its boiling point.
const DENSITY = { water: 1.0, argon: 1.3954, heavy_water: 1.105 }; // D2O at 20 °C

function renderFlux() {
  const r = app.result, f = r.flux, d = app.inputs.data, card = $("flux");
  const names = r.setup.components.map((c) => engine.DISPLAY[c]).join(", ");
  const per = r.setup.components.length > 1
    ? `<div class="sub">${r.setup.components.map((c) => `${engine.DISPLAY[c]} ${fmt(f.components[c][0])}`).join(" · ")}</div>` : "";
  let compare = "";
  if (r.quantity === "rate" && DENSITY[r.setup.detector]) {
    const side = (1e9 / DENSITY[r.setup.detector]) ** (1 / 3), crossing = f.total * side ** 2 * d.seconds_per_year;
    const rate = r.rows[0].Central;
    compare = `<div><h4>Flux against rate</h4><p>A 1 kt ${r.setup.detector === "water" ? "water" : "liquid-argon"} cube
      (${(side / 100).toFixed(1)} m side) is crossed by <b>${fmt(crossing)}</b> of these neutrinos a year;
      <b>${fmt(rate)}</b> are counted (${r.setup.period}, this channel and detector): one in <b>${fmt(crossing / rate)}</b>.</p></div>`;
  }
  card.innerHTML = `<div><h4>Flux at Earth</h4><div class="big">${fmt(f.total)} <small>cm⁻² s⁻¹</small></div>
      <div class="sub">${names} (${d.solar_models[r.setup.solar_model].label}); νₑ by day ${(100 * f.nue_day).toFixed(1)} %</div>${per}</div>
    ${compare}<div id="thumb"><h4>Your thumb against the Sun</h4><p class="hint">Computing…</p></div>`;
  card.hidden = false;
  if (app.thumb && app.thumb.key === thumbKey()) showThumb();
}

const thumbKey = () => `${$("set").value}|${$("solar").value}`;

async function thumb() {
  // every solar neutrino through a thumbnail, and how often they scatter in a thumb: all components, ES on the
  // electrons of water, no threshold, by day, central parameters of the chosen set and solar model
  const key = thumbKey();
  if (!app.inputs || (app.thumb && app.thumb.key === key)) { if (app.thumb) showThumb(); return; }
  const setup = engine.makeSetup({ solar_model: $("solar").value, components: ORDER, detector: "water", channel: "es" });
  const osc = engine.oscillation(engine.parameters(app.inputs, $("set").value));
  await app.tables.ensure([`day_${setup.solar_model}`]);
  const per = engine.componentTotals(app.inputs, app.tables, setup, osc, false);
  const rate = engine.combine(per, ORDER)[0]; // per kt yr
  app.thumb = { key, flux: engine.fluxSummary(app.inputs, app.tables, setup, osc).total, perYear: rate * THUMB_GRAMS * 1e-9 };
  showThumb();
}

function showThumb() {
  const t = app.thumb, node = $("thumb");
  if (!node) return;
  node.innerHTML = `<h4>Your thumb against the Sun</h4><p>A thumbnail (≈ 1 cm²) held up to the Sun is crossed by
    <b>${fmt(t.flux)}</b> solar neutrinos every second (all components). Of all of them, the ≈ ${THUMB_GRAMS} g of water
    in a thumb sees one scatter on an electron about once every <b>${fmt(1 / t.perYear)}</b> years.</p>`;
}

function thumbLine(r) {
  // the thumb preset: how often a thumb sees one of these interactions
  if ($("preset").value !== "thumb" || r.quantity !== "rate") return "";
  const perYear = r.rows[0].Central * THUMB_GRAMS * 1e-9; // per kt yr x kt
  return `<div class="sub thumb-line">In a ${THUMB_GRAMS} g thumb: ${fmt(perYear)} interactions a year, one about every <b>${fmt(1 / perYear)}</b> years,
    while ${fmt(r.flux.total)} neutrinos cross each cm² of it every second.</div>`;
}

function render() {
  const r = app.result;
  if (!r) return;
  const { setup, quantity, rows, scale, unit, live } = r;
  const total = rows.find((x) => x.Source === "total sampled"), central = total.Central;
  const sampled = rows.filter((x) => x.Kind === "sampled" && x.Source !== "total sampled").map((x) => x.Source);
  const ranges = rows.filter((x) => x.Kind === "model range").map((x) => quantity !== "adn"
    ? `${x.Source}: ${fmt(x.Low * scale)} to ${fmt(x.High * scale)} (${signed(100 * (x.Low / central - 1))} % / ${signed(100 * (x.High / central - 1))} %)`
    : `${x.Source}: ${(x.Low * scale).toFixed(3)} to ${(x.High * scale).toFixed(3)} %`);
  const events = live && quantity === "rate"
    ? `<div class="sub">Expected interactions in ${fmt(setup.exposure)} kt·yr: ${fmt(central * live, total.Sigma * live)}</div>` : "";
  $("headline").innerHTML = `
    <div class="what"><span>${describe(setup, quantity)} · ${app.inputs.data.parameter_sets.sets[r.set].label}</span>
      <span class="timing">Computed with ${N_DRAWS} draws in ${Math.round(r.ms)} ms.</span></div>
    <div class="sampled"><div class="value">${fmt(central * scale, total.Sigma * scale)}<small>${unit}</small></div>
      <div class="sub">± 1σ sampled from: ${sampled.join(", ")}</div>${events}</div>
    <div class="ranges"><b>Model ranges</b>${ranges.join("<br>") || "none for this setup"}</div>${thumbLine(r)}${publishedLine(r)}${measuredLine(r)}`;
  renderFlux();
  spectrumPlot($("plot-spectrum"), r);
  distributionPlot($("plot-distribution"), r, checkBand(r) || measuredBand(setup, quantity));
  budgetPlot($("plot-budget"), r);
  const cell = (v) => (Number.isFinite(v) ? fmt(v * scale) : "–");
  $("table").innerHTML = `<table><thead><tr><th>Source</th><th>Kind</th><th class="num">σ or range</th><th class="num">Relative</th></tr></thead><tbody>${
    rows.map((x) => `<tr><td>${x.Source}</td><td>${x.Kind}</td><td class="num">${x.Kind === "sampled" ? cell(x.Sigma) : `${cell(x.Low)} to ${cell(x.High)}`}</td><td class="num">${Number.isFinite(x.Relative) ? (100 * x.Relative).toFixed(2) + " %" : "–"}</td></tr>`).join("")
  }</tbody></table>`;
}

// ------------------------------------------------------------------ theme, share, download

function setupTheme() {
  const modes = ["system", "light", "dark"];
  let mode = "system";
  try { mode = localStorage.getItem("snufish-theme") || "system"; } catch { /* storage may be unavailable */ }
  const apply = () => {
    if (mode === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", mode);
    $("theme").textContent = `Theme: ${mode}`;
    render();
  };
  $("theme").addEventListener("click", () => {
    mode = modes[(modes.indexOf(mode) + 1) % modes.length];
    try { localStorage.setItem("snufish-theme", mode); } catch { /* ignore */ }
    apply();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
  apply();
}

// ------------------------------------------------------------------ plotipus in the page

const isDark = () => document.documentElement.dataset.theme === "dark"
  || (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);

async function renderPlotipus() {
  const result = app.result, id = ++app.renderId;
  if (!result) return;
  $("plotipus").hidden = false;
  $("render").disabled = true;
  app.rendered = [];
  const say = (text) => { $("plotipus-status").textContent = text; };
  say("Preparing…");
  try {
    if (!app.worker) {
      app.worker = new Worker("plotipus-worker.js", { type: "module" });
      app.worker.onmessage = ({ data }) => app.onWorker?.(data);
    }
    const wheel = new URL(`py/${(await (await fetch("py/manifest.json")).json()).plotipus}`, location.href).href;
    const { plotipusProject } = await import("./export.js");
    const { files, commands } = await plotipusProject(result, describe(result.setup, result.quantity), location.href);
    const t0 = performance.now();
    const answer = await new Promise((resolve) => {
      app.onWorker = (msg) => { if (msg.type === "progress") { if (id === app.renderId) say(msg.text); } else if (msg.id === id) resolve(msg); };
      app.worker.postMessage({ id, wheel, files, commands, theme: isDark() ? "dark" : "light" });
    });
    if (id !== app.renderId) return; // a newer result is being drawn
    if (answer.type === "error") throw new Error(answer.text);
    app.rendered = answer.images;
    const names = { spectrum: commands[0], samples: commands[2], budget: commands[1] }; // the page's order
    const rank = (name) => Object.keys(names).findIndex((k) => name.includes(`_${k}.png`));
    answer.images.sort((a, b) => rank(a.name) - rank(b.name));
    $("plotipus-figures").replaceChildren(...answer.images.map(({ name, bytes }) => {
      const fig = document.createElement("figure"), key = Object.keys(names).find((k) => name.includes(`_${k}.png`));
      fig.innerHTML = `<img alt="plotipus figure ${name}"><figcaption>plotipus ${names[key] || name}</figcaption>`;
      fig.querySelector("img").src = URL.createObjectURL(new Blob([bytes], { type: "image/png" }));
      return fig;
    }));
    say(answer.failed.length ? `Some commands failed: ${answer.failed.join("; ")}` : `Drawn in ${((performance.now() - t0) / 1000).toFixed(1)} s.`);
  } catch (error) {
    if (id === app.renderId) say(`plotipus failed: ${error.message}`);
  } finally {
    if (id === app.renderId) $("render").disabled = false;
  }
}

// ------------------------------------------------------------------ imported detector response

function numbers(text) {
  // rows of numbers from CSV or whitespace-separated text; # comments and blank lines skipped
  return text.split(/\r?\n/).map((line) => line.replace(/#.*/, "").trim()).filter(Boolean)
    .map((line, i) => line.split(/[\s,;]+/).map((v) => {
      const x = Number(v);
      if (!Number.isFinite(x)) throw new Error(`line ${i + 1}: "${v}" is not a number`);
      return x;
    }));
}

function parseEfficiency(text, name) {
  const rows = numbers(text);
  if (rows.length < 2 || rows.some((r) => r.length < 2)) throw new Error("need at least two lines of: energy, efficiency");
  const x = rows.map((r) => r[0]), raw = rows.map((r) => r[1]);
  const percent = Math.max(...raw) > 1.5, y = raw.map((v) => (percent ? v / 100 : v));
  if (y.some((v) => v < 0 || v > 1)) throw new Error("efficiencies must be between 0 and 1 (or 0 and 100 %)");
  return { id: `eff:${name}:${Date.now()}`, x, y, name, summary: `${x.length} points, ${x[0]}–${x[x.length - 1]} MeV${percent ? " (read as %)" : ""}` };
}

function parseSmearing(text, name) {
  const [obs, ...rows] = numbers(text);
  if (!obs || obs.length < 2 || !rows.length) throw new Error("need the observed-bin edges, then one line per true bin");
  const nObs = obs.length - 1, x = [];
  rows.forEach((r, i) => {
    if (r.length !== nObs + 2) throw new Error(`true bin ${i + 1}: expected 2 edges and ${nObs} probabilities, found ${r.length} numbers`);
    if (i > 0 && Math.abs(r[0] - x[x.length - 1]) > 1e-9) throw new Error(`true bin ${i + 1} does not start where the previous one ends`);
    if (i === 0) x.push(r[0]);
    x.push(r[1]);
  });
  let matrix = rows.map((r) => r.slice(2));
  const sums = matrix.map((r) => r.reduce((t, v) => t + v, 0));
  if (matrix.flat().some((v) => v < 0) || Math.max(...sums) > 1.001) throw new Error("probabilities must be ≥ 0 with each row summing to at most 1");
  matrix = matrix.map((r, i) => (sums[i] > 1 ? r.map((v) => v / sums[i]) : r)); // rounding: rows a hair above 1 scaled to 1
  return { id: `smear:${name}:${Date.now()}`, x, y: obs, matrix, true_axis: "observed", name,
           summary: `${rows.length} true × ${nObs} observed bins; rows sum ${Math.min(...sums).toFixed(3)}–${Math.min(1, Math.max(...sums)).toFixed(3)}` };
}

function setupImport(kind, fileId, infoId, parse) {
  $(fileId).addEventListener("change", async () => {
    const file = $(fileId).files[0];
    if (!file) return;
    try {
      app.imports[kind] = parse(await file.text(), file.name);
      $(infoId).textContent = `Imported ${file.name}: ${app.imports[kind].summary}.`;
      $("preset").value = "custom";
      sync(); schedule();
    } catch (error) {
      app.imports[kind] = null;
      $(infoId).textContent = `Could not read ${file.name}: ${error.message}`;
    }
  });
}

function download(name, text) {
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(new Blob([text], { type: "text/csv" })), download: name });
  document.body.append(a); a.click(); a.remove();
}

function templates() {
  // the file formats, filled from the current parametric settings
  $("eff-template").addEventListener("click", (e) => {
    e.preventDefault();
    const s = readSetup(), lines = ["# energy (MeV), efficiency (0-1): SNUfish template from the current settings"];
    for (let E = 0; E <= 25; E += 0.5) {
      let a = s.efficiency;
      if (s.efficiency_e50 > 0) a /= 1 + Math.exp(-(E - s.efficiency_e50) / s.efficiency_width);
      lines.push(`${E}, ${a.toPrecision(6)}`);
    }
    download("efficiency_template.csv", lines.join("\n") + "\n");
  });
  $("smear-template").addEventListener("click", (e) => {
    e.preventDefault();
    const s = { ...readSetup(), smearing_table: null }, edges = Array.from({ length: 51 }, (_, i) => 0.5 * i);
    const lines = ["# observed-bin edges (MeV), then per true bin: low, high, P(observed bin) ...",
                   "# SNUfish template: Gaussian smearing from the current resolution", edges.join(", ")];
    for (let i = 0; i + 1 < edges.length; i++) {
      const c = 0.5 * (edges[i] + edges[i + 1]), sigma = engine.resolution(app.inputs, s, c);
      const cdf = edges.map((x) => (sigma > 0 ? 0.5 * (1 + engine.erf((x - c) / sigma / Math.SQRT2)) : x > c ? 1 : 0));
      lines.push([edges[i], edges[i + 1], ...cdf.slice(1).map((v, k) => (v - cdf[k]).toPrecision(6))].join(", "));
    }
    download("smearing_template.csv", lines.join("\n") + "\n");
  });
}

function applyPreset(name) {
  applyValues(PRESETS[name]);
}

function applyValues(values) {
  if (!values) return;
  for (const id of ["detector", "channel"]) if (id in values) { $(id).value = values[id]; sync(); }
  for (const [id, v] of Object.entries(values)) {
    if (["detector", "channel"].includes(id)) continue;
    if (id === "components") document.querySelectorAll('input[name="components"]').forEach((x) => { x.checked = v.includes(x.value); });
    else if (id === "quantity" || id === "period" || id === "b8" || id === "es") setRadio(id, v);
    else $(id).value = v;
  }
}

// every field a check may leave untouched, at its default: a check sets the whole page
const CHECK_BASE = { set: "nufit60_global", solar: "b23_gs98", b8: "model", es: "bks", earth: "prem_full", "res-model": "quadrature",
                     "res-a": 0, "res-b": 0, "eff-model": "parametric", eff: 100, "eff-e50": 0, "eff-width": 0.5, mass: "", years: "",
                     "unc-scale": 0, "unc-res": 0, "unc-norm": 0, quantity: "rate", period: "annual", unit: "kt" };
const STEP5 = ["threshold", "res-model", "res-a", "res-b", "eff-model", "eff", "eff-e50", "eff-width", "mass", "years", "unc-scale", "unc-res", "unc-norm"];

function applyCheck(id) {
  const c = CHECKS.find((x) => x.id === id);
  if (!c) return;
  const { preset, ...values } = c.values;
  applyValues(CHECK_BASE);
  $("preset").value = preset;
  applyPreset(preset);
  applyValues(values);
  if (c.window) { // an energy window: the efficiency as a step from its low to its high edge
    const [lo, hi] = c.window;
    app.imports.efficiency = { id: `window:${lo}-${hi}`, x: [lo, hi - 1e-3, hi], y: [1, 1, 0], name: `${lo}–${hi} MeV window`,
                               summary: `${lo}–${hi} MeV, from the published check` };
    $("eff-model").value = "import";
    $("eff-info").textContent = `Energy window ${lo}–${hi} MeV (set by the published check).`;
  }
  if (c.window || Object.keys(values).some((k) => STEP5.includes(k))) $("preset").value = "custom"; // changed from the preset
}

function refreshSources() {
  // the open info boxes follow the current selection
  if (!app.inputs) return;
  const setup = readSetup(), quantity = radio("quantity");
  document.querySelectorAll(".step").forEach((step) => {
    const box = step.querySelector(".sources-box");
    if (!box.hidden) box.innerHTML = renderSources(forStep(Number(step.dataset.step), setup, quantity, app.inputs, $("set").value, $("preset").value));
  });
}

async function init() {
  setupTheme();
  try {
    app.inputs = new engine.Inputs(await (await fetch(`${DATA}inputs.json`)).json());
  } catch (error) {
    status(`Could not load the inputs (${error.message}). The page needs the data/ directory of snufish export-app.`, true);
    return;
  }
  app.tables = new engine.TableProbabilities(loadTable, app.inputs.data.parameter_sets.defaults.sin2_theta13.value);
  buildControls();
  for (const [name, c] of Object.entries(app.inputs.data.efficiency_curves || {})) // published curves, before "Imported curve"
    $("eff-model").insertBefore(new Option(`Published: ${c.label}`, `curve:${name}`), $("eff-model").querySelector('option[value="import"]'));
  sync();
  applyPreset($("preset").value); // the opening example, unless the link carries a setup
  sync();
  loadHash();
  sync();
  $("controls").addEventListener("change", (e) => {
    if (e.target.id === "unit") {
      if (app.result && app.result.quantity === "rate") [app.result.scale, app.result.unit] = UNITS[e.target.value];
      saveHash(); render(); return;
    }
    if (e.target.id === "check") applyCheck(e.target.value);
    else if (e.target.closest(".step")) $("check").value = ""; // edited by hand: no longer the published setup
    if (e.target.id === "preset") applyPreset(e.target.value);
    else if (e.target.id === "check") { /* set above */ }
    else if (e.target.closest('.step[data-step="5"]') || ($("preset").value === "thumb" && e.target.closest('.step[data-step="0"], .step[data-step="2"], .step[data-step="4"]')))
      $("preset").value = "custom"; // edited by hand: no longer the preset
    sync(); refreshSources(); schedule();
  });
  document.querySelectorAll("button.info").forEach((button) => button.addEventListener("click", () => {
    const box = button.closest(".step").querySelector(".sources-box"), open = box.hidden;
    box.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
    refreshSources();
  }));
  $("controls").addEventListener("input", (e) => { if (e.target.type === "number") { $("check").value = ""; sync(); schedule(); } });
  $("share").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(location.href); status("Link copied."); }
    catch { status(`Link: ${location.href}`); }
  });
  $("download").addEventListener("click", async () => {
    $("download").disabled = true;
    status("Preparing the download…");
    try {
      const { downloadResult } = await import("./export.js");
      await downloadResult(app.result, describe(app.result.setup, app.result.quantity), location.href, app.rendered);
      status("Downloaded: Parquet data, plotipus commands (plotipus run app) and the figures.");
    } catch (error) { status(`Download failed: ${error.message}`, true); }
    $("download").disabled = false;
  });
  if (HOSTED) {
    for (const id of ["render", "download", "share", "smear-template", "eff-template"]) $(id).hidden = true;
    const note = document.createElement("p");
    note.className = "hint";
    note.textContent = "In this hosted view the page cannot download files or draw plotipus figures, and the setup is not "
      + "kept in the link. Run the site locally for those (python web/build.py, then python -m http.server -d build/site).";
    $("download").closest(".actions").after(note);
  }
  $("render").addEventListener("click", renderPlotipus);
  setupImport("smearing", "smear-file", "smear-info", parseSmearing);
  setupImport("efficiency", "eff-file", "eff-info", parseEfficiency);
  templates();
  await run();
}

init();
