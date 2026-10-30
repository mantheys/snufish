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
export const QUANTITIES = ["rate", "adn", "ratio"]; // ratio: rate / the rate without oscillations
export const isNC = (setup) => setup.channel.startsWith("nc_");
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
  // selectable models of a channel ("#" marks internal tables, e.g. B(GT)-shifted ones)
  xsecModels(channel) { return Object.keys(this.data.xsec[channel] || { default: null }).filter((m) => !m.includes("#")); }
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
  detector: "water", channel: "es", xsec_model: "default", es_model: "bks", period: "day",
  // detector response in observed energy (ES: electron kinetic energy T; CC: visible energy E_nu - Q)
  threshold: 0.0, resolution_a: 0.0, resolution_b: 0.0, efficiency: 1.0, efficiency_e50: 0.0, efficiency_width: 0.5,
  // Super-K style resolution [c0, c1, c2]: sigma = c0 + c1 sqrt(E) + c2 E, E the total electron energy for ES
  resolution_poly: [], energy_scale: 1.0, resolution_scale: 1.0,
  // detector uncertainties (fractions, 1 sigma), sampled in the budget: energy scale, sigma, rate normalisation
  energy_scale_error: 0.0, resolution_error: 0.0, normalisation_error: 0.0,
  // imported response, {id, x, y, matrix, true_axis}: an efficiency curve (x energies, y efficiencies) in place of
  // efficiency and its turn-on; a smearing matrix (x true edges, y observed edges, matrix [true][observed]) in place
  // of the resolution; compared by id
  efficiency_table: null, smearing_table: null,
  exposure: null, profile_model: null, orbit: false,
};

export function makeSetup(changes = {}) { return { ...DEFAULT_SETUP, ...changes }; }

export const OBSERVED_MIN = 0.01, OBSERVED_MAX = 25.0; // MeV; a first bin [0, 0.01] collects everything below
const PER_DECADE = 16, FINE = 4;                        // display bins per decade, fine bins per display bin

export function check(inputs, setup, quantity = "rate") {
  const allowed = (what, value, options) => {
    if (!options.includes(value)) throw new Error(`${what} '${value}' is not available; choose one of: ${options.join(", ")}`);
  };
  const within = (what, value, low, high) => {
    if (!(value >= low && value <= high)) throw new Error(`${what} must be between ${low} and ${high} (got ${value})`);
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
  if (setup.channel === "es") allowed("ES model", setup.es_model, ES_MODELS);
  else allowed(`cross-section model of ${setup.channel}`, setup.xsec_model, inputs.xsecModels(setup.channel));
  within("the threshold (MeV)", setup.threshold, 0, OBSERVED_MAX);
  within("the resolution a (MeV^1/2)", setup.resolution_a, 0, 2);
  within("the resolution b", setup.resolution_b, 0, 1);
  within("the efficiency", setup.efficiency, 0, 1);
  within("the efficiency turn-on (MeV)", setup.efficiency_e50, 0, OBSERVED_MAX);
  within("the turn-on width (MeV)", setup.efficiency_width, 1e-3, 10);
  if (![0, 3].includes(setup.resolution_poly.length)) throw new Error("resolution_poly takes three coefficients (c0, c1, c2)");
  within("the energy scale", setup.energy_scale, 0.5, 1.5);
  within("the resolution scale", setup.resolution_scale, 0, 3);
  within("the energy-scale uncertainty", setup.energy_scale_error, 0, 0.2);
  within("the resolution uncertainty", setup.resolution_error, 0, 1);
  within("the normalisation uncertainty", setup.normalisation_error, 0, 1);
  for (const [name, t] of [["efficiency", setup.efficiency_table], ["smearing", setup.smearing_table]])
    if (t && (t.x.length < 2 || t.x.some((v, i) => i > 0 && v <= t.x[i - 1]))) throw new Error(`the imported ${name} needs increasing energies`);
  const t = setup.smearing_table;
  if (t) {
    if (t.matrix.length !== t.x.length - 1 || t.matrix.some((row) => row.length !== t.y.length - 1))
      throw new Error("the imported smearing matrix needs one row per true bin and one column per observed bin");
    if (t.true_axis === "neutrino" && (setup.channel === "es" || isNC(setup))) throw new Error("a smearing matrix in neutrino energy applies to CC channels only");
  }
  allowed("site", setup.site, Object.keys(d.sites));
  allowed("Earth model", setup.earth_model, d.earth_models);
  if (setup.orbit) {
    if (quantity === "ratio") throw new Error("a rate over the rate without oscillations does not depend on the Earth-Sun distance; leave orbit off");
    if (d.sites[setup.site].orbit_day === undefined) throw new Error("these inputs have no orbital factors: rebuild them (snufish export-app --inputs-only)");
  }
  if (setup.exposure !== null && !(setup.exposure > 0)) throw new Error("the exposure must be > 0 (or none)");
}

export const needsNight = (quantity, period) => quantity === "adn" || period !== "day";

// ------------------------------------------------------------------ observed energy

function logspace(lo, hi, n) { // numpy.logspace: 10 ** (lo + i * step), the last point exactly hi
  const step = (hi - lo) / (n - 1);
  return Array.from({ length: n }, (_, i) => 10 ** (i === n - 1 ? hi : lo + i * step));
}

export function observedEdges(threshold = 0) {
  // [fine, display] bin edges: 0, then log-spaced from 0.01 to 25 MeV; the threshold is a fine edge
  const n = Math.round(Math.log10(OBSERVED_MAX / OBSERVED_MIN) * PER_DECADE);
  const lo = Math.log10(OBSERVED_MIN), hi = Math.log10(OBSERVED_MAX);
  const display = [0, ...logspace(lo, hi, n + 1)];
  let fine = [0, ...logspace(lo, hi, n * FINE + 1)];
  if (threshold > 0 && !fine.some((e) => Math.abs(e - threshold) <= 1e-9)) fine = [...fine, threshold].sort((x, y) => x - y);
  return [fine, display];
}

export const observable = (channel) => (channel.startsWith("nc_") ? "Neutron-capture gamma energy (MeV)"
  : channel === "es" ? "Electron kinetic energy T (MeV)" : "Visible energy E_nu - Q (MeV)");

export function erf(x) {
  // series for |x| < 3, continued fraction for erfc beyond: ~1e-15 relative
  const ax = Math.abs(x);
  if (ax < 3) {
    let term = ax, total = ax;
    for (let n = 1; n < 200 && Math.abs(term) > 1e-17 * Math.abs(total); n++) { term *= -ax * ax / n; total += term / (2 * n + 1); }
    return Math.sign(x) * 2 / Math.sqrt(Math.PI) * total;
  }
  let f = ax, c = ax, dd = 0; // modified Lentz for erfc(x) = exp(-x^2)/sqrt(pi) / (x + 1/2/(x + 1/(x + 3/2/(x + ...))))
  for (let n = 1; n < 300; n++) {
    const an = n / 2;
    dd = ax + an * dd; dd = 1 / dd; c = ax + an / c;
    const delta = c * dd; f *= delta;
    if (Math.abs(delta - 1) < 1e-16) break;
  }
  return Math.sign(x) * (1 - Math.exp(-ax * ax) / Math.sqrt(Math.PI) / f);
}

export function esAbove(E, flavour, c, tMin) {
  // tree-level nu-e cross section (cm^2 per electron) integrated over T from tMin to T_max
  const me = c.m_e_MeV, sw2 = c.sin2_theta_W, G = c["G_F_GeV-2"] * 1e-6, hbarc2 = (c.hbarc_MeV_fm * 1e-13) ** 2;
  const g1 = (flavour === "nue" ? 0.5 : -0.5) + sw2, g2 = sw2;
  const tMax = 2 * E ** 2 / (me + 2 * E), lo = Math.min(tMin, tMax);
  const primitive = (T) => g1 ** 2 * T - g2 ** 2 * (E / 3) * (1 - T / E) ** 3 - g1 * g2 * me * T ** 2 / (2 * E ** 2);
  return 2 * G ** 2 * me / Math.PI * (primitive(tMax) - primitive(lo)) * hbarc2;
}

export function bksRatio(d, flavour, e, edges) {
  // ratio of the radiatively corrected (BKS 1995) to the tree-level sigma(E; T > t), linear in ln E and t / T_max
  const t = d.es_bks, grid = t.energy.map(Math.log), ratio = t[flavour], me = d.constants.m_e_MeV;
  const x = Math.min(Math.max(Math.log(e), grid[0]), grid[grid.length - 1]);
  let i = 0;
  while (i + 1 < grid.length && grid[i + 1] <= x) i++;
  i = Math.min(i, grid.length - 2);
  const w = (x - grid[i]) / (grid[i + 1] - grid[i]), tMax = 2 * e ** 2 / (me + 2 * e);
  return edges.map((edge) => { const u = edge / tMax; return (1 - w) * interp(u, t.fraction, ratio[i]) + w * interp(u, t.fraction, ratio[i + 1]); });
}

function quadrature(kind, energy, weight) {
  if (kind === "line") return weight;
  const q = energy.map(() => 0);
  for (let k = 0; k + 1 < energy.length; k++) { const h = 0.5 * (energy[k + 1] - energy[k]); q[k] += h; q[k + 1] += h; }
  return q.map((v, k) => v * weight[k]);
}

const targetsOf = (inputs, setup) => { const det = inputs.data.detectors[setup.detector]; return det.targets[det.channels[setup.channel]]; };

function kernels(inputs, setup, component, edges) {
  // cached, oscillation-independent: ES [E][bin] cross sections into each recoil bin (nu_e, nu_x); CC sigma(E)
  const key = [component, setup.detector, setup.channel, setup.es_model, setup.xsec_model, setup.threshold].join("|");
  inputs.kernelCache ||= new Map();
  if (!inputs.kernelCache.has(key)) {
    const { energy } = inputs.components[component], d = inputs.data;
    let value;
    if (setup.channel === "es") {
      value = ["nue", "numu"].map((fl) => energy.map((e) => {
        let above = edges.map((t) => esAbove(e, fl, d.constants, t));
        if (setup.es_model === "bks") { const r = bksRatio(d, fl, e, edges); above = above.map((a, j) => a * r[j]); }
        let ratio = 1;
        if (setup.es_model === "snowglobes") { // its tables start at 0.5 MeV: BKS below
          const r = d.es_radiative_ratio[fl];
          if (e < r.energy[0]) { const b = bksRatio(d, fl, e, edges); above = above.map((a, j) => a * b[j]); }
          else ratio = interp(e, r.energy, r.ratio, 1, 1);
        }
        return Float64Array.from({ length: edges.length - 1 }, (_, j) => (above[j] - above[j + 1]) * ratio);
      }));
    } else {
      const table = d.xsec[setup.channel][setup.xsec_model], threshold = d.xsec_thresholds_MeV[setup.channel] || 0;
      value = energy.map((e) => (e < threshold ? 0 : interp(e, table.energy, table.sigma, 0, 0)));
    }
    inputs.kernelCache.set(key, value);
  }
  return inputs.kernelCache.get(key);
}

export function electronSmearing(inputs, channel, xsecModel, b, step = 0.1, top = 25.0) {
  // smearing matrix in neutrino energy for the electron of a CC event alone, its de-excitation gammas undetected:
  // each nuclear level takes its share of the cross section to T = E_nu - Q - E_level, smeared by a Gaussian of
  // sigma = b T (b = 0: none); shares from the model's measured levels (their 1-sigma tables: sigma is linear in
  // each strength), the rest of the cross section (unmeasured levels) at the highest
  const table = inputs.data.xsec[channel], { energy, sigma: total } = table[xsecModel];
  const levels = inputs.data.xsec_levels[channel][xsecModel], q = inputs.data.visible_offset_MeV[channel];
  const n = Math.round(top / step), edges = Array.from({ length: n + 1 }, (_, i) => +(i * step).toFixed(10));
  const centres = edges.slice(0, -1).map((e, i) => 0.5 * (e + edges[i + 1]));
  const sigma = centres.map((c) => interp(c, energy, total, 0));
  const shares = levels.map((l) => {
    const t = table[l.name], part = energy.map((e, k) => (interp(e, t.energy, t.sigma) - total[k]) * l.strength / l.error);
    return centres.map((c, i) => (sigma[i] > 0 ? Math.max(interp(c, energy, part, 0) / sigma[i], 0) : 0));
  });
  const last = shares[shares.length - 1];
  centres.forEach((_, i) => { if (sigma[i] > 0) last[i] += Math.max(1 - shares.reduce((s, x) => s + x[i], 0), 0); });
  const cdf = (z) => 0.5 * (1 + erf(z / Math.SQRT2));
  const matrix = centres.map(() => new Array(n).fill(0));
  levels.forEach((level, j) => centres.forEach((c, i) => {
    const t = c - q - level.level_MeV, w = shares[j][i];
    if (!(w > 0 && t > 0)) return;
    const row = matrix[i];
    if (b > 0) {
      const f = edges.map((e) => cdf((e - t) / (b * t)));
      for (let m = 0; m < n; m++) row[m] += w * (f[m + 1] - f[m]);
      row[0] += w * f[0]; row[n - 1] += w * (1 - f[n]);
    } else {
      let m = 0;
      while (m < n - 1 && edges[m + 1] <= t) m++;
      row[m] += w;
    }
  }));
  return { id: `electron:${channel}:${xsecModel}:${b}`, x: edges, y: edges, matrix, true_axis: "neutrino",
           name: "electron alone", summary: `electron kinetic energy alone over ${levels.length} nuclear levels, σ/T = ${+(100 * b).toFixed(3)} %` };
}

export function resolution(inputs, setup, energy) {
  // sigma (MeV) at an observed energy: sqrt((a sqrt(E))^2 + (b E)^2), or Super-K's c0 + c1 sqrt(E) + c2 E in
  // total electron energy (ES); times resolution_scale
  let sigma;
  if (setup.resolution_poly.length) {
    const [c0, c1, c2] = setup.resolution_poly, total = energy + (setup.channel === "es" ? inputs.data.constants.m_e_MeV : 0);
    sigma = Math.max(c0 + c1 * Math.sqrt(total) + c2 * total, 0);
  } else sigma = Math.hypot(setup.resolution_a * Math.sqrt(energy), setup.resolution_b * energy);
  return setup.resolution_scale * sigma;
}

const responseKey = (setup) => [setup.channel, setup.efficiency_table?.id, setup.smearing_table?.id, setup.threshold, setup.resolution_a, setup.resolution_b, setup.resolution_poly.join(","),
  setup.energy_scale, setup.resolution_scale, setup.efficiency, setup.efficiency_e50, setup.efficiency_width].join("|");

function importedRows(inputs, setup, edges) {
  // fine rows from an imported matrix: each fine bin takes the row of the imported true bin holding its centre
  // (outside: identity, null), each imported observed bin spread over the fine bins it overlaps
  const t = setup.smearing_table, n = edges.length - 1;
  const shift = t.true_axis === "neutrino" ? inputs.data.visible_offset_MeV[setup.channel] : 0;
  const trueEdges = t.x.map((x) => x - shift), obs = t.y.map((y) => setup.energy_scale * y);
  const spread = obs.slice(0, -1).map((lo, k) => {
    const hi = obs[k + 1];
    return Float64Array.from({ length: n }, (_, m) => Math.max(0, Math.min(hi, edges[m + 1]) - Math.max(lo, edges[m])) / (hi - lo));
  });
  return Array.from({ length: n }, (_, j) => {
    const c = 0.5 * (edges[j] + edges[j + 1]);
    if (!(c >= trueEdges[0] && c < trueEdges[trueEdges.length - 1])) return null;
    let i = 0;
    while (i < trueEdges.length - 2 && trueEdges[i + 1] <= c) i++;
    const row = new Float64Array(n), probs = t.matrix[i];
    probs.forEach((p, k) => { if (p) { const sp = spread[k]; for (let m = 0; m < n; m++) row[m] += p * sp[m]; } });
    return row;
  });
}

function response(inputs, setup, edges) {
  // [rows of the response matrix (null: identity), acceptance per observed bin]: energy scale, resolution,
  // efficiency, threshold; events smeared below 0 or above the last edge stay in the first or last bin
  const key = responseKey(setup);
  inputs.responseCache ||= new Map();
  if (!inputs.responseCache.has(key)) {
    const n = edges.length - 1, centres = Array.from({ length: n }, (_, j) => 0.5 * (edges[j] + edges[j + 1]));
    const scale = setup.energy_scale, cdfOf = (z) => 0.5 * (1 + erf(z / Math.SQRT2));
    const imported = setup.smearing_table ? importedRows(inputs, setup, edges) : null;
    const rows = centres.map((c, j) => {
      if (imported) return imported[j];
      const sigma = resolution(inputs, setup, c);
      if (sigma > 0) {
        const cdf = edges.map((e) => cdfOf((e - scale * c) / sigma));
        const row = Float64Array.from({ length: n }, (_, m) => cdf[m + 1] - cdf[m]);
        row[0] += cdf[0]; row[n - 1] += 1 - cdf[n];
        return row;
      }
      if (scale === 1) return null;
      const low = scale * edges[j], high = scale * edges[j + 1], row = new Float64Array(n); // spread over the scaled width
      let kept = 0;
      for (let m = 0; m < n; m++) { const o = Math.max(0, Math.min(high, edges[m + 1]) - Math.max(low, edges[m])) / (high - low); row[m] = o; kept += o; }
      row[n - 1] += 1 - kept;
      return row;
    });
    const et = setup.efficiency_table;
    const acceptance = centres.map((c, j) => {
      let a = setup.efficiency;
      if (et) a = interp(c, et.x, et.y, 0, et.y[et.y.length - 1]);
      else if (setup.efficiency_e50 > 0) a = a / (1 + Math.exp(-(c - setup.efficiency_e50) / setup.efficiency_width));
      return edges[j] >= setup.threshold - 1e-12 ? a : 0;
    });
    inputs.responseCache.set(key, [rows, acceptance]);
  }
  return inputs.responseCache.get(key);
}

export function orbital(inputs, setup) {
  // [day, night] factors of the rates: the site's mean (1 AU / R)^2 over its days and nights with setup.orbit, else [1, 1]
  if (!setup.orbit) return [1, 1];
  const site = inputs.data.sites[setup.site];
  return [site.orbit_day, site.orbit_night];
}

export function survival(inputs, probabilities, setup, osc, night = true) {
  // {component: [P_ee by day, P_ee by night or null]} at the component's energies
  const U2 = ue2(osc), nightTable = night ? probabilities.night(osc, setup.earth_model, setup.site) : null;
  const out = {};
  for (const c of setup.components) {
    const { energy } = inputs.components[c];
    const F = probabilities.day(osc, setup.profile_model || setup.solar_model, c, energy);
    let peeNight = null;
    if (night) {
      const [nE, nP] = nightTable;
      const P = [0, 1, 2].map((i) => { const col = nP.map((row) => row[i]); return energy.map((e) => interp(e, nE, col, U2[i])); });
      peeNight = F.map((f, k) => f[0] * P[0][k] + f[1] * P[1][k] + f[2] * P[2][k]);
    }
    out[c] = [F.map((f) => f[0] * U2[0] + f[1] * U2[1] + f[2] * U2[2]), peeNight];
  }
  return out;
}

function visible(inputs, setup, kind, energy, density, edges) {
  // CC: rate per fine bin of visible energy E - Q; below the first edge goes to the first bin
  const nb = edges.length - 1, fixed = (inputs.data.visible_fixed_MeV || {})[setup.channel];
  if (fixed !== undefined) { // NC: every event deposits the same energy (the neutron-capture gamma)
    let total = 0;
    if (kind === "line") density.forEach((v) => { total += v; });
    else for (let i = 1; i < energy.length; i++) total += 0.5 * (density[i] + density[i - 1]) * (energy[i] - energy[i - 1]);
    let j = 0;
    while (j + 1 < nb && edges[j + 1] <= fixed) j++;
    const out = new Float64Array(nb);
    out[j] = total;
    return out;
  }
  const offset = inputs.data.visible_offset_MeV[setup.channel];
  const shifted = edges.map((e, j) => (j === 0 ? -Infinity : j === nb ? Infinity : e + offset));
  const truth = new Float64Array(nb);
  if (kind === "line") {
    energy.forEach((e, i) => { for (let j = 0; j < nb; j++) if (e >= shifted[j] && e < shifted[j + 1]) { truth[j] += density[i]; break; } });
    return truth;
  }
  const cumulative = [0];
  for (let i = 1; i < energy.length; i++) cumulative.push(cumulative[i - 1] + 0.5 * (density[i] + density[i - 1]) * (energy[i] - energy[i - 1]));
  const at = shifted.map((x) => interp(x, energy, cumulative, 0, cumulative[cumulative.length - 1]));
  for (let j = 0; j < nb; j++) truth[j] = at[j + 1] - at[j];
  return truth;
}

export function observedRates(inputs, probabilities, setup, osc, night = true) {
  // {component: {day, night}}: interactions per kton-year in each fine bin of observed energy, after the response.
  // The reference path: componentTotals and componentSpectra give the same numbers faster.
  const [edges] = observedEdges(setup.threshold), [rows, acceptance] = response(inputs, setup, edges);
  const nb = edges.length - 1, seconds = inputs.data.seconds_per_year, targets = targetsOf(inputs, setup);
  const [gDay, gNight] = orbital(inputs, setup);
  const out = {};
  for (const [c, [peeDay, peeNight]] of Object.entries(survival(inputs, probabilities, setup, osc, night))) {
    const { kind, energy, weight } = inputs.components[c];
    const scale = targets * inputs.flux(setup.solar_model, c, setup.b8_flux) * seconds, k = kernels(inputs, setup, c, edges);
    const spectrum = (pee, g) => {
      if (pee === null) return null;
      if (isNC(setup)) pee = pee.map(() => 1); // all active flavours alike
      let truth = new Float64Array(nb);
      if (setup.channel === "es") {
        const q = quadrature(kind, energy, weight);
        energy.forEach((_, i) => {
          const we = scale * q[i] * pee[i], wx = scale * q[i] * (1 - pee[i]), ke = k[0][i], kx = k[1][i];
          for (let j = 0; j < nb; j++) truth[j] += we * ke[j] + wx * kx[j];
        });
      } else {
        truth = visible(inputs, setup, kind, energy, energy.map((_, i) => scale * weight[i] * pee[i] * k[i]), edges);
      }
      const observed = new Float64Array(nb);
      for (let j = 0; j < nb; j++) {
        if (truth[j] === 0) continue;
        if (rows[j] === null) observed[j] += truth[j];
        else for (let m = 0; m < nb; m++) observed[m] += truth[j] * rows[j][m];
      }
      return Array.from(observed, (v, m) => g * v * acceptance[m]);
    };
    out[c] = { day: spectrum(peeDay, gDay), night: spectrum(peeNight, gNight) };
  }
  return out;
}

const rebinIndex = (fine, display) => Array.from({ length: fine.length - 1 }, (_, j) => {
  const centre = 0.5 * (fine[j] + fine[j + 1]);
  let b = 0;
  while (b < display.length - 2 && display[b + 1] < centre) b++;
  return b;
});

function prepared(inputs, setup, component) {
  // cached products of the kernels with the response: per true bin the accepted fraction g = R a;
  // ES also the kernels times g (totals) and times R, a and the display re-binning (spectra)
  const key = [component, setup.detector, setup.channel, setup.es_model, setup.xsec_model, responseKey(setup)].join("|");
  inputs.preparedCache ||= new Map();
  if (!inputs.preparedCache.has(key)) {
    const [edges, display] = observedEdges(setup.threshold), [rows, acceptance] = response(inputs, setup, edges);
    const nb = edges.length - 1, nd = display.length - 1, index = rebinIndex(edges, display);
    const identity = rows.every((r) => r === null);
    const accepted = rows.map((r, j) => (r === null ? acceptance[j] : r.reduce((t, v, m) => t + v * acceptance[m], 0)));
    // true bin -> display bin: resolution, acceptance and re-binning in one [nb][nd] matrix
    const toDisplay = rows.map((r, j) => {
      const out = new Float64Array(nd);
      if (r === null) out[index[j]] = acceptance[j]; else for (let m = 0; m < nb; m++) out[index[m]] += r[m] * acceptance[m];
      return out;
    });
    const observe = (vec) => { // true bins -> accepted, display-binned observed bins
      const out = new Float64Array(nd);
      for (let j = 0; j < nb; j++) { const v = vec[j]; if (v === 0) continue; const t = toDisplay[j]; for (let b = 0; b < nd; b++) out[b] += v * t[b]; }
      return out;
    };
    const { kind, energy, weight } = inputs.components[component], k = kernels(inputs, setup, component, edges);
    const prep = { edges, display, rows, acceptance, accepted, identity, observe, index };
    if (setup.channel === "es") {
      const q = quadrature(kind, energy, weight), base = new Float64Array(nb);
      const diff = energy.map((_, i) => Float64Array.from({ length: nb }, (__, j) => k[0][i][j] - k[1][i][j]));
      energy.forEach((_, i) => { for (let j = 0; j < nb; j++) base[j] += q[i] * k[1][i][j]; }); // true = (q P)(K_e - K_x) + q K_x
      const dot = (v) => v.reduce((t, x, j) => t + x * accepted[j], 0);
      Object.assign(prep, { q, diffTotal: diff.map(dot), baseTotal: dot(base), diffDisplay: diff.map(observe), baseDisplay: observe(base) });
    } else prep.sigma = k;
    inputs.preparedCache.set(key, prep);
  }
  return inputs.preparedCache.get(key);
}

function fast(inputs, probabilities, setup, osc, night, wantSpectra) {
  const [gDay, gNight] = orbital(inputs, setup), times = (g, v) => (v === null ? null : wantSpectra ? v.map((x) => g * x) : g * v);
  const out = {};
  for (const [c, [peeDay, peeNight]] of Object.entries(survival(inputs, probabilities, setup, osc, night))) {
    const { kind, energy, weight } = inputs.components[c], prep = prepared(inputs, setup, c);
    const scale = inputs.data.seconds_per_year * targetsOf(inputs, setup) * inputs.flux(setup.solar_model, c, setup.b8_flux);
    const value = (pee) => {
      if (pee === null) return wantSpectra ? null : NaN;
      if (isNC(setup)) pee = pee.map(() => 1); // all active flavours alike
      if (setup.channel === "es") {
        const w = prep.q.map((qi, i) => qi * pee[i]);
        if (!wantSpectra) return scale * (w.reduce((t, wi, i) => t + wi * prep.diffTotal[i], 0) + prep.baseTotal);
        const out2 = Array.from(prep.baseDisplay);
        w.forEach((wi, i) => { const row = prep.diffDisplay[i]; for (let b = 0; b < out2.length; b++) out2[b] += wi * row[b]; });
        return out2.map((v) => scale * v);
      }
      const truth = visible(inputs, setup, kind, energy, energy.map((_, i) => scale * weight[i] * pee[i] * prep.sigma[i]), prep.edges);
      if (!wantSpectra) return truth.reduce((t, v, j) => t + v * prep.accepted[j], 0);
      return Array.from(prep.observe(truth));
    };
    out[c] = { day: times(gDay, value(peeDay)), night: times(gNight, value(peeNight)) };
    if (!wantSpectra) out[c].ref = value(peeDay.map(() => 1)); // without oscillations: the denominator of "ratio"
  }
  return out;
}

export const componentTotals = (inputs, probabilities, setup, osc, night = true) => fast(inputs, probabilities, setup, osc, night, false);
export const componentSpectra = (inputs, probabilities, setup, osc, night = true) => fast(inputs, probabilities, setup, osc, night, true);

export function totals(rates) {
  return Object.fromEntries(Object.entries(rates).map(([c, r]) => [c, { day: r.day === null ? NaN : sum(r.day), night: r.night === null ? NaN : sum(r.night) }]));
}

export function combine(per, components, multipliers = null) {
  // [day, night, ref]: ref the rate without oscillations, when the totals have it (else NaN)
  let day = 0, night = 0, ref = 0;
  components.forEach((c, k) => {
    const m = multipliers ? multipliers[k] : 1;
    day += m * per[c].day; night += m * per[c].night; ref += m * (per[c].ref === undefined ? NaN : per[c].ref);
  });
  return [day, night, ref];
}

export function quantityValue(quantity, period, day, night, ref = NaN) {
  if (quantity === "adn") return 2 * (night - day) / (night + day);
  const rate = { day, night, annual: 0.5 * (day + night) }[period];
  return quantity === "ratio" ? rate / ref : rate;
}

export function statisticalSigma(quantity, period, day, night, exposure, ref = NaN) {
  // Poisson error for `exposure` kton-years, half of it by night (no backgrounds); the ratio's: the rate's over ref
  if (!exposure) return null;
  if (quantity === "ratio") return statisticalSigma("rate", period, day, night, exposure) / ref;
  if (quantity === "adn") {
    const D = day * exposure / 2, N = night * exposure / 2, S = D + N;
    return Math.sqrt((4 * D / S ** 2) ** 2 * N + (4 * N / S ** 2) ** 2 * D);
  }
  const rate = quantityValue(quantity, period, day, night), live = period === "annual" ? exposure : exposure / 2;
  return Math.sqrt(rate * live) / live;
}

export function rebin(values, fine, display) {
  // fine-bin values summed into the display bins (each fine bin goes where its centre falls)
  const out = new Array(display.length - 1).fill(0);
  for (let j = 0; j + 1 < fine.length; j++) {
    const centre = 0.5 * (fine[j] + fine[j + 1]);
    let b = 0;
    while (b < display.length - 2 && display[b + 1] < centre) b++;
    out[b] += values[j];
  }
  return out;
}

// ------------------------------------------------------------------ budget

export const ES_MODELS = ["bks", "tree", "snowglobes"];
export const ES_RANGE = ["bks", "snowglobes"]; // the radiatively corrected calculations; tree level is selectable, not a model
export const RANGE_LABELS = { xsec_model: "cross-section model", es_model: "ES radiative corrections",
                              earth_model: "Earth model", solar_model: "solar model" };

export function alternatives(inputs, setup, choice) {
  if (choice === "xsec_model") { // without the tables that are incomplete (zero below 5 MeV)
    const incomplete = (inputs.data.xsec_incomplete || {})[setup.channel] || [];
    return setup.channel !== "es" ? inputs.xsecModels(setup.channel).filter((m) => !incomplete.includes(m)) : [];
  }
  if (choice === "es_model") return setup.channel === "es" ? [...ES_RANGE] : [];
  if (choice === "earth_model") return [...inputs.data.earth_models];
  if (choice === "solar_model") return Object.keys(inputs.data.solar_models);
  throw new Error(choice);
}

export function fluxLabel(setup) {
  const measured = setup.b8_flux === "sno_nc" && setup.components.includes("B8");
  if (setup.components.length === 1) return `${DISPLAY[setup.components[0]]} flux (${measured ? "SNO NC" : "solar model"})`;
  return "solar fluxes" + (measured ? " (8B from SNO NC)" : "");
}

export function detectorSigmas(inputs, probabilities, setup, params, quantity, central, night) {
  // [[source, sigma]] of the detector uncertainties that are set: the quantity at the energy scale (or
  // resolution) shifted by +-1 sigma, half the difference; the normalisation scales a rate (cancels in A_DN)
  const value = (s) => quantityValue(quantity, s.period, ...combine(componentTotals(inputs, probabilities, s, oscillation(params), night), s.components));
  const pct = (x) => `${+(100 * x).toPrecision(6)}`;
  const out = [];
  if (setup.energy_scale_error > 0) {
    const e = setup.energy_scale_error;
    const [up, down] = [1, -1].map((k) => value({ ...setup, energy_scale: setup.energy_scale * (1 + k * e) }));
    out.push([`energy scale (±${pct(e)} %)`, Math.abs(up - down) / 2]);
  }
  if (setup.resolution_error > 0 && !setup.smearing_table) { // an imported matrix has no sigma to scale
    const r = setup.resolution_error;
    const [up, down] = [1, -1].map((k) => value({ ...setup, resolution_scale: setup.resolution_scale * (1 + k * r) }));
    out.push([`energy resolution (±${pct(r)} %)`, Math.abs(up - down) / 2]);
  }
  if (setup.normalisation_error > 0 && quantity === "rate")
    out.push([`detector normalisation (±${pct(setup.normalisation_error)} %)`, Math.abs(central) * setup.normalisation_error]);
  return out;
}

export function levelSigmas(inputs, probabilities, setup, params, quantity, central, night) {
  // measured nuclear strengths: one table per level with its B(GT) raised by 1 sigma (sigma is linear in each),
  // levels independent: sigma^2 = sum of the squared shifts of the quantity
  if (setup.channel === "es") return [];
  const levels = ((inputs.data.xsec_levels || {})[setup.channel] || {})[setup.xsec_model];
  if (!levels || !levels.length) return [];
  const value = (s) => quantityValue(quantity, s.period, ...combine(componentTotals(inputs, probabilities, s, oscillation(params), night), s.components));
  const variance = levels.reduce((t, level) => t + (value({ ...setup, xsec_model: level.name }) - central) ** 2, 0);
  return [[`measured B(GT) (${levels.length} levels)`, Math.sqrt(variance)]];
}

export function fluxSummary(inputs, probabilities, setup, osc) {
  // flux at Earth of the selected components (cm^-2 s^-1) and the flux-weighted nu_e fraction by day
  const components = {};
  for (const [c, [pee]] of Object.entries(survival(inputs, probabilities, setup, osc, false))) {
    const { kind, energy, weight } = inputs.components[c], q = quadrature(kind, energy, weight);
    components[c] = [inputs.flux(setup.solar_model, c, setup.b8_flux), q.reduce((t, w, i) => t + w * pee[i], 0)];
  }
  const total = Object.values(components).reduce((t, [f]) => t + f, 0);
  return { total, nue_day: Object.values(components).reduce((t, [f, p]) => t + f * p, 0) / total, components };
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
    quantityValue(quantity, s.period, ...combine(componentTotals(inputs, probabilities, s, osc, night), comps, m));
  const d = given || draws(inputs, setup, params, n, seed);
  const nominal = componentTotals(inputs, probabilities, setup, oscillation(params), night);
  const [day0, night0, ref0] = combine(nominal, comps);
  const central = quantityValue(quantity, setup.period, day0, night0, ref0);
  const rows = [], samples = {};
  const sampled = (source, values) => {
    const sigma = std(values);
    rows.push({ Source: source, Kind: "sampled", Central: central, Sigma: sigma, Relative: relative(sigma, central), Low: NaN, High: NaN });
    samples[source] = values;
  };
  const perDraw = d.osc.map((o) => componentTotals(inputs, probabilities, setup, o, night));
  sampled("oscillation parameters", perDraw.map((p) => quantityValue(quantity, setup.period, ...combine(p, comps))));
  let total = perDraw.map((p, i) => quantityValue(quantity, setup.period, ...combine(p, comps, d.flux ? d.flux[i] : null)));
  if (d.flux && !(quantity !== "rate" && comps.length === 1)) // one flux cancels in a ratio
    sampled(fluxLabel(setup), d.flux.map((m) => quantityValue(quantity, setup.period, ...combine(nominal, comps, m))));
  const queue = d.noise ? [...d.noise] : null, next = () => (queue ? queue.shift() : d.rng.normals(total.length));
  const stat = statisticalSigma(quantity, setup.period, day0, night0, setup.exposure, ref0);
  if (stat !== null) {
    sampled(`statistics (${+setup.exposure.toPrecision(6)} kt yr)`, next().map((z) => central + stat * z));
    const z = next();
    total = total.map((t, i) => t + stat * z[i]);
  }
  for (const [source, sigma] of [...detectorSigmas(inputs, probabilities, setup, params, quantity, central, night),
                                 ...levelSigmas(inputs, probabilities, setup, params, quantity, central, night)]) {
    const z = next(); // one Gaussian draw per source: its row and its share of the total
    sampled(source, z.map((x) => central + sigma * x));
    total = total.map((t, i) => t + sigma * z[i]);
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

export function spectra(inputs, probabilities, setup, params, { n = 400, seed = 1, night = true, given = null } = {}) {
  // rates per kton-year in display bins of observed energy: central per component and in total, and every draw's totals
  check(inputs, setup);
  const [, display] = observedEdges(setup.threshold), comps = setup.components, nd = display.length - 1;
  const d = given || draws(inputs, setup, params, n, seed);
  const total = (per, m = null) => {
    const day = new Array(nd).fill(0), nite = night ? new Array(nd).fill(0) : null;
    comps.forEach((c, k) => { const f = m ? m[k] : 1; per[c].day.forEach((v, b) => { day[b] += f * v; }); if (night) per[c].night.forEach((v, b) => { nite[b] += f * v; }); });
    return [day, nite];
  };
  const components = componentSpectra(inputs, probabilities, setup, oscillation(params), night);
  const each = d.osc.map((o, i) => total(componentSpectra(inputs, probabilities, setup, o, night), d.flux ? d.flux[i] : null));
  const [day, nite] = total(components);
  return { edges: display, observable: observable(setup.channel), components, day, night: nite,
           draws_day: each.map((x) => x[0]), draws_night: night ? each.map((x) => x[1]) : null };
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
  // theta13 is followed as nu_3 decouples: F_1,2 and P_1e,2e scale with cos^2 theta13, F_3 and P_3e with
  // sin^2 theta13 (P_ee = c13^4 P_ee^2nu + s13^4); `referenceS13` is the tables' (the registry default)
  constructor(loader, referenceS13) { this.loader = loader; this.tables = {}; this.clamped = 0; this.referenceS13 = referenceS13; }

  theta13(osc) { const s = osc.sin2_theta13, r = this.referenceS13 ?? s; return [(1 - s) / (1 - r), s / r]; }

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
    const F12 = this.blend(F, 0, t.dm21.length, e.length * 2, this.point(t, osc)), [c] = this.theta13(osc);
    const loge = e.map(Math.log), f1 = e.map((_, k) => F12[2 * k]), f2 = e.map((_, k) => F12[2 * k + 1]);
    return energies.map((x) => {
      const l = Math.log(Math.min(Math.max(x, e[0]), e[e.length - 1]));
      const a = c * interp(l, loge, f1), b = c * interp(l, loge, f2);
      return [a, b, 1 - a - b];
    });
  }

  night(osc, earthModel, site) {
    const t = this.get(`night_${earthModel}`), s = t.sites.indexOf(site), P = t.P;
    const [, ns, nd, ne] = P.shape, rest = ne * 3;
    const flat = this.blend(P, s * ns * nd * rest, nd, rest, this.point(t, osc)), [c, s3] = this.theta13(osc);
    return [t.energy, Array.from({ length: ne }, (_, k) => [c * flat[3 * k], c * flat[3 * k + 1], s3 * flat[3 * k + 2]])];
  }
}
