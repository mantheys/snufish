// SNUfish page: controls, computation (engine.js on the tables in data/) and display.
import * as engine from "./engine.js";
import { budgetPlot, distributionPlot, spectrumPlot } from "./plots.js";

const DATA = "data/";
const N_DRAWS = 400, SEED = 1;
const CHANNELS = { es: "Elastic scattering on electrons", cc_nue_ar40: "νe CC on ⁴⁰Ar", cc_nue_o16: "νe CC on ¹⁶O" };
const DETECTORS = { argon: "Liquid argon", water: "Water" };
const XSEC = { default: "SNOwGLoBES default", ar40_klmv: "KLMV", ar40_marley: "MARLEY", ar40_marley1: "MARLEY (v1)" };
const EARTH = { prem_full: "PREM, ten regions", prem_four: "PREM, four regions", prem_prob3: "Four shells (Prob3++)" };
const KINDS = { reactor: "Reactor", solar: "Solar", global: "Global fits" };
const ORDER = ["pp", "pep", "hep", "Be7", "B8", "N13", "O15", "F17"];

const $ = (id) => document.getElementById(id);
const app = { inputs: null, tables: null, result: null, timer: null, running: false, again: false };

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

function readSetup() {
  const exposure = parseFloat($("exposure").value);
  return engine.makeSetup({
    solar_model: $("solar").value,
    components: [...document.querySelectorAll('input[name="components"]:checked')].map((x) => x.value),
    b8_flux: radio("b8"), site: $("site").value, earth_model: $("earth").value, detector: $("detector").value,
    channel: $("channel").value, xsec_model: $("xsec").value || "default", es_model: radio("es"),
    recoil_threshold: parseFloat($("threshold").value) || 0, period: radio("period"),
    exposure: exposure > 0 ? exposure : null,
  });
}

function sync() {
  // offer only what applies: channels of the target, threshold for ES, nuclear models for CC, the Earth only at night
  const d = app.inputs.data, detector = $("detector").value;
  const channels = Object.keys(d.detectors[detector].channels);
  fillSelect($("channel"), channels.map((c) => [c, CHANNELS[c] || c]), $("channel").value);
  const es = $("channel").value === "es";
  $("threshold-row").hidden = $("es-row").hidden = !es;
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
               xsec: "xsec", threshold: "threshold", exposure: "exposure" };
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
  if (quantity === "adn" && setup.channel === "es" && setup.site === "Kamioka" && Math.abs(setup.recoil_threshold - 3.49) < 0.01) {
    const m = app.inputs.data.measurements.sk_day_night;
    return [-m.value, Math.hypot(m.stat, m.syst), "Super-K ±1σ"];
  }
  return null;
}

function describe(setup, quantity) {
  const comps = setup.components.map((c) => engine.DISPLAY[c]).join(", ");
  const what = CHANNELS[setup.channel] + (setup.channel === "es" ? `, T > ${setup.recoil_threshold} MeV` : "");
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
  const ms = performance.now() - t0;
  const [scale, unit] = quantity === "adn" ? [100, "%"] : [1, "per kt·yr"];
  const live = setup.exposure ? (setup.period === "annual" || quantity === "adn" ? setup.exposure : setup.exposure / 2) : null;
  app.result = { setup, quantity, rows, samples, spectra, scale, unit, live, set: $("set").value, ms };
  render();
  const notes = [];
  if (app.tables.clamped) notes.push(`${app.tables.clamped} sampled points fell outside the tables and were moved to their edge.`);
  const fluxSampled = rows.some((r) => r.Source.includes("flux"));
  const allMeasured = setup.components.length === 1 && setup.components[0] === "B8" && setup.b8_flux === "sno_nc";
  if (!fluxSampled && !allMeasured && !(quantity === "adn" && setup.components.length === 1))
    notes.push("This solar model publishes no flux uncertainties: no flux error is sampled.");
  status(notes.join(" ") || `Computed with ${N_DRAWS} draws in ${Math.round(ms)} ms.`);
  $("download").disabled = $("share").disabled = false;
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
    ? `<div class="sub">Expected interactions in ${setup.exposure} kt·yr: ${fmt(central * live, total.Sigma * live)}</div>` : "";
  $("headline").innerHTML = `
    <div class="what">${describe(setup, quantity)} · ${app.inputs.data.parameter_sets.sets[r.set].label}</div>
    <div class="sampled"><div class="value">${fmt(central * scale, total.Sigma * scale)}<small>${unit}</small></div>
      <div class="sub">± 1σ sampled from: ${sampled.join(", ")}</div>${events}</div>
    <div class="ranges"><b>Model ranges</b>${ranges.join("<br>") || "none for this setup"}</div>`;
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
  $("controls").addEventListener("change", () => { sync(); schedule(); });
  $("controls").addEventListener("input", (e) => { if (e.target.type === "number") schedule(); });
  $("share").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(location.href); status("Link copied."); }
    catch { status(`Link: ${location.href}`); }
  });
  $("download").addEventListener("click", async () => {
    $("download").disabled = true;
    status("Preparing the download…");
    try {
      const { downloadResult } = await import("./export.js");
      await downloadResult(app.result, describe(app.result.setup, app.result.quantity), location.href);
      status("Downloaded: Parquet data, plotipus commands (plotipus run app) and the figures.");
    } catch (error) { status(`Download failed: ${error.message}`, true); }
    $("download").disabled = false;
  });
  await run();
}

init();
