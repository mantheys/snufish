// Plotly figures of a result, in plotipus's look (style.css holds its palette and ink/paper roles):
// boxed axes, ticks inside on all four sides with minor ticks, no grid, frameless legends, DejaVu Sans.
import { DISPLAY, percentile } from "./engine.js";

const ORDER = ["pp", "pep", "hep", "Be7", "B8", "N13", "O15", "F17"]; // fixed colour slot per component

export function colours() {
  const css = getComputedStyle(document.documentElement), v = (name) => css.getPropertyValue(name).trim();
  return {
    text: v("--plot-ink"), secondary: v("--plot-ticklabel"), muted: v("--plot-muted"), axis: v("--plot-axis"),
    surface: v("--plot-paper"), sampled: v("--sampled"), range: v("--range"), measured: v("--measured"),
    component: Object.fromEntries(ORDER.map((c, i) => [c, v(`--series-${i + 1}`)])),
  };
}

function alpha(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}

const FONT = '"DejaVu Sans", Verdana, Geneva, sans-serif';

function layout(c, node, title, xTitle, yTitle, extra = {}) {
  node.previousElementSibling.textContent = title; // the card's heading: Plotly's toolbar would cover a title in the plot
  const axis = { showline: true, linecolor: c.axis, linewidth: 1, mirror: "allticks", ticks: "inside", ticklen: 6,
                 tickwidth: 1, tickcolor: c.axis, minor: { ticks: "inside", ticklen: 3, tickcolor: c.axis, showgrid: false },
                 showgrid: false, zeroline: false, tickfont: { color: c.secondary, size: 12 },
                 title: { font: { color: c.text, size: 13 } }, automargin: true };
  return {
    paper_bgcolor: c.surface, plot_bgcolor: c.surface, font: { family: FONT, color: c.text, size: 12 },
    margin: { l: 60, r: 16, t: 24, b: 48 }, hoverlabel: { bgcolor: c.surface, bordercolor: c.axis, font: { color: c.text, family: FONT } },
    legend: { orientation: "h", y: -0.22, x: 0, font: { color: c.text } },
    ...extra,
    xaxis: { ...axis, ...extra.xaxis, title: { ...axis.title, text: xTitle } },
    yaxis: { ...axis, ...extra.yaxis, title: { ...axis.title, text: yTitle } },
  };
}

const CONFIG = { responsive: true, displaylogo: false, displayModeBar: "hover",
                 modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d", "zoomIn2d", "zoomOut2d"] };
const ENERGY_TICKS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20];

function energyAxis(edges, values, floor) {
  // log axis over the bins with interactions, labelled 1-2-5
  const used = values.map((v, b) => (v > floor ? b : -1)).filter((b) => b >= 0);
  const lo = Math.max(edges[used.length ? used[0] : 0], 0.01), hi = edges[used.length ? used[used.length - 1] + 1 : edges.length - 1];
  const pad = 0.04 * Math.log10(hi / lo);
  return { type: "log", range: [Math.log10(lo) - pad, Math.log10(hi) + pad], tickvals: ENERGY_TICKS, ticktext: ENERGY_TICKS.map(String) };
}
function stairs(edges, values) {
  // explicit steps: two points per bin, a gap (null) for empty bins
  const x = [], y = [];
  values.forEach((v, b) => {
    if (v === null || !Number.isFinite(v)) { x.push(edges[b]); y.push(null); return; }
    x.push(edges[b], edges[b + 1]); y.push(v, v);
  });
  return { x, y };
}

function bandTraces(c, edges, low, high) {
  // one closed outline per run of bins with a band (a fill must not bridge empty bins)
  const traces = [];
  let b = 0;
  while (b < low.length) {
    if (low[b] === null || high[b] === null) { b++; continue; }
    const start = b;
    while (b < low.length && low[b] !== null && high[b] !== null) b++;
    const x = [], y = [];
    for (let k = start; k < b; k++) { x.push(edges[k], edges[k + 1]); y.push(high[k], high[k]); }
    for (let k = b - 1; k >= start; k--) { x.push(edges[k + 1], edges[k]); y.push(low[k], low[k]); }
    traces.push({ x, y, mode: "lines", fill: "toself", line: { width: 0 }, fillcolor: alpha(c.sampled, 0.45),
                  name: "sampled 68 %", legendgroup: "band", showlegend: traces.length === 0, hoverinfo: "skip" });
  }
  return traces;
}

export function pickPeriod(period, day, night) {
  if (period === "day") return day;
  if (period === "night") return night;
  return day.map((d, i) => 0.5 * (d + night[i]));
}

export function binAsymmetry(day, night) {
  const max = Math.max(...day);
  return day.map((d, i) => (d > 1e-9 * max ? 2 * (night[i] - d) / (night[i] + d) : NaN));
}

export function spectrumPlot(node, result) {
  const c = colours(), { setup, quantity, spectra, live } = result, edges = spectra.edges;
  const traces = [];
  if (quantity === "adn") {
    const a = binAsymmetry(spectra.day, spectra.night).map((v) => 100 * v);
    const draws = spectra.draws_day.map((d, i) => binAsymmetry(d, spectra.draws_night[i]));
    const low = a.map((v, b) => (Number.isFinite(v) ? 100 * percentile(draws.map((x) => x[b]), 16) : null));
    const high = a.map((v, b) => (Number.isFinite(v) ? 100 * percentile(draws.map((x) => x[b]), 84) : null));
    traces.push(...bandTraces(c, edges, low, high));
    traces.push({ ...stairs(edges, a), mode: "lines", name: "central",
                  line: { color: c.text, width: 2 }, hovertemplate: "%{y:.3f} %<extra>A_DN</extra>" });
    return Plotly.react(node, traces, layout(c, node, "Day-night asymmetry per energy bin", spectra.observable, "A_DN (%)",
      { xaxis: energyAxis(edges, spectra.day, 1e-9 * Math.max(...spectra.day)), hovermode: "x unified",
        shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { color: c.muted, dash: "dot", width: 1 } }] }), CONFIG);
  }
  const total = pickPeriod(setup.period, spectra.day, spectra.night);
  const draws = spectra.draws_day.map((d, i) => pickPeriod(setup.period, d, spectra.draws_night ? spectra.draws_night[i] : null));
  let low = total.map((_, b) => percentile(draws.map((x) => x[b]), 16));
  let high = total.map((_, b) => percentile(draws.map((x) => x[b]), 84));
  if (live) { // Poisson error per bin for the exposure, in quadrature
    const half = low.map((l, b) => 0.5 * (high[b] - l));
    const err = total.map((t, b) => Math.hypot(half[b], Math.sqrt(Math.max(t, 0) / live)));
    low = total.map((t, b) => t - err[b]); high = total.map((t, b) => t + err[b]);
  }
  const floor = Math.max(...total) * 1e-6, clip = (v) => (v > floor ? v : null); // log axis: hide empty bins
  traces.push(...bandTraces(c, edges, low.map((v, b) => (total[b] > floor ? Math.max(v, floor) : null)),
                            high.map((v, b) => (total[b] > floor ? v : null))));
  if (setup.components.length > 1) {
    for (const comp of setup.components) {
      const values = pickPeriod(setup.period, spectra.components[comp].day, spectra.components[comp].night);
      traces.push({ ...stairs(edges, values.map(clip)), mode: "lines", name: DISPLAY[comp],
                    line: { color: c.component[comp], width: 2.4 }, hovertemplate: "%{y:.4g}<extra>" + DISPLAY[comp] + "</extra>" });
    }
  }
  traces.push({ ...stairs(edges, total.map(clip)), mode: "lines", name: "total", line: { color: c.text, width: 2.4 },
                hovertemplate: "%{y:.4g}<extra>total</extra>" });
  const title = `Interactions per energy bin (${setup.period})` + (live ? ", band with statistics" : "");
  return Plotly.react(node, traces, layout(c, node, title, spectra.observable, "Interactions / (kt·yr) per bin",
    { xaxis: energyAxis(edges, total, floor), yaxis: { type: "log", dtick: 1, exponentformat: "power" }, hovermode: "x unified" }), CONFIG);
}

export function distributionPlot(node, result, measured) {
  const c = colours(), { rows, samples, scale, unit, quantity } = result;
  const values = samples["total sampled"].map((v) => v * scale), central = rows[0].Central * scale;
  const ranges = rows.filter((r) => r.Kind === "model range");
  const marks = measured ? [(measured[0] - measured[1]) * scale, (measured[0] + measured[1]) * scale] : [];
  const lo = Math.min(...values, ...ranges.map((r) => r.Low * scale), ...marks);
  const hi = Math.max(...values, ...ranges.map((r) => r.High * scale), ...marks);
  const nb = 25, width = (Math.max(...values) - Math.min(...values)) / nb || 1, start = Math.min(...values);
  const counts = new Array(nb).fill(0);
  values.forEach((v) => { counts[Math.min(nb - 1, Math.floor((v - start) / width))]++; });
  const top = Math.max(...counts);
  const shapes = [{ type: "line", x0: central, x1: central, y0: 0, y1: top * 1.05, line: { color: c.text, width: 2 } }];
  const annotations = [];
  ranges.forEach((r, k) => { // a bar per model range above the histogram, labelled above its left end
    const y = top * (1.15 + 0.2 * k);
    shapes.push({ type: "line", x0: r.Low * scale, x1: r.High * scale, y0: y, y1: y, line: { color: c.range, width: 6 } });
    annotations.push({ x: r.Low * scale, y, text: r.Source, showarrow: false, xanchor: "left", yanchor: "bottom", yshift: 4,
                       font: { size: 11, color: c.secondary } });
  });
  if (measured) {
    const [m, e, label] = measured;
    shapes.push({ type: "rect", x0: (m - e) * scale, x1: (m + e) * scale, y0: 0, y1: top * 1.05, line: { width: 0 },
                  fillcolor: alpha(c.measured, 0.2), layer: "below" });
    annotations.push({ x: m * scale, y: top * 0.5, text: label, showarrow: false, font: { size: 11, color: c.measured } });
  }
  const pad = 0.04 * (hi - lo || 1);
  const trace = { type: "bar", x: counts.map((_, i) => start + (i + 0.5) * width), y: counts, width: width * 0.92,
                  marker: { color: alpha(c.sampled, 0.8) }, name: `${values.length} draws`,
                  hovertemplate: `%{x:.4g} ${unit}: %{y} draws<extra></extra>` };
  const name = quantity === "adn" ? "A_DN" : "Rate";
  return Plotly.react(node, [trace], layout(c, node, quantity === "adn" ? "Sampled A_DN and model ranges" : "Sampled rates and model ranges", `${name} (${unit})`, "Draws",
    { shapes, annotations, showlegend: false, bargap: 0, margin: { l: 50, r: 16, t: 24, b: 48 },
      xaxis: { range: [lo - pad, hi + pad] }, yaxis: { range: [0, top * (1.25 + 0.2 * ranges.length)] } }), CONFIG);
}

export function budgetSizes(rows, quantity, scale) {
  // relative in % for rates; absolute (units of the quantity) for A_DN, which can be ~0
  return rows.map((r) => {
    const size = r.Kind === "sampled" ? r.Sigma : Math.max(r.High - r.Central, r.Central - r.Low);
    return quantity === "rate" ? 100 * size / Math.abs(r.Central) : size * scale;
  });
}

export function budgetPlot(node, result) {
  // one bar per source, labelled A, B, C… on the axis and named in a legend grouped by kind (long names would
  // squeeze the plot); the card grows with the number of sources so the legend never covers the axis
  const c = colours(), { rows, quantity, scale, unit } = result;
  const sizes = budgetSizes(rows, quantity, scale), letters = rows.map((_, i) => String.fromCharCode(65 + i));
  const fmt = (v) => (v >= 10 ? v.toFixed(1) : v >= 1 ? v.toFixed(2) : v.toPrecision(2));
  const traces = rows.map((r, i) => ({
    type: "bar", orientation: "h", y: [letters[i]], x: [sizes[i]], name: `${letters[i]} · ${r.Source}`,
    legendgroup: r.Kind, legendgrouptitle: { text: r.Kind === "sampled" ? "sampled 1σ" : "model range (largest deviation)" },
    marker: { color: r.Kind === "sampled" ? c.sampled : c.range }, text: [fmt(sizes[i])], textposition: "outside",
    cliponaxis: false, textfont: { color: c.secondary, size: 11 }, width: 0.7,
    hovertemplate: `${r.Source}: %{x:.3g}<extra>${r.Kind}</extra>`,
  }));
  const kinds = new Set(rows.map((r) => r.Kind)).size, legend = 18 * rows.length + 22 * kinds;
  node.style.height = `${260 + legend}px`;
  const xTitle = quantity === "rate" ? "Relative uncertainty (%)" : `Uncertainty (${unit})`;
  return Plotly.react(node, traces, layout(c, node, "Uncertainties", xTitle, "",
    { barmode: "overlay", margin: { l: 30, r: 16, t: 24, b: 56 + legend }, xaxis: { range: [0, 1.22 * Math.max(...sizes)] },
      yaxis: { categoryorder: "array", categoryarray: [...letters].reverse() },
      legend: { orientation: "v", yref: "container", y: 0, yanchor: "bottom", x: 0, xanchor: "left",
                font: { size: 11, color: c.text }, grouptitlefont: { size: 11, color: c.secondary }, tracegroupgap: 6 } }), CONFIG);
}
