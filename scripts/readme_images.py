"""Render the README figures (input/plots/readme_scripts.txt) in light and
dark and copy them to docs/images/{light,dark}/<output_suffix>.png.

    python scripts/readme_images.py      # after `snufish build`
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIST = ROOT / "input" / "plots" / "readme_scripts.txt"


def main():
    suffixes = re.findall(r"--output_suffix (\w+)", LIST.read_text())
    for theme, folder in (("light", "web"), ("dark", "web-dark")):
        subprocess.run([sys.executable, "-m", "plotipus", "run", "readme", "--medium", "web", "--theme", theme],
                       cwd=ROOT, check=True, capture_output=True)
        target = ROOT / "docs" / "images" / theme
        target.mkdir(parents=True, exist_ok=True)
        for suffix in suffixes:
            (found,) = (ROOT / "output" / "plots" / folder).glob(f"*_{suffix}.png")
            shutil.copy(found, target / f"{suffix}.png")
            print(f"{target / suffix}.png")


if __name__ == "__main__":
    main()
