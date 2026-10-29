// SNUfish page: controls, computation (engine.js on the tables in data/) and display.
import * as engine from "./engine.js";
import { budgetPlot, distributionPlot, spectrumPlot } from "./plots.js";
import { forStep, render as renderSources } from "./sources.js";

const DATA = "data/";
const N_DRAWS = 400, SEED = 1;
const CHANNELS = { es: "Elastic scattering on electrons", cc_nue_ar40: "νe CC on ⁴⁰Ar", cc_nue_o16: "νe CC on ¹⁶O" };
const DETECTORS = { argon: "Liquid argon", water: "Water" };
const XSEC = { default: "SNOwGLoBES default", ar40_klmv: "KLMV", ar40_marley: "MARLEY, B(GT) from (p,n)",
               ar40_marley1: "MARLEY, B(GT) from ⁴⁰Ti decay" };
const EARTH = { prem_full: "PREM, ten regions", prem_four: "PREM, four regions", prem_prob3: "Four shells (Prob3++)" };
const KINDS = { reactor: "Reactor", solar: "Solar", global: "Global fits" };
const ORDER = ["pp", "pep", "hep", "Be7", "B8", "N13", "O15", "F17"];
// Super-K IV, arXiv:2312.12907: resolution eq. 9; threshold table IV; 22.5 kt fiducial (fig. 28); 2970 days live
// (sec. V A 1); energy scale +-0.48 % (table II); resolution +-3 % (sec. IV A 3); other rate systematics +-1.1 % (table IV)
const SK4_RESOLUTION = [-0.05525, 0.3162, 0.04572];
const PRESETS = {
  sk4: { detector: "water", channel: "es", site: "Kamioka", threshold: 3.49, "res-model": "sk4", eff: 100, "eff-e50": 0,
         mass: 22.5, years: +(2970 / 365.25).toFixed(3), "unc-scale": 0.48, "unc-res": 3, "unc-norm": 1.1 },
};
const PRESET_NOTES = {
  custom: "",
  sk4: "Super-K IV as published (arXiv:2312.12907): resolution, threshold, fiducial mass, live time and detector uncertainties. "
     + "Its selection efficiency is only published as a figure (fig. 28) and is not included (100 %). "
     + "Without it, the energy-scale effect on the rate comes out ±0.5 % against Super-K's ±0.8 % (table IV).",
};

const $ = (id) => document.getElementById(id);
const app = { inputs: null, tables: null, result: null, timer: null, running: false, again: false,
              worker: null, rendered: [], renderId: 0 };

// ------------------------------------------------------------------ loading

async function loadTable(name) {
  const meta = await (await fetch(`${DATA}${name}.json`)).json();
  const response = await fetch(`${DATA}${meta.bin}`);
  if (!response.ok) throw new Error(`could not load ${meta.bin} (${response.status})`);
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
    energy_scale_error: number("unc-scale") / 100, resolution_error: number("unc-res") / 100,
    normalisation_error: number("unc-norm") / 100, exposure: exposure(),
  });
}

function sync() {
  // offer only what applies: channels of the target, threshold for ES, nuclear models for CC, the Earth only at night
  const d = app.inputs.data, detector = $("detector").value;
  const channels = Object.keys(d.detectors[detector].channels);
  fillSelect($("channel"), channels.map((c) => [c, CHANNELS[c] || c]), $("channel").value);
  const es = $("channel").value === "es";
  $("es-row").hidden = !es;
  $("res-ab").hidden = $("res-model").value !== "quadrature";
  $("preset-note").textContent = PRESET_NOTES[$("preset").value];
  $("threshold-label").textContent = es ? "Threshold on the electron kinetic energy T (MeV)" : "Threshold on the visible energy (MeV)";
  const q = d.visible_offset_MeV[$("channel").value];
  $("observable-note").textContent = es
    ? "Observed: the recoil electron's kinetic energy T."
    : `Observed: the visible energy E_ν − Q (Q = ${q} MeV; electron and de-excitation gammas, no neutron or binding losses).`;
  const exp = exposure();
  $("exposure-note").textContent = exp ? `Exposure ${fmt(exp)} kt·yr (half by night).` : "Set both for a statistical error.";
  const models = es ? [] : app.inputs.xsecModels($("channel").value);
  const keep = models.includes($("xsec").value) ? $("xsec").value : "default"; // the nominal model unless one was chosen
  fillSelect($("xsec"), models.map((m) => [m, XSEC[m] || m]), keep);
  $("xsec-row").hidden = models.length < 2;
  const comps = [...document.querySelectorAll('input[name="components"]:checked')].map((x) => x.value);
  $("b8-row").hidden = !comps.includes("B8");
  $("period-row").hidden = radio("quantity") !== "rate";
  const night = engine.needsNight(radio("quantity"), radio("period"));
  $("site").disabled = $("earth").disabled = !night;
  $("earth-note").textContent = night
    ? "Neutrinos cross the Earth at night; the site's latitude sets the path lengths through it."
    : "Not used: daytime neutrinos do not cross the Earth. Choose a night or annual rate, or the day-night asymmetry.";
  const p = d.parameter_sets.sets[$("set").value], dm = p.dm2_21_eV2, s = p.sin2_theta12;
  $("set-info").innerHTML = `Δm²₂₁ = ${(dm.value * 1e5).toFixed(2)} <span title="1σ">(−${(dm.error[0] * 1e5).toFixed(2)} +${(dm.error[1] * 1e5).toFixed(2)})</span> × 10⁻⁵ eV²<br>
    sin²θ₁₂ = ${s.value.toFixed(4)} (−${s.error[0].toFixed(4)} +${s.error[1].toFixed(4)})<br>
    θ₁₃, θ₂₃, δ, Δm²₃₁: NuFIT 6.0 · ${p.source}`;
}

// ------------------------------------------------------------------ URL state

const KEYS = { set: "set", solar: "solar", site: "site", earth: "earth", detector: "target", channel: "channel",
               xsec: "xsec", preset: "preset", threshold: "threshold", "res-model": "resolution", "res-a": "a", "res-b": "b",
               eff: "eff", "eff-e50": "e50", "eff-width": "width", mass: "mass", years: "years", "unc-scale": "dscale",
               "unc-res": "dres", "unc-norm": "dnorm" };
const RADIOS = { b8: "b8", es: "es", quantity: "q", period: "period" };

function saveHash() {
  const p = new URLSearchParams();
  for (const [id, key] of Object.entries(KEYS)) if ($(id).value) p.set(key, $(id).value);
  for (const [name, key] of Object.entries(RADIOS)) p.set(key, radio(name));
  p.set("components", readSetup().components.join(","));
  history.replaceState(null, "", `#${p}`);
}

function loadHash() {
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
  // from 1e5 on, in scientific notation with a common power of ten
  const big = Math.abs(value) >= 1e5, e = big ? Math.floor(Math.log10(Math.abs(value))) : 0, k = 10 ** e;
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
  if (quantity === "adn" && setup.channel === "es" && setup.site === "Kamioka" && Math.abs(setup.threshold - 3.49) < 0.01) {
    const m = app.inputs.data.measurements.sk_day_night;
    return [-m.value, Math.hypot(m.stat, m.syst), "Super-K ±1σ"];
  }
  return null;
}

function describe(setup, quantity) {
  const comps = setup.components.map((c) => engine.DISPLAY[c]).join(", ");
  const response = [];
  if (setup.threshold > 0) response.push(`${setup.channel === "es" ? "T" : "E_vis"} > ${setup.threshold} MeV`);
  if (setup.resolution_a > 0 || setup.resolution_b > 0) response.push("smeared");
  if (setup.efficiency < 1 || setup.efficiency_e50 > 0) response.push("efficiency");
  const what = CHANNELS[setup.channel] + (response.length ? `, ${response.join(", ")}` : "");
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
  const [scale, unit] = quantity === "adn" ? [100, "%"] : [1, "per kt·yr"];
  const live = setup.exposure ? (setup.period === "annual" || quantity === "adn" ? setup.exposure : setup.exposure / 2) : null;
  app.result = { setup, quantity, rows, samples, spectra, scale, unit, live, set: $("set").value, ms, flux };
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
const DENSITY = { water: 1.0, argon: 1.3954 };
const THUMB_GRAMS = 20; // a thumb, as water: an order of magnitude

function renderFlux() {
  const r = app.result, f = r.flux, d = app.inputs.data, card = $("flux");
  const names = r.setup.components.map((c) => engine.DISPLAY[c]).join(", ");
  const per = r.setup.components.length > 1
    ? `<div class="sub">${r.setup.components.map((c) => `${engine.DISPLAY[c]} ${fmt(f.components[c][0])}`).join(" · ")}</div>` : "";
  let compare = "";
  if (r.quantity === "rate") {
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

function render() {
  const r = app.result;
  if (!r) return;
  const { setup, quantity, rows, scale, unit, live } = r;
  const total = rows.find((x) => x.Source === "total sampled"), central = total.Central;
  const sampled = rows.filter((x) => x.Kind === "sampled" && x.Source !== "total sampled").map((x) => x.Source);
  const ranges = rows.filter((x) => x.Kind === "model range").map((x) => quantity === "rate"
    ? `${x.Source}: ${fmt(x.Low)} to ${fmt(x.High)} (${signed(100 * (x.Low / central - 1))} % / ${signed(100 * (x.High / central - 1))} %)`
    : `${x.Source}: ${(x.Low * scale).toFixed(3)} to ${(x.High * scale).toFixed(3)} %`);
  const events = live && quantity === "rate"
    ? `<div class="sub">Expected interactions in ${fmt(setup.exposure)} kt·yr: ${fmt(central * live, total.Sigma * live)}</div>` : "";
  $("headline").innerHTML = `
    <div class="what"><span>${describe(setup, quantity)} · ${app.inputs.data.parameter_sets.sets[r.set].label}</span>
      <span class="timing">Computed with ${N_DRAWS} draws in ${Math.round(r.ms)} ms.</span></div>
    <div class="sampled"><div class="value">${fmt(central * scale, total.Sigma * scale)}<small>${unit}</small></div>
      <div class="sub">± 1σ sampled from: ${sampled.join(", ")}</div>${events}</div>
    <div class="ranges"><b>Model ranges</b>${ranges.join("<br>") || "none for this setup"}</div>`;
  renderFlux();
  spectrumPlot($("plot-spectrum"), r);
  distributionPlot($("plot-distribution"), r, measuredBand(setup, quantity));
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

function applyPreset(name) {
  const values = PRESETS[name];
  if (!values) return;
  for (const id of ["detector", "channel"]) if (id in values) { $(id).value = values[id]; sync(); }
  for (const [id, v] of Object.entries(values)) if (!["detector", "channel"].includes(id)) $(id).value = v;
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
  app.tables = new engine.TableProbabilities(loadTable);
  buildControls();
  sync();
  loadHash();
  sync();
  $("controls").addEventListener("change", (e) => {
    if (e.target.id === "preset") applyPreset(e.target.value);
    else if (e.target.closest('.step[data-step="5"]')) $("preset").value = "custom"; // edited by hand: no longer the preset
    sync(); refreshSources(); schedule();
  });
  document.querySelectorAll("button.info").forEach((button) => button.addEventListener("click", () => {
    const box = button.closest(".step").querySelector(".sources-box"), open = box.hidden;
    box.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
    refreshSources();
  }));
  $("controls").addEventListener("input", (e) => { if (e.target.type === "number") { sync(); schedule(); } });
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
  $("render").addEventListener("click", renderPlotipus);
  await run();
}

init();
