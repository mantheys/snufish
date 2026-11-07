"""The raw rates SNUfish provides to the DUNE solar Phase I paper (scripts/dune_phase1_rates.py): pinned, so a change
in any input that moves a quoted number fails here first."""

import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))
DRIVER = ROOT / "contributions" / "nufast-earth" / "scripts" / "b3_driver"

pytestmark = pytest.mark.skipif(not DRIVER.exists(), reason="NuFast-Earth driver not built")

# annual, per kt-yr: the numbers in the paper (docs/dune-solar-tables.md#phase-i-paper)
PINNED = {("CC", "Enu", 1.0): 2425.7, ("ES", "Enu", 1.0): 1281.3, ("NC", "Enu", 1.0): 28.79,
          ("CC", "Enu", 5.0): 2415.8, ("ES", "Enu", 5.0): 1081.3, ("NC", "Enu", 5.0): 28.79,
          ("CC", "Te", 5.0): 1210.2, ("ES", "Te", 5.0): 359.90}


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("dune_phase1_rates", ROOT / "scripts" / "dune_phase1_rates.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def values(script):
    return script.rates()


def test_rates_are_pinned(values):
    assert set(values) == set(PINNED)
    for key, expected in PINNED.items():
        assert values[key]["annual"] == pytest.approx(expected, rel=2e-4), key


def test_annual_is_the_night_share_weighted_mean(values):
    for v in values.values():
        assert v["annual"] == pytest.approx(0.493 * v["day"] + 0.507 * v["night"], rel=1e-9)
        assert v["night"] >= v["day"]


def test_outputs(script, values, tmp_path):
    script.write(values, tmp_path, script.CC_MODEL, "prem_full")
    macros = (tmp_path / "snufish_rates.tex").read_text()
    assert r"\newcommand{\snufishRateCCTeFive}{$1.21\times10^{3}$}" in macros
    assert r"\newcommand{\snufishRateNCEnuOne}{$2.88\times10^{1}$}" in macros
    table = (tmp_path / "snufish_rates_table.tex").read_text()
    assert r"$T_e > 5$ MeV & $1.21\times10^{3}$ & $3.60\times10^{2}$ & --- & --- \\" in table
    record = json.loads((tmp_path / "snufish_rates.json").read_text())
    assert len(record["rates"]) == len(PINNED) and record["settings"]["night_fraction"] == 0.507


def test_latex_number(script):
    assert script.latex_number(1140.26) == r"$1.14\times10^{3}$"
    assert script.latex_number(0.0174) == r"$1.74\times10^{-2}$"
