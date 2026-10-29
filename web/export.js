// The result as a small plotipus project (Parquet data, command list, plotipus.toml,
// colors.json with the page's colours), used by "Download" (zipped with the page's
// figures and a README) and by "Render with plotipus" (plotipus-worker.js). Loaded on first use.
import { DISPLAY } from "./engine.js";
import { binAsymmetry, budgetSizes } from "./plots.js";

const PARQUET = "https://cdn.jsdelivr.net/npm/hyparquet-writer@0.16.11/+esm";
const ZIP = "https://cdn.jsdelivr.net/npm/fflate@0.8.2/+esm";

function spectrumColumns(result) {
  // long format: one row per component (and total) and energy bin
  const { spectra, setup } = result, edges = spectra.edges, night = spectra.night !== null;
  const cols = { Component: [], Energy: [], EnergyLow: [], EnergyHigh: [], Day: [] };
  if (night) Object.assign(cols, { Night: [], Annual: [], Asymmetry: [] });
  // bins without interactions (below a threshold, beyond the spectra) are left out, so plotipus's axes fit the data
  const filled = spectra.day.map((d, b) => d > 0 || (night && spectra.night[b] > 0));
  const add = (name, day, nite) => {
    const a = night ? binAsymmetry(day, nite) : null;
    day.forEach((d, b) => {
      if (!filled[b]) return;
      cols.Component.push(name); cols.Energy.push(Math.sqrt(Math.max(edges[b], 0.005) * edges[b + 1]));
      cols.EnergyLow.push(edges[b]); cols.EnergyHigh.push(edges[b + 1]); cols.Day.push(d);
      if (night) { cols.Night.push(nite[b]); cols.Annual.push(0.5 * (d + nite[b])); cols.Asymmetry.push(100 * a[b]); }
    });
  };
  for (const c of setup.components) add(DISPLAY[c], spectra.components[c].day, spectra.components[c].night);
  add("total", spectra.day, spectra.night);
  return cols;
}

function commands(result) {
  const adn = result.quantity === "adn", column = adn ? "Asymmetry" : result.setup.period.replace(/^./, (x) => x.toUpperCase());
  const spectrum = `line --no_error --datafile AppSpectrum -x Energy -y ${column} --hue Component --plot_type step --logx `
    + (adn ? "--select Component -s total --labely 'A_DN (%)' " : "--logy --labely 'Interactions / (kt yr) per bin' ")
    + `--labelx '${result.spectra.observable}' --output_suffix spectrum`;
  const size = adn ? "Uncertainty (%)" : "Relative uncertainty (%)";
  return [
    spectrum,
    `cat --no_error --datafile AppBudget -x Source -y Size --hue Kind --kind bar --orient h --labely '${size}' --output_suffix budget`,
    `hist --datafile AppSamples -x Value --labelx '${{ adn: "A_DN", ratio: "Rate / unoscillated rate" }[result.quantity] || "Rate"} (${result.unit})' --output_suffix samples`,
  ];
}

// plotipus colour registry: the same palette slots as the page (style.css), so a component keeps its colour
const COLOURS = {
  Component: { pp: "C0", pep: "C1", hep: "C2", "7Be": "C3", "8B": "C4", "13N": "C5", "15O": "C6", "17F": "C7", total: "role:ink" },
  Kind: { sampled: "C0", "model range": "C1" },
};

export async function plotipusProject(result, description, link) {
  const { parquetWriteBuffer } = await import(PARQUET);
  const strToU8 = (text) => new TextEncoder().encode(text);
  const columns = (cols) => Object.entries(cols).map(([name, data]) =>
    ({ name, data, type: typeof data[0] === "string" ? "STRING" : "DOUBLE" }));
  const rows = result.rows, sizes = budgetSizes(rows, result.quantity, result.scale);
  const budget = { Source: rows.map((r) => r.Source), Kind: rows.map((r) => r.Kind), Central: rows.map((r) => r.Central),
                   Sigma: rows.map((r) => r.Sigma), Low: rows.map((r) => r.Low), High: rows.map((r) => r.High),
                   Relative: rows.map((r) => r.Relative), Size: sizes };
  // plotipus hist reads one row holding the whole sample array
  const samples = parquetWriteBuffer({
    columnData: [{ name: "Quantity", data: [result.quantity] }, { name: "Value", data: [result.samples["total sampled"].map((v) => v * result.scale)] }],
    schema: [{ name: "root", num_children: 2 },
             { name: "Quantity", type: "BYTE_ARRAY", converted_type: "UTF8", repetition_type: "REQUIRED" },
             { name: "Value", repetition_type: "OPTIONAL", converted_type: "LIST", num_children: 1 },
             { name: "list", repetition_type: "REPEATED", num_children: 1 },
             { name: "element", type: "DOUBLE", repetition_type: "REQUIRED" }],
  });
  const list = commands(result);
  return { commands: list, files: {
    "build/data/AppSpectrum.parquet": new Uint8Array(parquetWriteBuffer({ columnData: columns(spectrumColumns(result)) })),
    "build/data/AppBudget.parquet": new Uint8Array(parquetWriteBuffer({ columnData: columns(budget) })),
    "build/data/AppSamples.parquet": new Uint8Array(samples),
    "plotipus.toml": strToU8('[project]\ndata_root = "build/data"\nplots = "input/plots"\noutput = "output"\n'),
    "input/plots/app_scripts.txt": strToU8(`# ${description}\n# ${link}\n${list.join("\n")}\n`),
    "colors.json": strToU8(JSON.stringify(COLOURS, null, 1)),
    "README.txt": strToU8([
      "SNUfish result", "", description, `Setup: ${link}`, "",
      "build/data/AppSpectrum.parquet  rates per kt yr per energy bin (one row per component and bin; Asymmetry in %)",
      "build/data/AppBudget.parquet    error budget: sampled sigma, or model range Low-High (Size: as plotted)",
      "build/data/AppSamples.parquet   the sampled values of the result (one row, an array)",
      "figures/                        the page's figures (and plotipus/, if rendered in the page)",
      "", "Plots with plotipus (https://github.com/mantheys/plotipus): plotipus run app", "",
    ].join("\n")),
  } };
}

export async function downloadResult(result, description, link, rendered = []) {
  const [{ zipSync }, { files }] = await Promise.all([import(ZIP), plotipusProject(result, description, link)]);
  for (const { name, bytes } of rendered) files[`figures/plotipus/${name}`] = bytes;
  for (const [name, id] of [["spectrum", "plot-spectrum"], ["distribution", "plot-distribution"], ["budget", "plot-budget"]]) {
    const url = await Plotly.toImage(document.getElementById(id), { format: "png", width: 1200, height: 700, scale: 2 });
    files[`figures/${name}.png`] = Uint8Array.from(atob(url.split(",")[1]), (ch) => ch.charCodeAt(0));
  }
  const blob = new Blob([zipSync(files)], { type: "application/zip" });
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "snufish_result.zip" });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}
