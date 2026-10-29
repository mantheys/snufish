// Cross-check of web/engine.js against the Python engine: reference results
// (with the Python draws) written by tests/test_web_engine.py.
//     node web/test/engine.test.mjs <fixtures.json> <tables directory>
import fs from "node:fs";
import path from "node:path";
import * as engine from "../engine.js";

const [fixturesPath, tablesDir] = process.argv.slice(2);
const fixtures = JSON.parse(fs.readFileSync(fixturesPath, "utf8"));
const inputs = new engine.Inputs(JSON.parse(fs.readFileSync(path.join(tablesDir, "inputs.json"), "utf8")));
const tables = new engine.TableProbabilities(async (name) => {
  const meta = JSON.parse(fs.readFileSync(path.join(tablesDir, `${name}.json`), "utf8"));
  const bytes = fs.readFileSync(path.join(tablesDir, meta.bin));
  return { meta, buffer: bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) };
});
await tables.ensure([...Object.keys(inputs.data.solar_models).map((m) => `day_${m}`),
                     ...inputs.data.earth_models.map((e) => `night_${e}`)]);

const TOLERANCE = 1e-9;
let worst = 0, failures = 0, compared = 0;
function close(a, b, where) {
  if (a === null || b === null || (Number.isNaN(a) && Number.isNaN(b))) {
    if (!((a === null || Number.isNaN(a)) && (b === null || Number.isNaN(b)))) { failures++; console.log(`  ${where}: ${a} vs ${b}`); }
    return;
  }
  const r = Math.abs(a - b) / Math.max(Math.abs(b), 1e-300);
  compared++;
  if (!(Math.abs(a - b) <= 1e-12 * Math.max(1, Math.abs(b)) || r <= TOLERANCE)) {
    if (failures < 20) console.log(`  ${where}: js ${a} python ${b} (relative ${r.toExponential(2)})`);
    failures++;
  } else if (Math.abs(b) > 1e-12) worst = Math.max(worst, r);
}
const nan = (v) => (v === null ? NaN : v);

for (const c of fixtures.cases) {
  const setup = engine.makeSetup(c.setup), params = c.params;
  const given = { osc: c.draws.osc, flux: c.draws.flux, noise: c.draws.noise };
  const f = engine.fluxSummary(inputs, tables, setup, engine.oscillation(params));
  close(f.total, c.flux.total, `${c.name} flux`); close(f.nue_day, c.flux.nue_day, `${c.name} nue fraction`);
  const { rows } = engine.budget(inputs, tables, setup, params, c.quantity, { solarRange: c.solar_range, given });
  if (rows.length !== c.rows.length) { failures++; console.log(`  ${c.name}: ${rows.length} rows vs ${c.rows.length}`); }
  rows.forEach((r, i) => {
    const p = c.rows[i] || {};
    if (r.Source !== p.Source) { failures++; console.log(`  ${c.name}: row ${i} ${r.Source} vs ${p.Source}`); }
    for (const k of ["Central", "Sigma", "Low", "High"]) close(r[k], nan(p[k]), `${c.name} ${r.Source} ${k}`);
  });
  const s = engine.spectra(inputs, tables, setup, params, { night: c.spectra.night !== null, given });
  s.edges.forEach((v, b) => close(v, c.spectra.edges[b], `${c.name} edges ${b}`));
  s.day.forEach((v, b) => close(v, c.spectra.day[b], `${c.name} spectrum day bin ${b}`));
  if (s.night) s.night.forEach((v, b) => close(v, c.spectra.night[b], `${c.name} spectrum night bin ${b}`));
  s.draws_day.forEach((row, i) => row.forEach((v, b) => close(v, c.spectra.draws_day[i][b], `${c.name} draw ${i} bin ${b}`)));
}
for (const bad of fixtures.invalid) {
  try { engine.check(inputs, engine.makeSetup(bad.setup), bad.quantity); failures++; console.log(`  accepted invalid setup ${JSON.stringify(bad.setup)}`); }
  catch (e) { if (!e.message.includes(bad.message)) { failures++; console.log(`  wrong message: ${e.message}`); } }
}
console.log(`${fixtures.cases.length} cases, ${compared} numbers, largest relative difference ${worst.toExponential(2)}, ${failures} failures`);
process.exit(failures ? 1 : 0);
