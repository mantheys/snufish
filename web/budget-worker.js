// The calculator's refinement (app.js): the same budget and spectra as on the page, with more draws, off the main
// thread, so the page answers at once with fewer draws and stays responsive while the precise numbers come.
import * as engine from "./engine.js";
import { DATA, loadTable } from "./load.js";

let inputs = null, tables = null;

self.onmessage = async ({ data }) => {
  const { id, setup, quantity, set, solarRange, night, n, seed, tableNames } = data;
  try {
    if (!inputs) {
      inputs = new engine.Inputs(await (await fetch(`${DATA}inputs.json`)).json());
      tables = new engine.TableProbabilities(loadTable, inputs.data.parameter_sets.defaults.sin2_theta13.value);
    }
    await tables.ensure(tableNames);
    const t0 = performance.now(), params = engine.parameters(inputs, set);
    const given = engine.draws(inputs, setup, params, n, seed); // shared, as in app.js
    const { rows, samples } = engine.budget(inputs, tables, setup, params, quantity, { given, solarRange, legacy: true });
    const spectra = engine.spectra(inputs, tables, setup, params, { given, night });
    self.postMessage({ id, rows, samples, spectra, ms: performance.now() - t0 });
  } catch (error) {
    self.postMessage({ id, error: String(error.message || error) });
  }
};
