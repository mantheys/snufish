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
from pathlib import Path

WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
PAGE = ["index.html", "rates.html", "style.css", "app.js", "engine.js", "plots.js", "export.js", "sources.js",
        "plotipus-worker.js"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tables", type=Path, default=ROOT / "build" / "app")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "site")
    parser.add_argument("--artifact", action="store_true",
                        help="for a claude.ai artifact: pages marked as hosted (no downloads, plotipus figures or "
                             "shareable hash there), home page without its own document wrapper, no plotipus wheel")
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
    if args.artifact:
        hosted(args.out)
        print_size(args.out)
        return
    py = args.out / "py"
    py.mkdir()
    subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "-q", "-w", str(py), str(args.plotipus)], check=True)
    wheel = next(py.glob("plotipus-*.whl")).name
    (py / "manifest.json").write_text(json.dumps({"plotipus": wheel}))
    print_size(args.out)


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
