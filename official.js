// Official figures of the published checks (checks.js), recomputed with the engine and drawn with plotipus:
// each holds the SNUfish curves and the paper's own numbers, and only numbers the paper prints (none read off a
// figure). officialFigure(check, ctx) -> {title, caption, source, url, columns, x, y, command options} or null.
import * as engine from "./engine.js";

const ARXIV = (id) => `https://arxiv.org/abs/${id}`;
const adnPaper = (d, n) => 100 * 2 * (d - n) / (d + n); // (D - N)/mean, in %, as Super-K and JUNO plot it

function table(rows) {
  // long format for plotipus: Series, X (number or label), Y, YError, XError
  const cols = { Series: [], X: [], Y: [], YError: [], XError: [] };
  for (const r of rows) {
    cols.Series.push(r.series); cols.X.push(r.x); cols.Y.push(r.y);
    cols.YError.push(r.yerr ?? 0); cols.XError.push(r.xerr ?? 0);
  }
  return cols;
}

function oscillation(ctx, setName, custom = {}) {
  return engine.oscillation(engine.parameters(ctx.inputs, setName, custom));
}

function totals(ctx, setup, osc) {
  return engine.combine(engine.componentTotals(ctx.inputs, ctx.tables, setup, osc, true), setup.components);
}

const DM_GRID = Array.from({ length: 33 }, (_, i) => 3.0 + 0.25 * i); // the tables' Δm²₂₁ range, 10⁻⁵ eV²

function superK(ctx, check, combined) {
  // Super-K arXiv:2312.12907 fig. 49 (SK-IV) or 52 (SK-I-IV, SK-I energy range): expected A_DN against Δm²₂₁,
  // with the expected and measured values the paper prints at 6.1 (and 4.8, 7.5) × 10⁻⁵ eV²
  const rows = DM_GRID.map((dm) => {
    const [d, n] = totals(ctx, ctx.setup, oscillation(ctx, "paper_sk_61", { dm2_21_eV2: dm * 1e-5 }));
    return { series: "SNUfish expected", x: dm, y: adnPaper(d, n) };
  });
  const expected = combined ? [[4.8, -3.84], [6.1, -2.42], [7.5, -1.72]] : [[6.1, -2.38]];
  // measured: stat ⊕ syst (sec. VIII: SK-IV −2.62 ± 1.07 ± 0.30; SK combined at 4.8, 6.1, 7.5 × 10⁻⁵ eV²)
  const measured = combined ? [[4.8, -2.73, Math.hypot(0.86, 0.32)], [6.1, -2.86, Math.hypot(0.85, 0.32)], [7.5, -2.74, Math.hypot(0.83, 0.32)]]
                            : [[6.1, -2.62, Math.hypot(1.07, 0.30)]];
  expected.forEach(([x, y]) => rows.push({ series: "Super-K expected", x, y }));
  measured.forEach(([x, y, yerr]) => rows.push({ series: combined ? "SK-I–IV measured" : "SK-IV measured", x, y, yerr }));
  return {
    title: combined ? "Super-K fig. 52: SK-I–IV day-night asymmetry against Δm²₂₁" : "Super-K fig. 49: SK-IV day-night asymmetry against Δm²₂₁",
    source: `Super-K, arXiv:2312.12907, fig. ${combined ? 52 : 49} and sec. VIII`, url: ARXIV("2312.12907"),
    caption: "SNUfish's expected A_DN (plain rate asymmetry, (D − N)/mean) over the Δm²₂₁ range of its tables (3–11 × 10⁻⁵ eV²; "
           + "the figure spans 2–22). Points: the expected and measured asymmetries the paper prints (measured: stat ⊕ syst); "
           + "its measured best-fit line over Δm²₂₁ is only drawn, not tabulated.",
    columns: table(rows), xLabel: "Δm²₂₁ (10⁻⁵ eV²)", yLabel: "Day/night asymmetry (%)",
    points: ["Super-K expected", combined ? "SK-I–IV measured" : "SK-IV measured"], horizontal: 0,
  };
}

function junoProbabilities(ctx) {
  // JUNO arXiv:2006.11760 fig. 3: ⁸B P_ee(E_ν) by day, by night and averaged, for Δm²₂₁ = 4.8 and 7.5 × 10⁻⁵ eV²
  const setup = engine.makeSetup({ ...ctx.setup, components: ["B8"] }), rows = [];
  const energy = ctx.inputs.components.B8.energy;
  for (const set of ["paper_juno_48", "paper_juno_75"]) {
    const [day, night] = engine.survival(ctx.inputs, ctx.tables, setup, oscillation(ctx, set), true).B8;
    const label = set.endsWith("48") ? "4.8" : "7.5";
    energy.forEach((e, k) => {
      if (e < 2 || e > 16) return;
      rows.push({ series: `Δm² ${label}: day`, x: e, y: day[k] });
      rows.push({ series: `Δm² ${label}: night`, x: e, y: night[k] });
      rows.push({ series: `Δm² ${label}: average`, x: e, y: 0.5 * (day[k] + night[k]) });
    });
  }
  return {
    title: "JUNO fig. 3: ⁸B νe survival probability by day and night",
    source: "JUNO, arXiv:2006.11760, fig. 3", url: ARXIV("2006.11760"),
    caption: "SNUfish's P_ee(E_ν) at Jiangmen with JUNO's PDG 2018 mixing, for the two Δm²₂₁ of the paper. The figure shades the "
           + "spread over solar zenith angles; SNUfish gives the day and the night average.",
    columns: table(rows), xLabel: "Neutrino energy (MeV)", yLabel: "νe survival probability P_ee", points: [],
  };
}

function junoAsymmetry(ctx) {
  // JUNO arXiv:2006.11760 table 7: A_DN in four visible-energy windows at Δm²₂₁ = 4.8 × 10⁻⁵ eV²
  const rows = [], osc = oscillation(ctx, "paper_juno_48");
  for (const [lo, hi, value, error] of [[2, 3, -2.1, 3.2], [3, 5, -2.5, 1.7], [5, 16, -3.4, 1.2], [2, 16, -2.9, 0.9]]) {
    const setup = engine.makeSetup({ ...ctx.setup, threshold: lo,
      efficiency_table: { id: `window:${lo}-${hi}`, x: [lo, hi - 1e-3, hi], y: [1, 1, 0] } });
    const [d, n] = totals(ctx, setup, osc), label = `${lo}–${hi} MeV`;
    rows.push({ series: "JUNO (table 7)", x: label, y: value, yerr: error });
    rows.push({ series: "SNUfish", x: label, y: adnPaper(d, n) });
  }
  return {
    title: "JUNO table 7: day-night asymmetry per energy window",
    source: "JUNO, arXiv:2006.11760, table 7", url: ARXIV("2006.11760"),
    caption: "A_DN = (D − N)/mean at Δm²₂₁ = 4.8 × 10⁻⁵ eV² in JUNO's visible-energy windows. JUNO's errors are its expected "
           + "ten-year uncertainties.",
    columns: table(rows), xLabel: "Visible-energy window", yLabel: "A_DN (%)", points: ["JUNO (table 7)", "SNUfish"], horizontal: 0,
  };
}

function sno(ctx) {
  // SNO arXiv:1109.0763 fig. 10 (left): daytime P_ee(E_ν) = c0 + c1 (E − 10) + c2 (E − 10)², table VII and VIII
  const c = [0.317, 0.0039, -0.0010];
  const sigma = [Math.hypot(0.016, 0.009), Math.hypot(0.0066, 0.0045), Math.hypot(0.0029, 0.0015)]; // stat ⊕ syst
  const rho = [[1, -0.299, -0.366], [-0.299, 1, -0.206], [-0.366, -0.206, 1]];
  const setup = engine.makeSetup({ ...ctx.setup, components: ["B8"] }), rows = [];
  const energy = ctx.inputs.components.B8.energy;
  const [day] = engine.survival(ctx.inputs, ctx.tables, setup, oscillation(ctx, ctx.set), false).B8;
  energy.forEach((e, k) => {
    if (e < 5 || e > 15) return;
    const j = [1, e - 10, (e - 10) ** 2];
    let variance = 0;
    for (let a = 0; a < 3; a++) for (let b = 0; b < 3; b++) variance += j[a] * j[b] * sigma[a] * sigma[b] * rho[a][b];
    rows.push({ series: "SNO fit (c₀, c₁, c₂)", x: e, y: c[0] + c[1] * j[1] + c[2] * j[2], yerr: Math.sqrt(variance) });
    rows.push({ series: "SNUfish, day", x: e, y: day[k] });
  });
  return {
    title: "SNO fig. 10: daytime νe survival probability",
    source: "SNO, arXiv:1109.0763, fig. 10, tables VII and VIII", url: ARXIV("1109.0763"),
    caption: "SNO's quadratic P_ee^day with its 1σ band (stat ⊕ syst, with the fit's correlations), and SNUfish's daytime P_ee at "
           + "SNOLAB for the selected parameter set.",
    columns: table(rows), xLabel: "Neutrino energy (MeV)", yLabel: "P_ee (day)", points: [], band: "SNO fit (c₀, c₁, c₂)",
  };
}

function borexino(ctx) {
  // Borexino arXiv:1707.09279 table II: measured rates (stat ⊕ syst) and the B16-GS98 prediction, over the prediction
  const rows = [], osc = oscillation(ctx, "nufit60_global"), k = 0.1 * 86400 / ctx.inputs.data.seconds_per_year;
  const table2 = { pp: [134, 10, 6, 10, 131.1, 1.4], Be7: [48.3, 1.1, 0.4, 0.7, 47.9, 2.8], pep: [2.43, 0.36, 0.15, 0.22, 2.74, 0.04] };
  for (const [c, [value, stat, up, down, predicted, perr]] of Object.entries(table2)) {
    const setup = engine.makeSetup({ ...ctx.setup, solar_model: "b16_gs98", components: [c], threshold: 0, period: "annual" });
    const [d, n] = totals(ctx, setup, osc), label = engine.DISPLAY[c];
    rows.push({ series: "Borexino measured", x: label, y: value / predicted, yerr: Math.hypot(stat, 0.5 * (up + down)) / predicted });
    rows.push({ series: "B16-GS98 prediction", x: label, y: 1, yerr: perr / predicted });
    rows.push({ series: "SNUfish (B16-GS98, NuFIT 6.0)", x: label, y: 0.5 * (d + n) * k / predicted });
  }
  return {
    title: "Borexino table II: rates over the B16-GS98 prediction",
    source: "Borexino, arXiv:1707.09279, table II", url: ARXIV("1707.09279"),
    caption: "The measured pp, ⁷Be and pep interaction rates (stat ⊕ syst, the asymmetric systematic averaged) and SNUfish's "
           + "prediction, each over Borexino's B16-GS98 prediction (its band: the solar-model error). pep: the HZ result.",
    columns: table(rows), xLabel: "Component", yLabel: "Rate ÷ B16-GS98 prediction",
    points: ["Borexino measured", "B16-GS98 prediction", "SNUfish (B16-GS98, NuFIT 6.0)"], horizontal: 1,
  };
}

const FIGURES = { sk49: (ctx, c) => superK(ctx, c, false), sk52: (ctx, c) => superK(ctx, c, true), juno3: junoProbabilities,
                  juno7: junoAsymmetry, sno10: sno, bx2: borexino };

export async function officialFigure(check, ctx) {
  const make = check && FIGURES[check.figure];
  if (!make) return null;
  await ctx.tables.ensure([`day_${ctx.setup.solar_model}`, "day_b16_gs98", `night_${ctx.setup.earth_model}`]);
  return { id: check.figure, ...make(ctx, check) };
}
