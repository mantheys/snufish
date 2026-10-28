"""Assemble the static SNUfish page: web/ plus the tables of ``snufish export-app``.

    snufish export-app --out build/app
    python web/build.py --out build/site
    python -m http.server -d build/site      # open http://localhost:8000

The result is plain files (HTML, JS, CSS, JSON, binary tables): any static
host serves it (GitHub Pages, a lab web server).
"""

import argparse
import shutil
from pathlib import Path

WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
PAGE = ["index.html", "style.css", "app.js", "engine.js", "plots.js", "export.js"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tables", type=Path, default=ROOT / "build" / "app")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "site")
    args = parser.parse_args()
    if not (args.tables / "inputs.json").exists():
        raise SystemExit(f"no tables in {args.tables}: run snufish export-app first")
    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)
    for name in PAGE:
        shutil.copy(WEB / name, args.out / name)
    shutil.copytree(args.tables, args.out / "data")
    size = sum(p.stat().st_size for p in args.out.rglob("*") if p.is_file())
    print(f"site in {args.out} ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
