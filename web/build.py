"""Assemble the static SNUfish page: web/ plus the tables of ``snufish export-app``.

    snufish export-app --out build/app
    python web/build.py --out build/site     # --plotipus: the plotipus checkout (default ../plotipus)
    python -m http.server -d build/site      # open http://localhost:8000 (home), rates.html (calculator)

The result is plain files (HTML, JS, CSS, JSON, binary tables): any static
host serves it (GitHub Pages, a lab web server).
"""

import argparse
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
PAGE = ["index.html", "rates.html", "style.css", "app.js", "engine.js", "plots.js", "export.js", "sources.js", "checks.js", "official.js",
        "plotipus-worker.js"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tables", type=Path, default=ROOT / "build" / "app")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "site")
    parser.add_argument("--artifact", action="store_true",
                        help="for a claude.ai artifact: pages marked as hosted (no downloads or shareable hash "
                             "there), home page without its own document wrapper, and a copy of Pyodide (pyodide/), "
                             "since the page may not fetch from other hosts")
    parser.add_argument("--plotipus", type=Path, default=ROOT.parent / "plotipus",
                        help="plotipus checkout: its wheel is served for 'Render with plotipus'")
    args = parser.parse_args()
    if not (args.tables / "inputs.json").exists():
        raise SystemExit(f"no tables in {args.tables}: run snufish export-app first")
    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)
    for name in PAGE:
        shutil.copy(WEB / name, args.out / name)
    shutil.copytree(args.tables, args.out / "data")
    py = args.out / "py"
    py.mkdir()
    subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "-q", "-w", str(py), str(args.plotipus)], check=True)
    wheel = next(py.glob("plotipus-*.whl")).name
    (py / "manifest.json").write_text(json.dumps({"plotipus": wheel}))
    if args.artifact:
        hosted(args.out)
        pyodide(args.out / "pyodide")
        encode(args.out, ["py", "pyodide"])
    print_size(args.out)


PYODIDE = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/"  # as in app.js
PACKAGES = ["numpy", "pandas", "matplotlib", "scipy", "pyarrow", "pyyaml", "jinja2", "rich", "micropip"]  # as in the worker
CACHE = Path.home() / ".cache" / "snufish" / "pyodide-v314.0.7"


def pyodide(out):
    """Pyodide's runtime and the worker's packages with their dependencies (from its lock file), downloaded once
    into CACHE and copied to ``out``."""
    def fetch(name):
        path = CACHE / name
        if not path.exists():
            CACHE.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(PYODIDE + name) as response:
                path.with_suffix(".part").write_bytes(response.read())
            path.with_suffix(".part").rename(path)
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, out / name)

    for name in ("pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"):
        fetch(name)
    packages = json.loads((out / "pyodide-lock.json").read_text())["packages"]
    needed = set()

    def add(name):
        if name not in needed:
            needed.add(name)
            for dependency in packages[name]["depends"]:
                add(dependency)

    for name in PACKAGES:
        add(name)
    for name in sorted(needed):
        fetch(packages[name]["file_name"])


SERVED = {".js", ".mjs", ".wasm", ".json", ".txt", ".html", ".css"}  # what an artifact serves, of what is here
PART = 15_000_000  # characters per base64 part (an artifact text file holds 16 MB)


def encode(out, folders):
    """Files an artifact does not serve (wheels, zip) as base64 text parts, <name>.b64.<k>.txt, listed in
    encoded.json ({path: parts}); the plotipus worker puts them back together when Pyodide fetches them."""
    import base64

    listed = {}
    for folder in folders:
        for path in sorted((out / folder).iterdir()):
            if path.suffix in SERVED:
                continue
            text = base64.b64encode(path.read_bytes()).decode()
            parts = [text[k:k + PART] for k in range(0, len(text), PART)]
            for k, part in enumerate(parts):
                path.with_name(f"{path.name}.b64.{k}.txt").write_text(part)
            path.unlink()
            listed[path.relative_to(out).as_posix()] = len(parts)
    (out / "encoded.json").write_text(json.dumps(listed, indent=1))


def print_size(out):
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"site in {out} ({size / 1e6:.1f} MB)")


HOSTED = '<meta name="snufish-host" content="artifact">'


def hosted(out):
    """Mark both pages as hosted; the home page loses its document wrapper (the host adds one)."""
    import base64

    for index in (out / "data").glob("*.json"):  # artifacts serve text, not raw binary: tables as base64 .txt
        meta = json.loads(index.read_text())
        if "bin" not in meta:
            continue
        binary = out / "data" / meta["bin"]
        encoded = binary.with_suffix(".b64.txt")
        encoded.write_text(base64.b64encode(binary.read_bytes()).decode())
        binary.unlink()
        meta.update(bin=encoded.name, encoding="base64")
        index.write_text(json.dumps(meta))
    rates = (out / "rates.html").read_text()
    (out / "rates.html").write_text(rates.replace('<meta charset="utf-8">', f'<meta charset="utf-8">\n  {HOSTED}', 1))
    home = (out / "index.html").read_text()
    head = home[home.index("<head>") + 6:home.index("</head>")]
    body = home[home.index("<body>") + 6:home.index("</body>")]
    head = "\n".join(line for line in head.splitlines() if "charset" not in line and 'name="viewport"' not in line)
    (out / "index.html").write_text(f"{HOSTED}\n{head.strip()}\n{body.strip()}\n")


if __name__ == "__main__":
    main()
