"""Build the static SNUfish app (Panel on Pyodide) into a directory to serve.

    snufish export-app --out build/app        # tables (once per data change)
    python app/build.py --plotipus ../plotipus --out build/site
    python -m http.server -d build/site       # then open /snufish_app.html

The site holds the page and its worker, wheels of snufish and plotipus
(installed in the browser by micropip) and the tables under data/.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Pyodide packages the app needs beyond what Panel infers from its imports.
PACKAGES = ["numpy", "pandas", "pyarrow", "matplotlib", "scipy", "pyyaml", "jinja2", "rich"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plotipus", type=Path, required=True, help="plotipus checkout")
    parser.add_argument("--tables", type=Path, default=ROOT / "build" / "app")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "site")
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    wheels = []
    for source in (ROOT, args.plotipus.resolve()):
        before = set(out.glob("*.whl"))
        subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "-q", "-w", str(out), str(source)],
                       check=True)
        wheels += [w.name for w in set(out.glob("*.whl")) - before]
    requirements = out / "requirements.txt"
    requirements.write_text("\n".join([*PACKAGES, *(f"./{w}" for w in sorted(wheels))]) + "\n")
    subprocess.run(["panel", "convert", str(ROOT / "app" / "snufish_app.py"), "--to", "pyodide-worker",
                    "--out", str(out), "--requirements", str(requirements),
                    "--title", "SNUfish"], check=True)
    shutil.copytree(args.tables, out / "data")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"site in {out} ({size / 1e6:.1f} MB): serve it and open snufish_app.html")


if __name__ == "__main__":
    main()
