// "Render with plotipus": Python (Pyodide) and plotipus in a background worker, loaded on the
// first request only, so the page itself never waits for them. Input: a plotipus project
// (export.js plotipusProject) and a theme; output: the PNGs `plotipus run app` would write.
// Pyodide comes from `base`: its CDN, or the site's own copy (pyodide/, written by build.py --artifact) where
// the page may not fetch from other hosts.

const PACKAGES = ["numpy", "pandas", "matplotlib", "scipy", "pyarrow", "pyyaml", "jinja2", "rich", "micropip"];
let ready = null;

function decodeFetches(encoded, site) {
  // a hosted site keeps wheels and zips as base64 text parts (build.py encode): fetches of them are answered
  // from the parts, everything else goes through
  const parts = new Map(Object.entries(encoded).map(([path, n]) => [new URL(path, site).href, n]));
  const fetch = self.fetch.bind(self);
  self.fetch = async (input, init) => {
    const url = new URL(input instanceof Request ? input.url : String(input), site).href, n = parts.get(url.split(/[?#]/)[0]);
    if (!n) return fetch(input, init);
    const texts = await Promise.all(Array.from({ length: n }, (_, k) => fetch(`${url}.b64.${k}.txt`).then((r) => {
      if (!r.ok) throw new Error(`${url}: part ${k} (${r.status})`);
      return r.text();
    })));
    const binary = atob(texts.join("").trim()), bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return new Response(bytes, { status: 200, headers: { "Content-Type": "application/octet-stream" } });
  };
}

function start(wheel, base) {
  ready ||= (async () => {
    self.postMessage({ type: "progress", text: "Loading Python (first time only, ~10 s)…" });
    const { loadPyodide } = await import(`${base}pyodide.mjs`);
    const py = await loadPyodide({ indexURL: base });
    await py.loadPackage(PACKAGES, { messageCallback: () => {} });
    self.postMessage({ type: "progress", text: "Installing plotipus…" });
    await py.pyimport("micropip").install(wheel, { deps: false }); // its dependencies are loaded above
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
  const { id, wheel, base, encoded, site, files, commands, theme } = data;
  try {
    if (encoded && !self.decoding) { decodeFetches(encoded, site); self.decoding = true; }
    const py = await start(wheel, base);
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
