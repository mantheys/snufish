// SNUfish benchmark pages (benchmarks.html): what each benchmark varies, how well tools agree on it, and how
// much it moves five reference observables. Reads data/sections.json (snufish export-sections) and data/inputs.json;
// the discrepancies tab recomputes the calculator's result templates (checks.js) on its tables.
import * as engine from "./engine.js";
import { DISPLAY } from "./engine.js";
import { CHECKS, PAPER_SETS, UNITS, checkSetup, currentSetup, reproduced } from "./checks.js";
import { CONFIG, alpha, colours, htmlLegend, layout } from "./plots.js";

const DATA = "data/";
const ORDER = ["pp", "pep", "hep", "Be7", "B8", "N13", "O15", "F17"];
const SECTIONS = { oscillation: "Oscillation parameters", B1: "B1 solar models", B2: "B2 Sun", B3: "B3 Earth", B4: "B4 cross sections" };
const SECTION_SERIES = { oscillation: 9, B1: 2, B2: 1, B3: 6, B4: 5 }; // --series-N of each step
const SHORT = { water_es_b8: "⁸B ES, water", argon_cc_b8: "⁸B CC, ⁴⁰Ar", argon_cc_hep: "hep CC, ⁴⁰Ar",
                scint_es_be7: "⁷Be ES, scintillator", water_es_adn: "A_DN, water" };
const EARTH = { prem_crust1: "PREM + local crust (CRUST1.0)", prem_full: "PREM, ten regions", prem_four: "PREM, four regions", prem_prob3: "Four shells (Prob3++)" };
const MARLEY_DEFAULT = "ar40_marley2_bhattacharya2009"; // as export.MARLEY_DEFAULT
const XSEC = { ar40_marley2_bhattacharya2009: "MARLEY 2, B(GT) from (p,n) 2009", ar40_marley2_liu1998: "MARLEY 2, B(GT) Liu 1998",
               ar40_marley2_bhattacharya1998: "MARLEY 2, B(GT) Bhattacharya 1998", ar40_ksz2018: "Shell model (Kostensalo 2018)", ar40_marley1_bhattacharya2009: "MARLEY v1 model",
               default: "SNOwGLoBES default", ar40_klmv: "SNOwGLoBES KLMV" };
const CHANNELS = { es: "ES", cc_nue_ar40: "CC ⁴⁰Ar", cc_nue_o16: "CC ¹⁶O" };

const $ = (id) => document.getElementById(id);
// the palette without its two greys (series 4 and 9), which read as the oscillation bars and muted lines
const palette = () => [1, 2, 3, 5, 6, 7, 8, 10].map((n) => getComputedStyle(document.documentElement).getPropertyValue(`--series-${n}`).trim());
const page = { sections: null, inputs: null, tab: "overview" };
const sup = (s) => s.replace(/\b(7Be|8B|40Ar|16O|13N|15O|17F)\b/g, (m) => ({ "7Be": "⁷Be", "8B": "⁸B", "40Ar": "⁴⁰Ar", "16O": "¹⁶O",
                                                                           "13N": "¹³N", "15O": "¹⁵O", "17F": "¹⁷F" })[m]);

// ------------------------------------------------------------------ sizes

function size(row, central) {
  // per cent of the central value: sampled 1 sigma, largest deviation of a model range, signed shift of an approximation
  const c = Math.abs(central);
  if (row.kind === "sampled") return 100 * row.sigma / c;
  if (row.kind === "model range") return 100 * Math.max(row.high - central, central - row.low) / c;
  return 100 * row.shift / c;
}

const pct = (v) => {
  const a = Math.abs(v);
  if (a === 0) return "0";
  const s = a >= 10 ? a.toFixed(1) : a >= 0.1 ? a.toPrecision(2) : a >= 1e-4 ? a.toPrecision(1) : "< 0.0001";
  return `${v < 0 ? "−" : ""}${s} %`;
};
const FLOOR = 1e-4; // per cent: the left end of the log axes

// the overview counts state-of-the-art contributions only: sampled uncertainties and ranges over current models
// (export-sections builds them so); approximations and legacy spreads stay on each benchmark's own page
const stateOfTheArt = (r) => r.kind === "sampled" || r.kind === "model range";

function largest(rows, central, keep) {
  let best = null;
  for (const r of rows.filter(keep)) {
    const v = size(r, central);
    if (!best || Math.abs(v) > Math.abs(best.value)) best = { value: v, source: r.source, kind: r.kind };
  }
  return best;
}

// ------------------------------------------------------------------ overview

function matrix() {
  const obs = page.sections.observables, accent = colours().sampled;
  const columns = Object.keys(SECTIONS).map((s) => [s, SECTIONS[s], (r) => r.section === s && stateOfTheArt(r)]);
  const heads = { oscillation: "Oscillation", B1: "B1", B2: "B2", B3: "B3", B4: "B4" };
  const cell = (best) => {
    if (!best) return `<td class="num empty">–</td>`;
    const strength = Math.max(0, Math.min(1, (Math.log10(Math.abs(best.value)) + 2) / 3.5));
    return `<td class="num" style="background:${alpha(accent, 0.08 + 0.55 * strength)}" title="${sup(best.source)} (${best.kind})">${pct(best.value)}</td>`;
  };
  $("matrix").innerHTML = `<table><thead><tr><th>Observable</th><th class="num" title="Rates per kt·yr; A_DN in %">Central</th>${columns.map(([k, l]) => `<th class="num" title="${l}">${heads[k]}</th>`).join("")}</tr></thead><tbody>${
    Object.entries(obs).map(([id, o]) => `<tr><th title="${sup(o.label)}">${SHORT[id]}</th><td class="num">${central(o)}</td>${
      columns.map(([, , keep]) => cell(largest(o.rows, o.central, keep))).join("")}</tr>`).join("")}</tbody></table>`;
}

const central = (o) => (o.quantity === "adn" ? `${(100 * o.central).toFixed(2)} %` : o.central.toPrecision(4));

function overviewPlot() {
  const c = colours(), id = $("overview-observable").value, o = page.sections.observables[id], node = $("plot-overview");
  const rows = o.rows.filter(stateOfTheArt).sort((a, b) => Math.abs(size(a, o.central)) - Math.abs(size(b, o.central)));
  const traces = Object.keys(SECTIONS).map((s) => {
    const mine = rows.filter((r) => r.section === s);
    return { type: "bar", orientation: "h", name: SECTIONS[s], y: mine.map((r) => sup(r.source)),
             x: mine.map((r) => Math.max(Math.abs(size(r, o.central)), FLOOR)),
             text: mine.map((r) => `${pct(size(r, o.central))} · ${r.kind}`), textposition: "outside", cliponaxis: false,
             textfont: { size: 11, color: c.secondary }, hovertemplate: "%{y}: %{text}<extra></extra>",
             marker: { color: seriesColour(s) } };
  });
  htmlLegend(node, Object.keys(SECTIONS).map((s) => ({ label: SECTIONS[s], colour: seriesColour(s), fill: true })),
             "State-of-the-art inputs only: approximations and legacy models are on each benchmark's page.");
  node.style.height = `${Math.max(360, 34 * rows.length + 90)}px`;
  return Plotly.react(node, traces, layout(c, node, sup(o.label), "Relative to the central value (%), log scale", "",
    { showlegend: false, barmode: "overlay", margin: { l: 20, r: 90, t: 24, b: 48 },
      xaxis: { type: "log", range: [Math.log10(FLOOR), Math.log10(200)], exponentformat: "power" },
      yaxis: { categoryorder: "array", categoryarray: rows.map((r) => sup(r.source)), automargin: true } }), CONFIG);
}

const seriesColour = (section) => getComputedStyle(document.documentElement).getPropertyValue(`--series-${SECTION_SERIES[section]}`).trim();

// ------------------------------------------------------------------ impact of one step

function impactPlot(node, section) {
  // per observable: one bar per source of this step, the oscillation parameters in grey for scale
  const c = colours(), obs = page.sections.observables, ids = Object.keys(obs).reverse();
  const sources = [...new Set(Object.values(obs).flatMap((o) => o.rows.filter((r) => r.section === section).map((r) => r.source)))];
  const colourOf = palette();
  const trace = (source, colour, opacity = 1) => {
    const x = [], text = [];
    ids.forEach((id) => {
      const o = obs[id], r = o.rows.find((row) => row.source === source);
      const v = r ? size(r, o.central) : null;
      x.push(v === null ? null : Math.max(Math.abs(v), FLOOR)); text.push(v === null ? "" : pct(v));
    });
    return { type: "bar", orientation: "h", name: sup(source), y: ids.map((id) => SHORT[id]), x, text, textposition: "outside",
             cliponaxis: false, textfont: { size: 10, color: c.secondary }, marker: { color: alpha(colour, opacity) },
             hovertemplate: `%{y}: %{text}<extra>${sup(source)}</extra>` };
  };
  const traces = [trace("oscillation parameters", c.muted, 0.6), ...sources.map((s, i) => trace(s, colourOf[i % colourOf.length]))];
  const kindOf = (s) => Object.values(obs).flatMap((o) => o.rows).find((r) => r.source === s).kind;
  htmlLegend(node, traces.map((t, i) => ({ label: i ? `${t.name} <span class="kind">(${kindOf(sources[i - 1])})</span>` : "oscillation parameters (sampled, for scale)",
                                           colour: t.marker.color, fill: true })));
  node.style.height = `${Math.max(380, ids.length * (traces.length * 14 + 18) + 80)}px`;
  return Plotly.react(node, traces, layout(c, node, `Effect of ${SECTIONS[section]} on the reference observables`,
    "Relative to the central value (%), log scale", "",
    { showlegend: false, barmode: "group", bargap: 0.25, margin: { l: 20, r: 70, t: 24, b: 48 },
      xaxis: { type: "log", range: [Math.log10(FLOOR), Math.log10(200)], exponentformat: "power" } }), CONFIG);
}

// ------------------------------------------------------------------ B1

function b1() {
  impactPlot($("plot-b1-impact"), "B1");
  const c = colours(), models = page.inputs.solar_models, ref = page.sections.solar_model;
  const names = Object.keys(models);
  // fluxes over the reference model, its published 1 sigma as error bars
  let node = $("plot-b1-flux");
  const fluxTraces = names.map((m, i) => ({
    x: ORDER.map((comp) => DISPLAY[comp]), y: ORDER.map((comp) => models[m].fluxes[comp] / models[ref].fluxes[comp]),
    mode: "markers", name: models[m].label, marker: { color: palette()[i % 8], size: m === ref ? 9 : 7, symbol: m === ref ? "diamond" : i >= 8 ? "square" : "circle" },
    error_y: m === ref && models[m].flux_uncertainty ? { type: "data", array: ORDER.map((comp) => models[m].flux_uncertainty[comp]), color: palette()[i % 8], thickness: 1.5, width: 4 } : undefined,
    hovertemplate: `%{x}: %{y:.3f}<extra>${models[m].label}</extra>` }));
  htmlLegend(node, fluxTraces.map((t) => ({ label: t.name, colour: t.marker.color, fill: true })), `Error bars: ${models[ref].label}'s published 1σ`);
  Plotly.react(node, fluxTraces, layout(c, node, `Fluxes over ${models[ref].label}`, "Component", "Flux ratio",
    { showlegend: false, hovermode: "closest", xaxis: { minor: { ticks: "" } } }), CONFIG);
  // where each component is produced, in the chosen model
  const b1d = page.sections.b1, model = $("b1-model").value;
  node = $("plot-b1-production");
  const prodTraces = ORDER.map((comp, i) => ({ x: b1d.radius, y: b1d.models[model].production[comp], mode: "lines", name: DISPLAY[comp],
    line: { color: c.component[comp], width: 2 }, hovertemplate: `r = %{x:.3f}: %{y:.3g}<extra>${DISPLAY[comp]}</extra>` }));
  htmlLegend(node, prodTraces.map((t) => ({ label: t.name, colour: t.line.color })));
  Plotly.react(node, prodTraces, layout(c, node, `Production profiles (${models[model].label})`, "r / R☉", "Fraction per unit r / R☉",
    { showlegend: false, hovermode: "x unified", xaxis: { range: [0, 0.35] } }), CONFIG);
  // electron density
  node = $("plot-b1-density");
  const neTraces = names.map((m, i) => ({ x: b1d.radius, y: b1d.models[m].log_ne.map((v) => 10 ** v), mode: "lines", name: models[m].label,
    line: { color: palette()[i % 8], width: m === ref ? 2.6 : 1.4, dash: i >= 8 ? "dot" : undefined }, hovertemplate: `r = %{x:.3f}: %{y:.4g}<extra>${models[m].label}</extra>` }));
  htmlLegend(node, neTraces.map((t) => ({ label: t.name, colour: t.line.color, dash: !!t.line.dash })));
  Plotly.react(node, neTraces, layout(c, node, "Electron density", "r / R☉", "n_e (N_A / cm³)",
    { showlegend: false, hovermode: "closest", yaxis: { type: "log" }, xaxis: { range: [0, 0.4] } }), CONFIG);
}

// ------------------------------------------------------------------ B2

function componentRange(comp) {
  // [energies of the component] for the curves: a continuum's span, a line's energies
  const info = page.inputs.components[comp];
  if (info.lines) return { lines: info.lines.map((l) => l[0]) };
  const e = info.energy.filter((v, i) => info.shape[i] > 0);
  return { lo: Math.max(Math.min(...e), 0.1), hi: Math.max(...e) };
}

function curve(energy, values, comp) {
  const span = componentRange(comp);
  if (span.lines) {
    const log = energy.map(Math.log);
    return { x: span.lines, y: span.lines.map((e) => interpLog(log, values, Math.log(e))), line: true };
  }
  const keep = energy.map((e, i) => (e >= span.lo && e <= span.hi ? i : -1)).filter((i) => i >= 0);
  return { x: keep.map((i) => energy[i]), y: keep.map((i) => values[i]), line: false };
}

function interpLog(log, values, x) {
  let i = 1;
  while (i < log.length - 1 && log[i] < x) i++;
  const w = (x - log[i - 1]) / (log[i] - log[i - 1]);
  return values[i - 1] + w * (values[i] - values[i - 1]);
}

const energyAxis = { type: "log", tickvals: [0.1, 0.2, 0.5, 1, 2, 5, 10, 20], ticktext: ["0.1", "0.2", "0.5", "1", "2", "5", "10", "20"] };

function b2() {
  impactPlot($("plot-b2-impact"), "B2");
  const c = colours(), b2d = page.sections.b2, ref = page.sections.solar_model, models = page.inputs.solar_models;
  const trace = (comp, values, name, colour, dash) => {
    const k = curve(b2d.energy, values, comp);
    return { x: k.x, y: k.y, name, mode: k.line ? "markers" : "lines", line: { color: colour, width: 2.2, dash },
             marker: { color: colour, size: 9 }, hovertemplate: `%{x:.3g} MeV: %{y:.4f}<extra>${name}</extra>` };
  };
  let node = $("plot-b2-components");
  let traces = ORDER.map((comp) => trace(comp, b2d.treatments.own[comp], DISPLAY[comp], c.component[comp]));
  htmlLegend(node, traces.map((t) => ({ label: t.name, colour: t.line.color, fill: t.mode === "markers" })), "Lines: monoenergetic (points)");
  Plotly.react(node, traces, layout(c, node, `Daytime P_ee by component (${models[ref].label})`, "Neutrino energy (MeV)", "P_ee (day)",
    { showlegend: false, hovermode: "closest", xaxis: energyAxis }), CONFIG);

  const comp = $("b2-component").value, labels = b2d.treatment_labels;
  node = $("plot-b2-treatments");
  traces = Object.keys(b2d.treatments).map((t, i) => trace(comp, b2d.treatments[t][comp], labels[t], i ? palette()[i] : c.text, i ? "dash" : undefined));
  htmlLegend(node, traces.map((t) => ({ label: sup(t.name), colour: t.line.color, dash: t.line.dash === "dash" })));
  Plotly.react(node, traces, layout(c, node, `${DISPLAY[comp]}: where it is produced`, "Neutrino energy (MeV)", "P_ee (day)",
    { showlegend: false, hovermode: "x unified", xaxis: energyAxis }), CONFIG);

  node = $("plot-b2-models");
  const base = b2d.models[ref][comp];
  traces = Object.keys(b2d.models).map((m, i) => trace(comp, b2d.models[m][comp].map((v, k) => 1e3 * (v - base[k])), models[m].label, palette()[i % 8], i >= 8 ? "dot" : undefined));
  htmlLegend(node, traces.map((t) => ({ label: t.name, colour: t.line.color, dash: !!t.line.dash, fill: t.mode === "markers" })));
  Plotly.react(node, traces, layout(c, node, `${DISPLAY[comp]}: density and production of each model`, "Neutrino energy (MeV)", `P_ee − P_ee(${models[ref].label}) (×10⁻³)`,
    { showlegend: false, hovermode: "closest", xaxis: energyAxis }), CONFIG);
  $("b2-tools").innerHTML = toolTable(page.sections.tools.B2_sun, "F_i", "B2 fixes the production radius and energy grid; every solver gets the same n_e(r).");
}

function toolTable(rows, what, note) {
  if (!rows?.length) return `<p class="hint">No tool other than the reference has contributed yet.</p>`;
  return `<table><thead><tr><th>Tool</th><th>Variant</th><th class="num">Points</th><th class="num">Largest |Δ${what}| from the SNUfish reference</th></tr></thead><tbody>${
    rows.map((r) => `<tr><td>${r.tool}</td><td>${page.inputs.solar_models[r.variant]?.label || EARTH[r.variant] || r.variant}</td><td class="num">${r.points.toLocaleString()}</td><td class="num">${r.max_abs.toExponential(1)}</td></tr>`).join("")
  }</tbody></table><p class="hint">${note}</p>`;
}

// ------------------------------------------------------------------ B3

function b3() {
  impactPlot($("plot-b3-impact"), "B3");
  const c = colours(), b3d = page.sections.b3, site = $("b3-site").value;
  let node = $("plot-b3-models");
  let traces = Object.keys(b3d.models).map((m, i) => ({ x: b3d.energy, y: b3d.models[m][site].map((v) => 100 * v), mode: "lines", name: EARTH[m] || m,
    line: { color: palette()[i], width: 2.2 }, hovertemplate: `%{x:.3g} MeV: %{y:.3f}<extra>${EARTH[m] || m}</extra>` }));
  htmlLegend(node, traces.map((t) => ({ label: t.name, colour: t.line.color })));
  const axis = { ...energyAxis, range: [Math.log10(1), Math.log10(20)] };
  Plotly.react(node, traces, layout(c, node, `⁸B regeneration at ${site}`, "Neutrino energy (MeV)", "P_ee(night) − P_ee(day) (%)",
    { showlegend: false, hovermode: "x unified", xaxis: axis }), CONFIG);
  node = $("plot-b3-sites");
  traces = Object.keys(page.inputs.sites).map((s, i) => ({ x: b3d.energy, y: b3d.models.prem_full[s].map((v) => 100 * v), mode: "lines", name: s,
    line: { color: palette()[i], width: 2.2 }, hovertemplate: `%{x:.3g} MeV: %{y:.3f}<extra>${s}</extra>` }));
  htmlLegend(node, traces.map((t) => ({ label: `${t.name} (${page.inputs.sites[t.name].latitude_deg.toFixed(1)}° N)`, colour: t.line.color })));
  Plotly.react(node, traces, layout(c, node, "⁸B regeneration by site (PREM, ten regions)", "Neutrino energy (MeV)", "P_ee(night) − P_ee(day) (%)",
    { showlegend: false, hovermode: "x unified", xaxis: axis }), CONFIG);
  $("b3-tools").innerHTML = toolTable(page.sections.tools.B3_earth, "P", "P(νᵢ → νₑ) on B3's energy × nadir grids, for the Earth models both tools compute.");
}

// ------------------------------------------------------------------ B4

function b4() {
  impactPlot($("plot-b4-impact"), "B4");
  const c = colours(), xs = page.inputs.xsec.cc_nue_ar40;
  const nominal = xs[MARLEY_DEFAULT], incomplete = page.inputs.xsec_incomplete.cc_nue_ar40 || [];
  const ratio = (name) => {
    const x = [], y = [];
    xs[name].energy.forEach((e, i) => { if (e >= 5 && nominal.sigma[i] > 0) { x.push(e); y.push(xs[name].sigma[i] / nominal.sigma[i]); } });
    return { x, y };
  };
  let node = $("plot-b4-argon");
  const levels = Object.keys(xs).filter((n) => n.startsWith(`${MARLEY_DEFAULT}#`));
  const traces = levels.map((n, i) => ({ ...ratio(n), mode: "lines", name: "one level's B(GT) +1σ", showlegend: false,
    line: { color: alpha(c.muted, 0.6), width: 1 }, legendgroup: "levels", hovertemplate: `%{x:.1f} MeV: %{y:.3f}<extra>level ${i + 1}</extra>` }));
  const models = Object.keys(xs).filter((n) => !n.includes("#") && !incomplete.includes(n));
  models.forEach((n, i) => traces.push({ ...ratio(n), mode: "lines", name: XSEC[n] || n, line: { color: palette()[i % 8], width: 2.2 },
                                         hovertemplate: `%{x:.1f} MeV: %{y:.3f}<extra>${XSEC[n] || n}</extra>` }));
  htmlLegend(node, [{ label: "one level's B(GT) +1σ", colour: c.muted }, ...traces.slice(levels.length).map((t) => ({ label: t.name, colour: t.line.color }))]);
  Plotly.react(node, traces, layout(c, node, "νₑ CC on ⁴⁰Ar over MARLEY 2", "Neutrino energy (MeV)", "σ / σ(MARLEY 2, 2009)",
    { showlegend: false, hovermode: "closest", yaxis: { range: [0.3, 2] } }), CONFIG);
  node = $("plot-b4-es");
  const es = page.inputs.es_radiative_ratio;
  const esTraces = [["nue", "νₑ"], ["numu", "ν_μ,τ"]].map(([f, label], i) => ({ x: es[f].energy, y: es[f].ratio, mode: "lines", name: label,
    line: { color: palette()[i], width: 2.2 }, hovertemplate: `%{x:.2f} MeV: %{y:.4f}<extra>${label}</extra>` }));
  htmlLegend(node, esTraces.map((t) => ({ label: t.name, colour: t.line.color })));
  Plotly.react(node, esTraces, layout(c, node, "ES: SNOwGLoBES over tree level", "Neutrino energy (MeV)", "σ(SNOwGLoBES) / σ(tree)",
    { showlegend: false, hovermode: "x unified", xaxis: { type: "log", tickvals: energyAxis.tickvals, ticktext: energyAxis.ticktext },
      shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 1, y1: 1, line: { color: c.muted, dash: "dot", width: 1 } }] }), CONFIG);
}

// ------------------------------------------------------------------ B5

function b5() {
  const c = colours(), rows = (page.sections.tools.B5_rates || []).filter((r) => r.variant === "b16_gs98");
  const node = $("plot-b5-chain");
  const cases = [...new Set(rows.map((r) => `${r.detector} ${CHANNELS[r.channel] || r.channel}, ${r.threshold > 0 ? `E > ${r.threshold} MeV` : "all energies"}`))];
  const key = (r) => `${r.detector} ${CHANNELS[r.channel] || r.channel}, ${r.threshold > 0 ? `E > ${r.threshold} MeV` : "all energies"}`;
  const traces = cases.map((name, i) => {
    const mine = rows.filter((r) => key(r) === name).sort((a, b) => ORDER.indexOf(a.component) - ORDER.indexOf(b.component));
    return { x: mine.map((r) => ORDER.indexOf(r.component) + 0.08 * (i - (cases.length - 1) / 2)), y: mine.map((r) => r.ratio), mode: "markers", name,
             text: mine.map((r) => DISPLAY[r.component]), marker: { color: palette()[i % 8], size: 8, symbol: ["circle", "square", "diamond", "triangle-up"][i % 4] },
             hovertemplate: `%{text}: %{y:.4f}<extra>${name}</extra>` };
  });
  htmlLegend(node, traces.map((t) => ({ label: t.name, colour: t.marker.color, fill: true })));
  Plotly.react(node, traces, layout(c, node, "SNOwGLoBES full chain over SNUfish's folding (B16-GS98)", "Component", "Rate ratio",
    { showlegend: false, hovermode: "closest", xaxis: { tickvals: ORDER.map((_, i) => i), ticktext: ORDER.map((x) => DISPLAY[x]), range: [-0.5, ORDER.length - 0.5], minor: { ticks: "" } },
      shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 1, y1: 1, line: { color: c.muted, dash: "dot", width: 1 } }] }), CONFIG);
  $("b5-tools").innerHTML = rows.length ? `<table><thead><tr><th>Tool</th><th>Case</th><th>Component</th><th class="num">Tool (/kt·yr)</th><th class="num">SNUfish (/kt·yr)</th><th class="num">Ratio</th></tr></thead><tbody>${
    rows.map((r) => `<tr><td>${r.tool}</td><td>${key(r)}</td><td>${DISPLAY[r.component]}</td><td class="num">${r.rate.toPrecision(5)}</td><td class="num">${r.folded.toPrecision(5)}</td><td class="num">${r.ratio.toFixed(4)}</td></tr>`).join("")
  }</tbody></table><p class="hint">Same fluxes, oscillations and cross-section tables in both; B5 rates are daytime, in true neutrino energy, before any detector response.</p>`
    : `<p class="hint">No full-chain tool has contributed yet.</p>`;
}

// ------------------------------------------------------------------ discrepancies

async function loadTable(name) {
  // as app.js: a table's JSON index and its float32 binary (base64 text in a hosted copy)
  const meta = await (await fetch(`${DATA}${name}.json`)).json();
  const response = await fetch(`${DATA}${meta.bin}`);
  if (!response.ok) throw new Error(`could not load ${meta.bin} (${response.status})`);
  if (meta.encoding === "base64") {
    const text = atob((await response.text()).trim()), bytes = new Uint8Array(text.length);
    for (let i = 0; i < text.length; i++) bytes[i] = text.charCodeAt(i);
    return { meta, buffer: bytes.buffer };
  }
  return { meta, buffer: await response.arrayBuffer() };
}

async function templates() {
  // every template's central value as the calculator computes it (the paper's inputs), and again with every legacy
  // input and approximation replaced by the state of the art (reference/status.yaml), next to the published number
  Object.assign(page.inputs.parameter_sets.sets, PAPER_SETS);
  const inputs = new engine.Inputs(page.inputs);
  const tables = new engine.TableProbabilities(loadTable, page.inputs.parameter_sets.defaults.sin2_theta13.value);
  const value = async (c, { setup, quantity, set }) => {
    engine.check(inputs, setup, quantity);
    const night = engine.needsNight(quantity, setup.period);
    await tables.ensure([`day_${setup.solar_model}`, ...(night ? [`night_${setup.earth_model}`] : [])]);
    const osc = engine.oscillation(engine.parameters(inputs, set));
    return reproduced(c, engine.quantityValue(quantity, setup.period,
      ...engine.combine(engine.componentTotals(inputs, tables, setup, osc, night), setup.components)), setup.exposure);
  };
  const pull = (p, v) => (p.measured ? (v - p.value) / (v > p.value ? p.plus : p.minus) : undefined);
  const rows = [];
  for (const [order, c] of CHECKS.entries()) {
    const row = { check: c, order }, p = c.published;
    try {
      row.ours = await value(c, checkSetup(inputs, c));
      row.relative = 100 * (row.ours / p.value - 1);
      row.pull = pull(p, row.ours);
      const current = currentSetup(inputs, c);
      row.flagged = current.flagged;
      row.current = current.flagged.some((f) => f.by) ? await value(c, current) : row.ours;
      row.shift = 100 * (row.current / row.ours - 1);
      row.currentRelative = 100 * (row.current / p.value - 1);
      row.currentPull = pull(p, row.current);
    } catch (error) {
      row.error = String(error.message || error);
    }
    rows.push(row);
  }
  return rows;
}

const HEAT = [0.1, 20]; // per cent: the ends of the colour scale (log), as |relative difference|
const heat = (v) => Math.max(0, Math.min(1, Math.log10(Math.abs(v) / HEAT[0]) / Math.log10(HEAT[1] / HEAT[0])));
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const minus = (text) => text.replace("-", "−");
const signedPct = (v) => `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v) < 10 ? Math.abs(v).toFixed(2) : Math.abs(v).toFixed(1)} %`;

function paperNumber(p, v) {
  // as the calculator's published line: events whole, A_DN in per cent, the rest to four figures
  if (p.kind === "events") return Math.round(v).toLocaleString("en-US");
  if (p.kind === "adn") return minus(`${(100 * v).toFixed(2)} %`);
  return minus(Number(v.toPrecision(4)).toString());
}

const UNIT_OF = { rate: (p) => UNITS[p.unit][1], events: () => "events", ratio: () => "ratio", adn: () => "A_DN" };
const ES = { bks: "BKS radiative corrections", tree: "ES at tree level", snowglobes: "SNOwGLoBES ES" };
const STATUS_LABEL = { legacy: "legacy", approximation: "approximation", reproduction: "paper's parameters" }; // as app.js
const ORDERS = { size: (r) => -Math.abs(r.relative), shift: (r) => -Math.abs(r.shift), calculator: (r) => r.order };

function inputName(category, name) {
  // the labels of these pages, without the " · legacy" tags main() adds
  const label = { parameter_set: () => page.inputs.parameter_sets.sets[name]?.label, solar_model: () => page.inputs.solar_models[name]?.label,
                  earth_model: () => EARTH[name], xsec_model: () => XSEC[name], es_model: () => ES[name] }[category]?.() || name;
  return label.replace(/ · (legacy|approximation)$/, "");
}

function inputsCell(r) {
  // the paper's inputs that are not the state of the art, each with its status: what the reproduction rests on
  if (!r.flagged.length) return `<span class="badge current">state of the art</span>`;
  return r.flagged.map((f) => `<span class="input" title="${(f.status === "reproduction" ? "The scenario the paper computes: kept in the update." : f.summary).replace(/"/g, "&quot;")}">`
    + `<span class="badge ${f.status}">${STATUS_LABEL[f.status]}</span> ${inputName(f.category, f.name)}</span>`).join("");
}

async function discrepancies() {
  const note = $("discrepancy-status");
  if (!page.templates) {
    note.textContent = "Recomputing the calculator's templates…";
    page.templates = templates();
  }
  let rows;
  try { rows = await page.templates; } catch (error) {
    page.templates = null; // computed again the next time the tab opens
    note.textContent = `Could not compute the templates: ${error.message || error}`; note.classList.add("error"); return;
  }
  if (page.tab !== "discrepancies") return;
  const failed = rows.filter((r) => r.error);
  note.textContent = failed.length ? `${failed.length} template${failed.length > 1 ? "s" : ""} could not be computed: ${failed.map((r) => `${r.check.id} (${r.error})`).join("; ")}` : "";
  note.classList.toggle("error", failed.length > 0);
  const order = ORDERS[$("discrepancy-order").value];
  const shown = rows.filter((r) => !r.error).sort((a, b) => order(a) - order(b));
  // two questions, two colour scales: reproduction (the paper's own assumptions against its number) and update
  // (what the state-of-the-art models and measurements change in SNUfish's own number)
  const hues = { reproduction: css("--series-3"), update: css("--series-5") };
  const shade = (kind, strength) => alpha(hues[kind], 0.06 + 0.6 * strength);
  const strip = (kind) => `<i style="background:linear-gradient(to right, ${shade(kind, 0)}, ${shade(kind, 1)})"></i>`;
  const pullCell = (kind, v) => (v === undefined ? `<td class="num empty">–</td>`
    : `<td class="num" style="background:${shade(kind, Math.min(Math.abs(v) / 3, 1))}">${minus(v.toFixed(1))}σ</td>`);
  const empty = `<td class="num empty">–</td>`;

  $("discrepancy-scale").innerHTML = `<span class="key"><b>Reproduction</b> |Δ| ${HEAT[0]} % ${strip("reproduction")} ≥ ${HEAT[1]} %; pull 0 ${strip("reproduction")} ≥ 3σ</span>`
    + `<span class="key"><b>Update</b> |shift| ${HEAT[0]} % ${strip("update")} ≥ ${HEAT[1]} %; pull 0 ${strip("update")} ≥ 3σ</span>`;
  $("discrepancy-table").innerHTML = `<table><thead>`
    + `<tr><th colspan="2"></th><th colspan="5" class="group reproduction">Reproduction: the paper's own assumptions</th>`
    + `<th colspan="4" class="group update">Update: state-of-the-art models and measurements</th></tr>`
    + `<tr><th>Experiment</th><th title="Δm² is Δm²₂₁; T the electron's kinetic energy">Template and source (Δm² in 10⁻⁵ eV²)</th>`
    + `<th class="num">Published</th><th class="num" title="With the paper's inputs, as the calculator's template">SNUfish</th>`
    + `<th class="num" title="SNUfish ÷ published − 1: what SNUfish does not reproduce with the paper's assumptions">Δ</th>`
    + `<th class="num" title="Measurements: (SNUfish − measured) / its error">Pull</th><th>Paper's inputs</th>`
    + `<th>Replaced</th><th class="num" title="Every legacy input and approximation replaced by the state of the art">SNUfish</th>`
    + `<th class="num" title="State of the art ÷ paper's inputs − 1: what the newer models and measurements change">Shift</th>`
    + `<th class="num" title="Measurements: the state-of-the-art prediction's pull">Pull</th></tr></thead><tbody>${
    shown.map((r) => {
      const c = r.check, p = c.published, changed = r.flagged.some((f) => f.by);
      const published = `${paperNumber(p, p.value)}${p.measured ? ` <span class="error-bar">−${paperNumber(p, p.minus)} +${paperNumber(p, p.plus)}</span>` : ""}`;
      const points = p.kind === "adn" ? ` (${minus((100 * (r.ours - p.value)).toFixed(2))} points)` : "";
      const replaced = r.flagged.filter((f) => f.by);
      return `<tr><td>${c.group}</td><td class="template"><a href="rates.html#check=${encodeURIComponent(c.id)}" title="Open in the calculator">${c.label}</a>`
        + `<a class="source" href="https://arxiv.org/abs/${c.arxiv}" target="_blank" rel="noopener">${c.source}</a>`
        + `${c.note ? `<span class="note">${c.note}</span>` : ""}</td>`
        + `<td class="num start">${published}<span class="unit">${UNIT_OF[p.kind](p)}${p.measured ? ", measured" : ""}</span></td><td class="num">${paperNumber(p, r.ours)}</td>`
        + `<td class="num" style="background:${shade("reproduction", heat(r.relative))}" title="SNUfish ÷ published − 1${points}">${signedPct(r.relative)}</td>`
        + pullCell("reproduction", r.pull)
        + `<td class="inputs">${inputsCell(r)}</td>`
        + `<td class="inputs start">${replaced.length ? replaced.map((f) => `<span class="input" title="${f.summary.replace(/"/g, "&quot;")}">${inputName(f.category, f.name)} → ${inputName(f.category, f.by)}</span>`).join("") : `<span class="muted">nothing</span>`}</td>`
        + (changed ? `<td class="num">${paperNumber(p, r.current)}</td>`
            + `<td class="num" style="background:${shade("update", heat(r.shift))}" title="State of the art ÷ published − 1: ${signedPct(r.currentRelative)}">${signedPct(r.shift)}</td>`
            + pullCell("update", r.currentPull)
          : `<td class="num muted">same</td>${empty}${empty}`) + `</tr>`;
    }).join("")}</tbody></table>`;

  const c = colours(), node = $("plot-discrepancies"), ordered = [...shown].reverse(); // the first row at the top
  const names = ordered.map((r) => `${r.check.group}: ${r.check.label}`), y = ordered.map((_, i) => i);
  const bars = (kind, values, label) => ({
    type: "bar", orientation: "h", y, x: values, name: label,
    marker: { color: values.map((v) => alpha(hues[kind], 0.25 + 0.75 * heat(v))),
              line: { color: ordered.map((r) => (r.check.published.measured ? c.text : "rgba(0,0,0,0)")), width: 1 } },
    text: values.map((v) => (kind === "update" && Math.abs(v) < 0.05 ? "" : signedPct(v))), textposition: "outside", cliponaxis: false,
    textfont: { size: 9, color: c.secondary }, customdata: names, hovertemplate: `%{customdata}<br>${label}: %{x:.2f} %<extra></extra>` });
  const traces = [bars("update", ordered.map((r) => r.shift), "update, state of the art ÷ paper's inputs − 1"),
                  bars("reproduction", ordered.map((r) => r.relative), "reproduction, SNUfish ÷ published − 1")];
  const reach = Math.max(1, ...shown.flatMap((r) => [Math.abs(r.relative), Math.abs(r.shift)])) * 1.25;
  htmlLegend(node, [{ label: "Reproduction: SNUfish with the paper's own assumptions ÷ published − 1", colour: hues.reproduction, fill: true },
                    { label: "Update: SNUfish with state-of-the-art models and measurements ÷ SNUfish with the paper's − 1", colour: hues.update, fill: true }],
             "Outlined: a measurement (pulls in the table). The update bar is empty where every input the template uses is already the state of the art.");
  node.style.height = `${Math.max(400, 30 * shown.length + 90)}px`;
  return Plotly.react(node, traces, layout(c, node, "Two kinds of divergence, per template", "Relative difference (%)", "",
    { showlegend: false, barmode: "group", bargap: 0.25, bargroupgap: 0.05, margin: { l: 20, r: 60, t: 24, b: 48 },
      xaxis: { range: [-reach, reach] },
      yaxis: { tickvals: y, ticktext: names, automargin: true, minor: { ticks: "" }, tickfont: { size: 11 } },
      shapes: [{ type: "line", yref: "paper", y0: 0, y1: 1, x0: 0, x1: 0, line: { color: c.muted, width: 1 } }] }), CONFIG);
}

// ------------------------------------------------------------------ pages

const RENDER = { overview: () => { matrix(); overviewPlot(); }, B1: b1, B2: b2, B3: b3, B4: b4, B5: b5, discrepancies };

function show() {
  const tab = (location.hash || "#overview").slice(1);
  page.tab = RENDER[tab] ? tab : "overview";
  document.body.dataset.tab = page.tab; // the discrepancy table widens the page (style.css)
  document.querySelectorAll("[data-page]").forEach((el) => { el.hidden = el.dataset.page !== page.tab; });
  document.querySelectorAll("nav.tabs a").forEach((a) => a.classList.toggle("active", a.dataset.tab === page.tab));
  render();
}

function render() {
  if (page.sections) RENDER[page.tab]();
}

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

const fill = (select, entries, value) => {
  select.replaceChildren(...entries.map(([v, l]) => { const o = document.createElement("option"); o.value = v; o.textContent = l; o.selected = v === value; return o; }));
  select.addEventListener("change", render);
};

async function main() {
  try {
    const [sections, inputs] = await Promise.all([`${DATA}sections.json`, `${DATA}inputs.json`].map(async (url) => {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`could not load ${url} (${response.status}): run snufish export-sections`);
      return response.json();
    }));
    Object.assign(page, { sections, inputs });
  } catch (error) {
    $("status").textContent = String(error.message || error);
    $("status").classList.add("error");
    return;
  }
  // label every legacy model and approximation (reference/status.yaml) wherever it is named on these pages
  const status = page.inputs.status || {}, tag = (s) => (s && s.status !== "current" ? ` · ${s.status}` : "");
  for (const [m, info] of Object.entries(page.inputs.solar_models)) info.label += tag(status.solar_model?.[m]);
  for (const m of Object.keys(EARTH)) EARTH[m] += tag(status.earth_model?.[m]);
  for (const m of Object.keys(XSEC)) XSEC[m] += tag(status.xsec_model?.cc_nue_ar40?.[m]);
  const s = page.sections, set = page.inputs.parameter_sets.sets[s.set];
  $("reference-note").textContent = `Reference: ${set?.label || s.set} oscillation parameters, ${page.inputs.solar_models[s.solar_model].label} `
    + `fluxes and profiles, PREM with the local crust (CRUST1.0), MARLEY 2 for ⁴⁰Ar, BKS radiative corrections for ES; rates are annual averages without `
    + `detector response, ${s.draws} draws for the sampled sources. The full budget for any setup is in the calculator.`;
  fill($("overview-observable"), Object.entries(s.observables).map(([id, o]) => [id, sup(o.label)]), "argon_cc_hep");
  fill($("b1-model"), Object.entries(page.inputs.solar_models).map(([m, info]) => [m, info.label]), s.solar_model);
  fill($("b2-component"), ORDER.map((comp) => [comp, DISPLAY[comp]]), "hep");
  fill($("b3-site"), Object.keys(page.inputs.sites).map((site) => [site, site]), "Kamioka");
  $("discrepancy-order").addEventListener("change", render);
  addEventListener("hashchange", show);
  setupTheme();
  show();
}

main();
