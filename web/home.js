// SNUfish home page (index.html): the findings, each with a figure drawn from data/sections.json (snufish
// export-sections) and data/inputs.json, and the About tab (how the numbers are made, the status of every input,
// credits).
import * as engine from "./engine.js";
import { CONFIG, colours, htmlLegend, layout, themeIcon } from "./plots.js";
import { CREDITS, render as renderSources } from "./sources.js";

const DATA = "data/";
const ORDER = ["pp", "pep", "hep", "Be7", "B8", "N13", "O15", "F17"];
const DISPLAY = { pp: "pp", pep: "pep", hep: "hep", Be7: "⁷Be", B8: "⁸B", N13: "¹³N", O15: "¹⁵O", F17: "¹⁷F" };
const MARLEY = "ar40_marley2_bhattacharya2009";
const XSEC = { ar40_marley2_bhattacharya2009: "MARLEY 2, B(GT) (p,n) 2009", ar40_marley2_liu1998: "MARLEY 2, B(GT) Liu 1998",
               ar40_marley2_bhattacharya1998: "MARLEY 2, B(GT) Bhattacharya 1998", ar40_ksz2018: "Shell model, Kostensalo 2018 (g_A = 1)",
               ar40_marley1_bhattacharya2009: "MARLEY v1 model", ar40_marley: "SNOwGLoBES MARLEY (p,n)",
               ar40_marley1: "SNOwGLoBES MARLEY ⁴⁰Ti", ar40_klmv: "SNOwGLoBES KLMV", default: "SNOwGLoBES default" };
const SHORT_XS = { ar40_marley1_bhattacharya2009: "MARLEY v1", ar40_marley: "SNOwGLoBES MARLEY", ar40_marley1: "SNOwGLoBES ⁴⁰Ti",
                   ar40_klmv: "KLMV", default: "SNOwGLoBES default" };
const $ = (id) => document.getElementById(id);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const series = (n) => css(`--series-${n}`);
const page = { sections: null, inputs: null, tab: "overview", adn: null };

// ------------------------------------------------------------------ helpers

const sizeOf = (row, central) => { // per cent of the central value, as the benchmark pages
  const c = Math.abs(central);
  if (row.kind === "sampled") return 100 * row.sigma / c;
  if (row.kind === "model range") return 100 * Math.max(row.high - central, central - row.low) / c;
  return 100 * row.shift / c;
};
const row = (obs, source) => {
  const o = page.sections.observables[obs], r = o?.rows.find((x) => x.source === source);
  return r ? Math.abs(sizeOf(r, o.central)) : null;
};
const pct = (v) => { const a = Math.abs(v); return `${v < 0 ? "−" : v > 0 ? "+" : ""}${a >= 10 ? a.toFixed(0) : a >= 1 ? a.toFixed(1) : a.toPrecision(1)} %`; };
const interp = (xs, ys, x) => {
  if (x <= xs[0]) return ys[0];
  let i = 1;
  while (i < xs.length - 1 && xs[i] < x) i++;
  return ys[i - 1] + (x - xs[i - 1]) / (xs[i] - xs[i - 1]) * (ys[i] - ys[i - 1]);
};
const flat = (c, y) => ({ type: "line", xref: "paper", x0: 0, x1: 1, y0: y, y1: y, line: { color: c.muted, dash: "dot", width: 1 } });

// ------------------------------------------------------------------ the findings

function toolsVsInputs() {
  // 6. tools on the same inputs against the spread of competing inputs, on one log scale
  const c = colours(), node = $("plot-f6"), tools = page.sections.tools;
  // each tool against the reference on the spec's tool comparison (B2 b16_gs98, B3 four shells): identical inputs
  const perTool = (rows, label) => (rows || []).filter((r) => r.comparison).sort((a, b) => a.name.localeCompare(b.name))
    .map((r) => [`${label}: ${r.name} (|ΔP|)`, 100 * r.max_abs, "tools"]);
  const es = Math.max(...["water_es_b8", "scint_es_be7"].map((o) => row(o, "ES radiative corrections") || 0));
  const bars = [
    ...perTool(tools.B2_sun, "B2 Sun"),
    ...perTool(tools.B3_earth, "B3 Earth"),
    ["B4 ES: BKS vs SNOwGLoBES", es, "tools"],
    ["B1 osc. parameters, ⁸B ES", row("water_es_b8", "oscillation parameters"), "inputs"],
    ["B2 composition, ⁸B ES", row("water_es_b8", "solar model fluxes (production profiles fixed)"), "inputs"],
    ["B4 ⁴⁰Ar model, ⁸B CC", row("argon_cc_b8", "40Ar nuclear model"), "inputs"],
  ].filter(([, v]) => v !== null && v > 0);
  const colour = { tools: c.sampled, inputs: c.range };
  const trace = { type: "bar", orientation: "h", y: bars.map((b) => b[0]), x: bars.map((b) => b[1]),
                  marker: { color: bars.map((b) => colour[b[2]]) }, text: bars.map((b) => (b[1] < 0.01 ? `${b[1].toExponential(0)} %` : pct(b[1]).slice(1))),
                  textposition: "outside", cliponaxis: false, textfont: { size: 11, color: c.secondary }, hovertemplate: "%{y}: %{text}<extra></extra>" };
  htmlLegend(node, [{ label: "different tools, same inputs", colour: c.sampled, fill: true },
                    { label: "competing state-of-the-art inputs", colour: c.range, fill: true }]);
  return Plotly.react(node, [trace], layout(c, node, "Tools agree, inputs do not", "Largest difference (%), log scale", "",
    { showlegend: false, margin: { l: 20, r: 56, t: 16, b: 48 }, xaxis: { type: "log", range: [-6, 2.3], exponentformat: "power" },
      yaxis: { autorange: "reversed", automargin: true } }), CONFIG);
}

function outdated() {
  // 7. legacy inputs and approximations against the state of the art: shifts, not uncertainties
  const c = colours(), node = $("plot-f7"), d = page.inputs, xs = d.xsec.cc_nue_ar40, status = d.status || {};
  const at5 = (n) => 100 * (interp(xs[n].energy, xs[n].sigma, 5) / interp(xs[MARLEY].energy, xs[MARLEY].sigma, 5) - 1);
  const bars = Object.keys(xs).filter((n) => !n.includes("#") && status.xsec_model?.cc_nue_ar40?.[n]?.status === "legacy")
    .map((n) => [`B4 ⁴⁰Ar σ(5 MeV), ${SHORT_XS[n] || n}`, at5(n), "legacy"]).sort((a, b) => b[1] - a[1]);
  // A_DN of 8B without a crust (PREM's four regions) against PREM + the local crust (computed by adn())
  if (page.adn) for (const [site, kind, label] of [["Kamioka", "water", "⁸B ES"], ["SURF", "argon", "⁸B CC ⁴⁰Ar"]]) {
    const a = page.adn[site][kind];
    bars.push([`B3 A_DN ${label}, no crust (${site})`, 100 * (a.prem_four / a.prem_crust1 - 1), "approximation"]);
  }
  const m = d.solar_models;
  if (m.b16_gs98 && m.b23_mb22m) bars.push(["B2 ⁸B flux, B16 GS98", 100 * (m.b16_gs98.fluxes.B8 / m.b23_mb22m.fluxes.B8 - 1), "legacy"]);
    bars.sort((a, b) => a[0].slice(0, 2).localeCompare(b[0].slice(0, 2))); // B2, B3, B4: the calculator's order
const colour = { legacy: css("--series-7"), approximation: c.muted };
  const trace = { type: "bar", orientation: "h", y: bars.map((b) => b[0]), x: bars.map((b) => b[1]), marker: { color: bars.map((b) => colour[b[2]]) },
                  text: bars.map((b) => pct(b[1])), textposition: "outside", cliponaxis: false, textfont: { size: 11, color: c.secondary },
                  hovertemplate: "%{y}: %{text}<extra></extra>" };
  htmlLegend(node, [{ label: "legacy input", colour: colour.legacy, fill: true }, { label: "approximation", colour: colour.approximation, fill: true }],
             `Against MARLEY 2 (⁴⁰Ar), PREM + local crust (A_DN${page.adn ? "" : ": computing…"}), B23 MB22m (flux)`);
  const lo = Math.min(0, ...bars.map((b) => b[1])), hi = Math.max(0, ...bars.map((b) => b[1])), span = hi - lo;
  return Plotly.react(node, [trace], layout(c, node, "Legacy inputs and approximations: shifts, not uncertainties", "Shift from the state of the art (%)", "",
    { showlegend: false, margin: { l: 20, r: 56, t: 16, b: 48 }, xaxis: { range: [lo - 0.3 * span, hi + 0.25 * span], zeroline: true, zerolinecolor: c.muted },
      yaxis: { autorange: "reversed", automargin: true } }), CONFIG);
}

function composition() {
  // 2. (B2) the three state-of-the-art solar models, flux by flux, over B23 MB22m with its published 1 sigma
  const c = colours(), node = $("plot-f2"), models = page.inputs.solar_models, status = page.inputs.status?.solar_model || {};
  const ref = "b23_mb22m", current = Object.keys(models).filter((k) => status[k]?.status === "current");
  const colourOf = [series(1), series(2), series(3)];
  const traces = current.map((k, i) => ({
    x: ORDER.map((comp) => DISPLAY[comp]), y: ORDER.map((comp) => models[k].fluxes[comp] / models[ref].fluxes[comp]),
    mode: "markers", name: models[k].label, marker: { color: colourOf[i % 3], size: k === ref ? 9 : 8, symbol: k === ref ? "diamond" : "circle" },
    error_y: k === ref ? { type: "data", array: ORDER.map((comp) => models[k].flux_uncertainty[comp]), color: colourOf[i % 3], thickness: 1.5, width: 4 } : undefined,
    hovertemplate: `%{x}: %{y:.3f}<extra>${models[k].label}</extra>` }));
  htmlLegend(node, traces.map((t) => ({ label: t.name, colour: t.marker.color, fill: true })), `Error bars: ${models[ref].label}'s published 1σ`);
  return Plotly.react(node, traces, layout(c, node, "The state-of-the-art solar models disagree on composition", "Component", `Flux over ${models[ref].label}`,
    { showlegend: false, hovermode: "closest", xaxis: { minor: { ticks: "" } }, shapes: [flat(c, 1)] }), CONFIG);
}

// published folded cross sections not in the tables (docs/crosschecks.md, "40Ar: independent calculations"), as a
// ratio to MARLEY 2 with the (p,n) strengths on the same quantity
const PUBLISHED_AR40 = [
  ["Shell model, Suzuki & Honma 2013", 14.05 / 13.66, 0, "electrons above 5 MeV, PRC 87, 014607"],
  ["Shell model, Kostensalo 2018, free g_A", 2.64 / 2.72, 0, "⁸B-folded, PRC 97, 034309, sec. III E"],
];

function argon() {
  // 4. (B4) the state-of-the-art 40Ar cross sections folded over the 8B spectrum, over MARLEY 2 (p,n); the shell model of
  // Suzuki & Honma, which publishes one folded value only, and Kostensalo's with the free g_A, from the papers
  const c = colours(), node = $("plot-f4"), d = page.inputs, xs = d.xsec.cc_nue_ar40, status = d.status?.xsec_model?.cc_nue_ar40 || {};
  const b8 = d.components.B8, folded = (n) => {
    let t = 0;
    for (let i = 1; i < b8.energy.length; i++) {
      const e = 0.5 * (b8.energy[i] + b8.energy[i - 1]), w = 0.5 * (b8.shape[i] + b8.shape[i - 1]) * (b8.energy[i] - b8.energy[i - 1]);
      t += w * interp(xs[n].energy, xs[n].sigma, e);
    }
    return t;
  };
  const ref = folded(MARLEY);
  const bars = Object.keys(xs).filter((n) => !n.includes("#") && status[n]?.status === "current")
    .map((n) => [XSEC[n] || n, folded(n) / ref, n === "ar40_ksz2018" ? 0.23 / 1.78 * folded(n) / ref : 0, "table", "⁸B-folded, SNUfish tables"]).sort((a, b) => b[1] - a[1]);
  bars.push(...PUBLISHED_AR40.map(([name, v, e, how]) => [name, v, e, "published", how]));
  const colour = { table: c.range, published: series(5) };
  const trace = { type: "bar", orientation: "h", y: bars.map((b) => b[0]), x: bars.map((b) => b[1]), marker: { color: bars.map((b) => colour[b[3]]) },
                  error_x: { type: "data", array: bars.map((b) => b[2]), color: c.text, thickness: 1.2, width: 3 },
                  customdata: bars.map((b) => b[4]), text: bars.map((b) => b[1].toFixed(2)), textposition: "inside", insidetextanchor: "end",
                  textfont: { size: 11, color: "#fff" }, hovertemplate: "%{y}: %{x:.3f}<extra>%{customdata}</extra>" };
  htmlLegend(node, [{ label: "folded over the ⁸B spectrum (SNUfish tables)", colour: colour.table, fill: true },
                    { label: "published value only", colour: colour.published, fill: true }],
             "Kostensalo, g_A = 1.00: with its published error");
  return Plotly.react(node, [trace], layout(c, node, "νₑ CC on ⁴⁰Ar: how much the strength is quenched", "σ / σ(MARLEY 2, B(GT) (p,n) 2009)", "",
    { showlegend: false, margin: { l: 20, r: 20, t: 16, b: 48 }, xaxis: { range: [0, 1.15] },
      yaxis: { autorange: "reversed", automargin: true },
      shapes: [{ type: "line", yref: "paper", y0: 0, y1: 1, x0: 1, x1: 1, line: { color: c.muted, dash: "dot", width: 1 } }] }), CONFIG);
}

function earth() {
  // 3. (B3) the local crust: A_DN with PREM + CRUST1.0 over A_DN with PREM's average crust, per site (computed by adn())
  const c = colours(), node = $("plot-f3"), sites = Object.keys(page.inputs.sites);
  const kinds = [["water", "⁸B ES in water, T > 3.49 MeV", c.sampled], ["argon", "⁸B CC on ⁴⁰Ar, E_vis > 5 MeV", c.range]];
  const traces = page.adn ? kinds.map(([kind, name, colour]) => {
    const y = sites.map((site) => 100 * (page.adn[site][kind].prem_crust1 / page.adn[site][kind].prem_full - 1));
    return { type: "bar", x: sites, y, name, marker: { color: colour }, text: y.map(pct), textposition: "outside", cliponaxis: false,
             textfont: { size: 10, color: c.secondary }, hovertemplate: `%{x}: %{text}<extra>${name}</extra>` };
  }) : [];
  htmlLegend(node, kinds.map(([, name, colour]) => ({ label: name, colour, fill: true })),
             page.adn ? `Annual A_DN, ${page.inputs.parameter_sets.sets[page.sections.set]?.label || page.sections.set}, B23 MB22m` : "Computing A_DN at the five sites…");
  return Plotly.react(node, traces, layout(c, node, "The crust under the detector", "", "A_DN, local crust over PREM (%)",
    { showlegend: false, barmode: "group", bargap: 0.3, xaxis: { minor: { ticks: "" } }, yaxis: { range: [-4, 6] }, shapes: [flat(c, 0)] }), CONFIG);
}

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

async function adn() {
  // annual A_DN of 8B (+ hep) per site and Earth model with the calculator's engine and tables: ES in water above
  // 3.49 MeV and CC on 40Ar above 5 MeV, central values, no detector response
  const d = new engine.Inputs(page.inputs), models = ["prem_crust1", "prem_full", "prem_four"];
  const tables = new engine.TableProbabilities(loadTable, d.data.parameter_sets.defaults.sin2_theta13.value);
  const solar = page.sections.solar_model;
  await tables.ensure([`day_${solar}`, ...models.map((m) => `night_${m}`)]);
  const osc = engine.oscillation(engine.parameters(d, page.sections.set)), out = {};
  const KINDS = { water: { detector: "water", channel: "es", threshold: 3.49 }, argon: { detector: "argon", channel: "cc_nue_ar40", threshold: 5 } };
  for (const site of Object.keys(d.data.sites)) {
    out[site] = {};
    for (const [kind, extra] of Object.entries(KINDS)) {
      out[site][kind] = {};
      for (const m of models) {
        const setup = engine.makeSetup({ solar_model: solar, components: ["B8", "hep"], site, earth_model: m, ...extra });
        const [day, night] = engine.combine(engine.componentTotals(d, tables, setup, osc, true), setup.components);
        out[site][kind][m] = engine.quantityValue("adn", "annual", day, night);
      }
    }
  }
  return out;
}

function oscillations() {
  // 1. (B1) Delta m^2_21 and sin^2 theta_12 of the state-of-the-art parameter sets, with their 1 sigma
  const c = colours(), node = $("plot-f1"), sets = page.inputs.parameter_sets.sets, status = page.inputs.status?.parameter_set || {};
  const shown = Object.keys(sets).filter((k) => status[k]?.status === "current");
  const colourOf = { reactor: series(1), global: series(2), solar: series(3) }, symbol = { reactor: "square", global: "diamond", solar: "circle" };
  const seen = new Set();
  const traces = shown.map((k) => {
    const p = sets[k], dm = p.dm2_21_eV2, s = p.sin2_theta12;
    // two sets can share a point (SK + SNO and all solar): the second a hair to the right, so both show
    const key = `${s.value}|${dm.value}`, x = s.value + (seen.has(key) ? 0.0015 : 0);
    seen.add(key);
    return { x: [x], y: [1e5 * dm.value], mode: "markers", name: p.label,
             marker: { color: colourOf[p.kind] || series(5), size: 10, symbol: symbol[p.kind] || "circle", line: { width: 0 } },
             error_x: { type: "data", symmetric: false, array: [s.error[1]], arrayminus: [s.error[0]], color: colourOf[p.kind], thickness: 1.4, width: 3 },
             error_y: { type: "data", symmetric: false, array: [1e5 * dm.error[1]], arrayminus: [1e5 * dm.error[0]], color: colourOf[p.kind], thickness: 1.4, width: 3 },
             hovertemplate: `sin²θ₁₂ = ${s.value.toFixed(4)}, Δm²₂₁ = %{y:.2f} × 10⁻⁵ eV²<extra>${p.label}</extra>` };
  });
  htmlLegend(node, traces.map((t) => ({ label: t.name, colour: t.marker.color, fill: true })), "State-of-the-art parameter sets, 1σ");
  return Plotly.react(node, traces, layout(c, node, "Δm²₂₁: reactors against the Sun", "sin²θ₁₂", "Δm²₂₁ (10⁻⁵ eV²)",
    { showlegend: false, hovermode: "closest" }), CONFIG);
}

function folding() {
  // 5. (B5) SNOwGLoBES's full chain over SNUfish's folding of the same fluxes and cross sections, per component
  const c = colours(), node = $("plot-f5");
  const rows = (page.sections.tools.B5_rates || []).filter((r) => r.variant === "b16_gs98" && r.threshold === 0);
  const groups = [["water", "es", "ES in water", series(1)], ["argon", "es", "ES in argon", series(2)],
                  ["argon", "cc_nue_ar40", "CC on ⁴⁰Ar", series(5)]];
  const traces = groups.map(([detector, channel, name, colour]) => {
    const mine = ORDER.map((k) => rows.find((r) => r.detector === detector && r.channel === channel && r.component === k))
      .filter(Boolean);
    return { type: "bar", name, x: mine.map((r) => DISPLAY[r.component]), y: mine.map((r) => 100 * (r.ratio - 1)),
             marker: { color: colour }, hovertemplate: `%{x}, ${name}: %{y:+.2f} %<extra></extra>` };
  }).filter((t) => t.x.length);
  htmlLegend(node, traces.map((t) => ({ label: t.name, colour: t.marker.color, fill: true })),
             "B16-GS98, all energies, before any detector response");
  return Plotly.react(node, traces, layout(c, node, "SNOwGLoBES full chain against SNUfish's folding", "", "Tool ÷ SNUfish − 1 (%)",
    { showlegend: false, barmode: "group", margin: { l: 20, r: 20, t: 16, b: 40 },
      xaxis: { categoryorder: "array", categoryarray: ORDER.map((k) => DISPLAY[k]) }, yaxis: { automargin: true } }), CONFIG);
}

const FIGURES = [oscillations, composition, earth, argon, folding, toolsVsInputs, outdated]; // the findings: B1 to B5, then across steps

// ------------------------------------------------------------------ About: the status of every input

const CATEGORIES = { parameter_set: "Oscillation parameters", solar_model: "Solar model", earth_model: "Earth model",
                     es_model: "ν–e elastic scattering", xsec_model: "CC and NC cross sections" }; // B1 to B4
const STEP_OF = { parameter_set: "B1", solar_model: "B2", earth_model: "B3", es_model: "B4", xsec_model: "B4" };
const BADGE = { current: "state of the art", legacy: "legacy", approximation: "approximation" };
const CHANNELS = { cc_nue_ar40: "⁴⁰Ar", cc_nue_o16: "¹⁶O", cc_nue_d: "d CC", nc_d: "d NC", nc_ar40: "⁴⁰Ar NC" };
const XS_NAMES = { ar40_marley2_bhattacharya2009: "MARLEY 2, B(GT) (p,n) 2009", ar40_marley2_liu1998: "MARLEY 2, B(GT) Liu 1998",
                   ar40_marley2_bhattacharya1998: "MARLEY 2, B(GT) Bhattacharya 1998", ar40_ksz2018: "shell model, Kostensalo 2018",
                   ar40_marley1_bhattacharya2009: "MARLEY v1 model", ar40_marley1_allowed: "MARLEY v1 model, allowed",
                   ar40_marley: "SNOwGLoBES MARLEY (p,n)", ar40_marley1: "SNOwGLoBES MARLEY ⁴⁰Ti", ar40_klmv: "KLMV", default: "default table" };
const ES = { bks: "BKS", tree: "Tree level", snowglobes: "SNOwGLoBES (Marciano & Parsa)" };
const EARTH_NAMES = { prem_crust1: "PREM + local crust (CRUST1.0)", prem_full: "PREM, ten regions", prem_four: "PREM, four regions", prem_prob3: "Four shells (Prob3++)" };

function statusTable(d) {
  const status = d.status || {}, name = (category, key, channel) => ({
    parameter_set: d.parameter_sets.sets[key]?.label, solar_model: d.solar_models[key]?.label, earth_model: EARTH_NAMES[key],
    es_model: ES[key], xsec_model: `${CHANNELS[channel] || channel}: ${XS_NAMES[key] || key}` }[category] || key);
  const rows = [];
  for (const [category, title] of Object.entries(CATEGORIES)) {
    const tables = category === "xsec_model" ? Object.entries(status[category] || {}) : [[null, status[category] || {}]];
    for (const [channel, table] of tables)
      for (const [key, s] of Object.entries(table))
        rows.push(`<tr><td><span class="bench-id">${STEP_OF[category]}</span></td><td>${title}</td><td>${name(category, key, channel)}</td><td><span class="badge ${s.status}">${BADGE[s.status]}</span></td>
          <td>${s.summary}${s.superseded_by ? ` <i>Instead: ${name(category, s.superseded_by, channel)}.</i>` : ""}</td></tr>`);
  }
  $("status-table").innerHTML = rows.length
    ? `<table><thead><tr><th>Step</th><th>Choice</th><th>Input</th><th>Status</th><th>Why</th></tr></thead><tbody>${rows.join("")}</tbody></table>` : "";
}

// ------------------------------------------------------------------ tabs, theme

function draw() {
  if (page.tab !== "overview" || !page.sections || typeof Plotly === "undefined") return;
  for (const figure of FIGURES) {
    try { figure(); } catch (error) { console.warn(`home figure ${figure.name}:`, error); }
  }
}

function show() {
  // #about, and the anchors inside it (#status, #credits, linked from the calculator), open the About tab
  const hash = location.hash.slice(1), target = hash ? document.getElementById(hash) : null;
  page.tab = hash === "about" || target?.closest('[data-page="about"]') ? "about" : "overview";
  document.querySelectorAll("[data-page]").forEach((el) => { el.hidden = el.dataset.page !== page.tab; });
  document.querySelectorAll("nav.tabs a").forEach((a) => a.classList.toggle("active", a.dataset.tab === page.tab));
  if (target && hash !== "about") target.scrollIntoView();
  draw();
}

function setupTheme() {
  const modes = ["system", "light", "dark"];
  let mode = "system";
  try { mode = localStorage.getItem("snufish-theme") || "system"; } catch { /* storage may be unavailable */ }
  const apply = () => {
    if (mode === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", mode);
    themeIcon($("theme"), mode);
    draw();
  };
  $("theme").addEventListener("click", () => {
    mode = modes[(modes.indexOf(mode) + 1) % modes.length];
    try { localStorage.setItem("snufish-theme", mode); } catch { /* ignore */ }
    apply();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
  apply();
}

async function main() {
  $("credit-groups").innerHTML = CREDITS.map(([title, items]) => `<section class="step"><h2>${title}</h2>${renderSources(items)}</section>`).join("");
  setupTheme();
  addEventListener("hashchange", show);
  show();
  try {
    const [sections, inputs] = await Promise.all([`${DATA}sections.json`, `${DATA}inputs.json`].map(async (url) => {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`could not load ${url} (${response.status})`);
      return response.json();
    }));
    Object.assign(page, { sections, inputs });
    statusTable(inputs);
  } catch (error) {
    document.querySelectorAll(".finding .plot").forEach((el) => { el.hidden = true; });
    $("status").textContent = `The figures need data/sections.json and data/inputs.json (snufish export-app, export-sections): ${error.message}`;
    return;
  }
  if (typeof Plotly === "undefined") await new Promise((r) => addEventListener("load", r, { once: true })); // Plotly is deferred
  draw();
  try { page.adn = await adn(); draw(); } catch (error) { console.warn("home: A_DN not computed:", error); }
}

main();
