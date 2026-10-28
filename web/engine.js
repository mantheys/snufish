// SNUfish engine for the web page: a port of src/snufish/engine.py (same
// functions, same order of operations), checked against it to ~1e-9 by
// web/test/engine.test.mjs on reference results written by the Python engine.
//
// Rates are interactions per kton-year in true neutrino energy. Probabilities
// come from the tables of `snufish export-app` (TableProbabilities). Sampled
// uncertainties (oscillation parameters, fluxes with their correlations,
// statistics) are standard deviations; model choices (cross-section model, ES
// radiative corrections, Earth model, solar model) are ranges, never folded
// into a sigma.

export const PARAMETERS = ["sin2_theta12", "sin2_theta13", "sin2_theta23", "delta_cp_deg", "dm2_21_eV2", "dm2_31_eV2"];
export const DISPLAY = { pp: "pp", pep: "pep", hep: "hep", Be7: "7Be", B8: "8B", N13: "13N", O15: "15O", F17: "17F" };
export const QUANTITIES = ["rate", "adn"];
export const PERIODS = ["day", "night", "annual"];

// ------------------------------------------------------------------ numerics

export function interp(x, xp, fp, left = fp[0], right = fp[fp.length - 1]) {
  // numpy.interp for one x (xp increasing)
  const n = xp.length;
  if (x < xp[0]) return left;
  if (x > xp[n - 1]) return right;
  if (n === 1) return fp[0];
  let lo = 0, hi = n - 1;
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (xp[mid] <= x) lo = mid; else hi = mid; }
  if (x === xp[hi]) return fp[hi];
  return fp[lo] + (fp[hi] - fp[lo]) * (x - xp[lo]) / (xp[hi] - xp[lo]);
}

function trapezoid(y, x) {
  let s = 0;
  for (let i = 1; i < x.length; i++) s += 0.5 * (y[i] + y[i - 1]) * (x[i] - x[i - 1]);
  return s;
}

const sum = (a) => a.reduce((s, v) => s + v, 0);

function std(values) { // ddof = 1
  const m = sum(values) / values.length;
  return Math.sqrt(values.reduce((s, v) => s + (v - m) ** 2, 0) / (values.length - 1));
}

export function percentile(values, q) { // numpy's default (linear) method
  const s = Float64Array.from(values).sort();
  const pos = (q / 100) * (s.length - 1), lo = Math.floor(pos), hi = Math.ceil(pos);
  return s[lo] + (s[hi] - s[lo]) * (pos - lo);
}

// Seeded generator (mulberry32) with Box-Muller normals. Not numpy's stream:
// the cross-check passes the Python draws in explicitly.
export class Rng {
  constructor(seed = 1) { this.state = seed >>> 0; this.spare = null; }
  uniform() { // in (0, 1)
    let t = (this.state = (this.state + 0x6d2b79f5) >>> 0);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return (((t ^ (t >>> 14)) >>> 0) + 0.5) / 4294967296;
  }
  normal() {
    if (this.spare !== null) { const v = this.spare; this.spare = null; return v; }
    const u = this.uniform(), v = this.uniform(), r = Math.sqrt(-2 * Math.log(u));
    this.spare = r * Math.sin(2 * Math.PI * v);
    return r * Math.cos(2 * Math.PI * v);
  }
  normals(n) { return Array.from({ length: n }, () => this.normal()); }
}

function cholesky(a) {
  const n = a.length, l = a.map(() => new Array(n).fill(0));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j <= i; j++) {
      let s = a[i][j];
      for (let k = 0; k < j; k++) s -= l[i][k] * l[j][k];
      if (i === j) {
        if (s <= 0) throw new Error("covariance matrix is not positive definite");
        l[i][i] = Math.sqrt(s);
      } else l[i][j] = s / l[j][j];
    }
  }
  return l;
}

// ------------------------------------------------------------------ inputs

export class Inputs {
  constructor(data) {
    this.data = data;
    this.components = {};
    for (const [name, info] of Object.entries(data.components)) {
      if (info.lines) {
        this.components[name] = { kind: "line", energy: info.lines.map((l) => l[0]), weight: info.lines.map((l) => l[1]) };
      } else {
        const keep = info.energy.map((e) => e > 0); // tables start at E = 0, where the shape vanishes
        this.components[name] = { kind: "continuum", energy: info.energy.filter((_, i) => keep[i]),
                                  weight: info.shape.filter((_, i) => keep[i]) };
      }
    }
  }
  flux(solarModel, component, b8Flux = "model") {
    if (component === "B8" && b8Flux === "sno_nc") return this.data.b8_measured.flux;
    return this.data.solar_models[solarModel].fluxes[component];
  }
  xsecModels(channel) { return Object.keys(this.data.xsec[channel] || { default: null }); }
}

// ------------------------------------------------------------------ parameters

export function parameters(inputs, setName = null, custom = {}) {
  const registry = inputs.data.parameter_sets, out = {};
  const take = (block) => { for (const [k, v] of Object.entries(block)) if (v && typeof v === "object" && "value" in v) out[k] = { value: v.value, error: [...v.error] }; };
  take(registry.defaults);
  if (setName !== null) take(registry.sets[setName]);
  for (const [k, v] of Object.entries(custom || {})) out[k] = typeof v === "object" ? { value: v.value, error: [...v.error] } : { value: v, error: [0, 0] };
  return out;
}

export function oscillation(params) {
  return Object.fromEntries(PARAMETERS.map((k) => [k, params[k].value]));
}

export function ue2(osc) { // |U_ei|^2, i = 1, 2, 3
  const s12 = osc.sin2_theta12, s13 = osc.sin2_theta13;
  return [(1 - s12) * (1 - s13), s12 * (1 - s13), s13];
}

export function sampleOscillation(params, rng, n) {
  const draws = {};
  for (const k of PARAMETERS) {
    const { value, error: [minus, plus] } = params[k];
    draws[k] = rng.normals(n).map((z) => value + (z < 0 ? z * minus : z * plus));
  }
  return Array.from({ length: n }, (_, i) => Object.fromEntries(PARAMETERS.map((k) => [k, draws[k][i]])));
}

export function sampleFluxes(inputs, rng, solarModel, components, n, b8Flux = "model") {
  // [n][components] flux multipliers with the model's correlations; null if the model has no errors
  const model = inputs.data.solar_models[solarModel], errors = model.flux_uncertainty;
  const out = Array.from({ length: n }, () => components.map(() => 1));
  const sampled = components.filter((c) => !(c === "B8" && b8Flux === "sno_nc"));
  if (sampled.length) {
    if (!errors) return null;
    const order = inputs.data.component_order, index = sampled.map((c) => order.indexOf(c));
    const corr = model.flux_correlation || order.map((_, i) => order.map((__, j) => (i === j ? 1 : 0)));
    const sigma = sampled.map((c) => errors[c]);
    const cov = index.map((a, i) => index.map((b, j) => corr[a][b] * sigma[i] * sigma[j]));
    const l = cholesky(cov);
    for (let d = 0; d < n; d++) {
      const z = rng.normals(sampled.length);
      sampled.forEach((c, i) => { let x = 0; for (let k = 0; k <= i; k++) x += l[i][k] * z[k]; out[d][components.indexOf(c)] = 1 + x; });
    }
  }
  if (components.includes("B8") && b8Flux === "sno_nc") {
    const k = components.indexOf("B8"), e = inputs.data.b8_measured.error;
    for (let d = 0; d < n; d++) out[d][k] = 1 + e * rng.normal();
  }
  return out;
}

// ------------------------------------------------------------------ setup and checks

export const DEFAULT_SETUP = {
  solar_model: "b23_gs98", components: ["B8"], b8_flux: "model", earth_model: "prem_full", site: "Kamioka",
  detector: "water", channel: "es", xsec_model: "default", es_model: "tree", recoil_threshold: 0.0,
  period: "day", exposure: null, profile_model: null,
};

export function makeSetup(changes = {}) { return { ...DEFAULT_SETUP, ...changes }; }

export function check(inputs, setup, quantity = "rate") {
  const allowed = (what, value, options) => {
    if (!options.includes(value)) throw new Error(`${what} '${value}' is not available; choose one of: ${options.join(", ")}`);
  };
  const d = inputs.data;
  allowed("quantity", quantity, QUANTITIES);
  allowed("period", setup.period, PERIODS);
  allowed("solar model", setup.solar_model, Object.keys(d.solar_models));
  if (!setup.components.length) throw new Error("select at least one flux component");
  for (const c of setup.components) allowed("flux component", c, Object.keys(inputs.components));
  allowed("8B flux", setup.b8_flux, ["model", "sno_nc"]);
  allowed("detector", setup.detector, Object.keys(d.detectors));
  const channels = Object.keys(d.detectors[setup.detector].channels);
  if (!channels.includes(setup.channel)) throw new Error(`channel '${setup.channel}' is not available in ${setup.detector}; choose one of: ${channels.join(", ")}`);
  if (setup.channel === "es") allowed("ES model", setup.es_model, ["tree", "snowglobes"]);
  else allowed(`cross-section model of ${setup.channel}`, setup.xsec_model, inputs.xsecModels(setup.channel));
  if (!(setup.recoil_threshold >= 0)) throw new Error("the recoil threshold must be >= 0");
  allowed("site", setup.site, Object.keys(d.sites));
  allowed("Earth model", setup.earth_model, d.earth_models);
  if (setup.exposure !== null && !(setup.exposure > 0)) throw new Error("the exposure must be > 0 (or none)");
}

export const needsNight = (quantity, period) => quantity === "adn" || period !== "day";

// ------------------------------------------------------------------ cross sections and rates

export function esAbove(E, flavour, c, tMin) {
  // tree-level nu-e cross section (cm^2 per electron) integrated over T from tMin to T_max
  const me = c.m_e_MeV, sw2 = c.sin2_theta_W, G = c["G_F_GeV-2"] * 1e-6, hbarc2 = (c.hbarc_MeV_fm * 1e-13) ** 2;
  const g1 = (flavour === "nue" ? 0.5 : -0.5) + sw2, g2 = sw2;
  const tMax = 2 * E ** 2 / (me + 2 * E), lo = Math.min(tMin, tMax);
  const primitive = (T) => g1 ** 2 * T - g2 ** 2 * (E / 3) * (1 - T / E) ** 3 - g1 * g2 * me * T ** 2 / (2 * E ** 2);
  return 2 * G ** 2 * me / Math.PI * (primitive(tMax) - primitive(lo)) * hbarc2;
}

export function crossSections(inputs, setup, energy) {
  const d = inputs.data, det = d.detectors[setup.detector];
  const targets = det.targets[det.channels[setup.channel]];
  if (setup.channel === "es") {
    const sigma = ["nue", "numu"].map((fl) => energy.map((e) => {
      let s = esAbove(e, fl, d.constants, setup.recoil_threshold);
      if (setup.es_model === "snowglobes") { const r = d.es_radiative_ratio[fl]; s *= interp(e, r.energy, r.ratio, 1, 1); }
      return s;
    }));
    return [sigma[0], sigma[1], targets];
  }
  const table = d.xsec[setup.channel][setup.xsec_model], threshold = d.xsec_thresholds_MeV[setup.channel] || 0;
  const sigmaE = energy.map((e) => (e < threshold ? 0 : interp(e, table.energy, table.sigma, 0, 0)));
  return [sigmaE, energy.map(() => 0), targets];
}

export function componentRates(inputs, probabilities, setup, osc, night = true) {
  // {component: {kind, energy, day, night}} per kton-year: per MeV for a continuum, per line for lines
  const U2 = ue2(osc), seconds = inputs.data.seconds_per_year;
  const nightTable = night ? probabilities.night(osc, setup.earth_model, setup.site) : null;
  const out = {};
  for (const c of setup.components) {
    const { kind, energy, weight } = inputs.components[c];
    const F = probabilities.day(osc, setup.profile_model || setup.solar_model, c, energy);
    const [sigmaE, sigmaX, targets] = crossSections(inputs, setup, energy);
    const flux = inputs.flux(setup.solar_model, c, setup.b8_flux);
    const rate = (pee) => pee.map((p, i) => targets * flux * seconds * weight[i] * (p * sigmaE[i] + (1 - p) * sigmaX[i]));
    const entry = { kind, energy, day: rate(F.map((f) => f[0] * U2[0] + f[1] * U2[1] + f[2] * U2[2])), night: null };
    if (night) {
      const [nE, nP] = nightTable;
      const P = [0, 1, 2].map((i) => { const col = nP.map((row) => row[i]); return energy.map((e) => interp(e, nE, col, U2[i])); });
      entry.night = rate(F.map((f, k) => f[0] * P[0][k] + f[1] * P[1][k] + f[2] * P[2][k]));
    }
    out[c] = entry;
  }
  return out;
}

export function totals(rates) {
  const total = (r, values) => (values === null ? NaN : r.kind === "continuum" ? trapezoid(values, r.energy) : sum(values));
  return Object.fromEntries(Object.entries(rates).map(([c, r]) => [c, { day: total(r, r.day), night: total(r, r.night) }]));
}

export function combine(per, components, multipliers = null) {
  let day = 0, night = 0;
  components.forEach((c, k) => { const m = multipliers ? multipliers[k] : 1; day += m * per[c].day; night += m * per[c].night; });
  return [day, night];
}

export function quantityValue(quantity, period, day, night) {
  if (quantity === "adn") return 2 * (night - day) / (night + day);
  return { day, night, annual: 0.5 * (day + night) }[period];
}

export function statisticalSigma(quantity, period, day, night, exposure) {
  // Poisson error for `exposure` kton-years, half of it by night (no backgrounds)
  if (!exposure) return null;
  if (quantity === "adn") {
    const D = day * exposure / 2, N = night * exposure / 2, S = D + N;
    return Math.sqrt((4 * D / S ** 2) ** 2 * N + (4 * N / S ** 2) ** 2 * D);
  }
  const rate = quantityValue(quantity, period, day, night), live = period === "annual" ? exposure : exposure / 2;
  return Math.sqrt(rate * live) / live;
}

export function binned(rates, edges) {
  // {component: {day, night}} of rates per kton-year in each energy bin
  const counts = (r, values) => {
    if (values === null) return null;
    const out = new Array(edges.length - 1).fill(0);
    if (r.kind === "line") {
      r.energy.forEach((e, i) => {
        for (let b = 0; b < out.length; b++) {
          if (e >= edges[b] && (e < edges[b + 1] || (b === out.length - 1 && e === edges[b + 1]))) { out[b] += values[i]; break; }
        }
      });
      return out;
    }
    const cumulative = [0];
    for (let i = 1; i < r.energy.length; i++) cumulative.push(cumulative[i - 1] + 0.5 * (values[i] + values[i - 1]) * (r.energy[i] - r.energy[i - 1]));
    const at = edges.map((x) => interp(x, r.energy, cumulative));
    return out.map((_, b) => at[b + 1] - at[b]);
  };
  return Object.fromEntries(Object.entries(rates).map(([c, r]) => [c, { day: counts(r, r.day), night: counts(r, r.night) }]));
}

export function energyEdges(inputs, components, perDecade = 16) {
  const lows = [], highs = [];
  for (const c of components) { const e = inputs.components[c].energy; lows.push(Math.min(...e)); highs.push(Math.max(...e)); }
  const lo = Math.log10(Math.max(Math.min(...lows) * 0.9, 0.05)), hi = Math.log10(Math.max(...highs) * 1.05);
  const n = Math.max(Math.ceil((hi - lo) * perDecade), 4);
  return Array.from({ length: n + 1 }, (_, i) => 10 ** (lo + (hi - lo) * i / n));
}

// ------------------------------------------------------------------ budget

export const RANGE_LABELS = { xsec_model: "cross-section model", es_model: "ES radiative corrections",
                              earth_model: "Earth model", solar_model: "solar model" };

export function alternatives(inputs, setup, choice) {
  if (choice === "xsec_model") return setup.channel !== "es" ? inputs.xsecModels(setup.channel) : [];
  if (choice === "es_model") return setup.channel === "es" ? ["tree", "snowglobes"] : [];
  if (choice === "earth_model") return [...inputs.data.earth_models];
  if (choice === "solar_model") return Object.keys(inputs.data.solar_models);
  throw new Error(choice);
}

export function fluxLabel(setup) {
  const measured = setup.b8_flux === "sno_nc" && setup.components.includes("B8");
  if (setup.components.length === 1) return `${DISPLAY[setup.components[0]]} flux (${measured ? "SNO NC" : "solar model"})`;
  return "solar fluxes" + (measured ? " (8B from SNO NC)" : "");
}

const relative = (error, central) => (central !== 0 ? error / Math.abs(central) : NaN);

export function draws(inputs, setup, params, n, seed) {
  // {rng, osc, flux}: the same for a budget and the spectra of one seed
  const rng = new Rng(seed);
  const osc = sampleOscillation(params, rng, n);
  return { rng, osc, flux: sampleFluxes(inputs, rng, setup.solar_model, setup.components, n, setup.b8_flux) };
}

export function budget(inputs, probabilities, setup, params, quantity = "rate",
                       { n = 400, seed = 1, ranges = ["xsec_model", "es_model", "earth_model", "solar_model"],
                         solarRange = "full", given = null } = {}) {
  // {rows, samples}: rows {Source, Kind, Central, Sigma, Relative, Low, High}; `given` = {osc, flux, statNoise?}
  check(inputs, setup, quantity);
  const night = needsNight(quantity, setup.period), comps = setup.components;
  const valueOf = (s, osc = oscillation(params), m = null) =>
    quantityValue(quantity, s.period, ...combine(totals(componentRates(inputs, probabilities, s, osc, night)), comps, m));
  const d = given || draws(inputs, setup, params, n, seed);
  const nominal = totals(componentRates(inputs, probabilities, setup, oscillation(params), night));
  const [day0, night0] = combine(nominal, comps);
  const central = quantityValue(quantity, setup.period, day0, night0);
  const rows = [], samples = {};
  const sampled = (source, values) => {
    const sigma = std(values);
    rows.push({ Source: source, Kind: "sampled", Central: central, Sigma: sigma, Relative: relative(sigma, central), Low: NaN, High: NaN });
    samples[source] = values;
  };
  const perDraw = d.osc.map((o) => totals(componentRates(inputs, probabilities, setup, o, night)));
  sampled("oscillation parameters", perDraw.map((p) => quantityValue(quantity, setup.period, ...combine(p, comps))));
  let total = perDraw.map((p, i) => quantityValue(quantity, setup.period, ...combine(p, comps, d.flux ? d.flux[i] : null)));
  if (d.flux && !(quantity === "adn" && comps.length === 1)) // one flux cancels in a ratio
    sampled(fluxLabel(setup), d.flux.map((m) => quantityValue(quantity, setup.period, ...combine(nominal, comps, m))));
  const stat = statisticalSigma(quantity, setup.period, day0, night0, setup.exposure);
  if (stat !== null) {
    const noise = d.statNoise || [d.rng.normals(total.length), d.rng.normals(total.length)];
    sampled(`statistics (${setup.exposure} kt yr)`, noise[0].map((z) => central + stat * z));
    total = total.map((t, i) => t + stat * noise[1][i]);
  }
  sampled("total sampled", total);
  for (const choice of ranges) {
    let options = alternatives(inputs, setup, choice);
    if (choice === "earth_model" && !night) options = [];
    if (options.length < 2) continue;
    const fixed = choice === "solar_model" && solarRange === "fluxes" ? { profile_model: setup.solar_model } : {};
    const values = options.map((o) => valueOf({ ...setup, [choice]: o, ...fixed }));
    const low = Math.min(...values), high = Math.max(...values);
    if (high - low <= 1e-12 * Math.abs(central)) continue; // e.g. the solar model when the only flux is measured
    const label = choice === "xsec_model" && setup.channel === "cc_nue_ar40" ? "40Ar nuclear model" : RANGE_LABELS[choice];
    rows.push({ Source: label, Kind: "model range", Central: central, Sigma: NaN,
                Relative: relative(Math.max(high - central, central - low), central), Low: low, High: high });
  }
  return { rows, samples };
}

export function spectra(inputs, probabilities, setup, params, { edges = null, n = 400, seed = 1, night = true, given = null } = {}) {
  // binned rates per kton-year: central per component and in total, and the totals of every draw
  check(inputs, setup);
  edges = edges || energyEdges(inputs, setup.components);
  const comps = setup.components, d = given || draws(inputs, setup, params, n, seed);
  const total = (per, m = null) => {
    const day = new Array(edges.length - 1).fill(0), nite = night ? new Array(edges.length - 1).fill(0) : null;
    comps.forEach((c, k) => { const f = m ? m[k] : 1; per[c].day.forEach((v, b) => { day[b] += f * v; }); if (night) per[c].night.forEach((v, b) => { nite[b] += f * v; }); });
    return [day, nite];
  };
  const nominal = binned(componentRates(inputs, probabilities, setup, oscillation(params), night), edges);
  const each = d.osc.map((o, i) => total(binned(componentRates(inputs, probabilities, setup, o, night), edges), d.flux ? d.flux[i] : null));
  const [day, nite] = total(nominal);
  return { edges, components: nominal, day, night: nite, draws_day: each.map((x) => x[0]), draws_night: night ? each.map((x) => x[1]) : null };
}

// ------------------------------------------------------------------ tables

function cell(axis, x) {
  x = Math.min(Math.max(x, axis[0]), axis[axis.length - 1]);
  let i = 0;
  while (i < axis.length - 2 && axis[i + 1] <= x) i++;
  return [i, (x - axis[i]) / (axis[i + 1] - axis[i])];
}

export class TableProbabilities {
  // Tables of `snufish export-app` (JSON index + float32 binary); `loader(name)` -> {meta, buffer}
  constructor(loader) { this.loader = loader; this.tables = {}; this.clamped = 0; }

  async ensure(names) {
    await Promise.all(names.filter((n) => !this.tables[n]).map(async (name) => {
      const { meta, buffer } = await this.loader(name);
      const t = { ...meta.values };
      for (const [key, entry] of Object.entries(meta.arrays)) {
        const size = entry.shape.reduce((a, b) => a * b, 1);
        t[key] = { data: new Float32Array(buffer, entry.offset, size), shape: entry.shape };
      }
      this.tables[name] = t;
    }));
  }

  has(name) { return Boolean(this.tables[name]); }

  get(name) {
    const t = this.tables[name];
    if (!t) throw new Error(`table ${name} not loaded`);
    return t;
  }

  point(t, osc) {
    const s12 = osc.sin2_theta12, dm = osc.dm2_21_eV2 * 1e5;
    if (!(t.s12[0] <= s12 && s12 <= t.s12[t.s12.length - 1] && t.dm21[0] <= dm && dm <= t.dm21[t.dm21.length - 1])) this.clamped++;
    return [cell(t.s12, s12), cell(t.dm21, dm)];
  }

  // bilinear interpolation of the trailing block [rest] of a [s12][dm21][rest] array (at `base` + offset)
  blend(array, base, nd, rest, [[i, tx], [j, ty]]) {
    const at = (a, b) => base + (a * nd + b) * rest, d = array.data, out = new Float64Array(rest);
    const w = [[at(i, j), (1 - tx) * (1 - ty)], [at(i + 1, j), tx * (1 - ty)], [at(i, j + 1), (1 - tx) * ty], [at(i + 1, j + 1), tx * ty]];
    for (let k = 0; k < rest; k++) out[k] = w[0][1] * d[w[0][0] + k] + w[1][1] * d[w[1][0] + k] + w[2][1] * d[w[2][0] + k] + w[3][1] * d[w[3][0] + k];
    return out;
  }

  day(osc, solarModel, component, energies) {
    const t = this.get(`day_${solarModel}`), e = t[`energy_${component}`], F = t[`F_${component}`];
    const F12 = this.blend(F, 0, t.dm21.length, e.length * 2, this.point(t, osc));
    const loge = e.map(Math.log), f1 = e.map((_, k) => F12[2 * k]), f2 = e.map((_, k) => F12[2 * k + 1]);
    return energies.map((x) => {
      const l = Math.log(Math.min(Math.max(x, e[0]), e[e.length - 1]));
      const a = interp(l, loge, f1), b = interp(l, loge, f2);
      return [a, b, 1 - a - b];
    });
  }

  night(osc, earthModel, site) {
    const t = this.get(`night_${earthModel}`), s = t.sites.indexOf(site), P = t.P;
    const [, ns, nd, ne] = P.shape, rest = ne * 3;
    const flat = this.blend(P, s * ns * nd * rest, nd, rest, this.point(t, osc));
    return [t.energy, Array.from({ length: ne }, (_, k) => [flat[3 * k], flat[3 * k + 1], flat[3 * k + 2]])];
  }
}
