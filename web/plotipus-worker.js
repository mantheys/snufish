// "Render with plotipus": Python (Pyodide) and plotipus in a background worker, loaded on the
// first request only, so the page itself never waits for them. Input: a plotipus project
// (export.js plotipusProject) and a theme; output: the PNGs `plotipus run app` would write.
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

const PACKAGES = ["numpy", "pandas", "matplotlib", "scipy", "pyarrow", "pyyaml", "jinja2", "rich", "micropip"];
let ready = null;

function start(wheel) {
  ready ||= (async () => {
    self.postMessage({ type: "progress", text: "Loading Python (first time only, ~10 s)…" });
    const py = await loadPyodide();
    await py.loadPackage(PACKAGES, { messageCallback: () => {} });
    self.postMessage({ type: "progress", text: "Installing plotipus…" });
    await py.pyimport("micropip").install(wheel);
    await py.runPythonAsync("import matplotlib; matplotlib.use('agg'); import plotipus.cli");
    return py;
  })();
  return ready;
}

const RENDER = `
import contextlib, io, os, shlex, shutil
from plotipus.cli import main

shutil.rmtree("/work/output", ignore_errors=True)
os.chdir("/work")
log, failed = io.StringIO(), []
for command in commands:
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            main([*shlex.split(command), "--theme", theme])
        except SystemExit as exit:
            if exit.code:
                failed.append(command)
        except Exception as error:
            failed.append(f"{command}: {error!r}")
pngs = sorted(os.path.join(root, f) for root, _, files in os.walk("/work/output") for f in files if f.endswith(".png"))
(pngs, failed, log.getvalue()[-3000:])
`;

self.onmessage = async ({ data }) => {
  const { id, wheel, files, commands, theme } = data;
  try {
    const py = await start(wheel);
    self.postMessage({ type: "progress", text: "Drawing the figures with plotipus…" });
    py.FS.mkdirTree("/work");
    py.runPython("import shutil; shutil.rmtree('/work', ignore_errors=True)");
    for (const [path, bytes] of Object.entries(files)) {
      const full = `/work/${path}`;
      py.FS.mkdirTree(full.slice(0, full.lastIndexOf("/")));
      py.FS.writeFile(full, bytes);
    }
    py.globals.set("commands", py.toPy(commands));
    py.globals.set("theme", theme);
    const [pngs, failed, log] = (await py.runPythonAsync(RENDER)).toJs();
    const images = pngs.map((path) => ({ name: path.split("/").pop(), bytes: py.FS.readFile(path) }));
    self.postMessage({ type: "done", id, images, failed, log }, images.map((x) => x.bytes.buffer));
  } catch (error) {
    self.postMessage({ type: "error", id, text: String(error.message || error) });
  }
};
