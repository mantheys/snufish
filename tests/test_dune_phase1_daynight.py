"""Day-night asymmetries of CC and ES in argon for the DUNE solar Phase I paper (scripts/dune_phase1_daynight.py):
pinned, and consistent with the day and night rates of scripts/dune_phase1_rates.py."""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))
DRIVER = ROOT / "contributions" / "nufast-earth" / "scripts" / "b3_driver"

pytestmark = pytest.mark.skipif(not DRIVER.exists(), reason="NuFast-Earth driver not built")

# T_e threshold (MeV): (A_CC, A_ES), A_DN = 2 (N - D) / (N + D)
PINNED = {5.0: (0.04968, 0.02428), 8.0: (0.05999, 0.03052), 10.0: (0.06578, 0.03512)}


def load(name):
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def result():
    return load("dune_phase1_daynight").compute()


def test_asymmetries_are_pinned(result):
    for t, (cc, es) in PINNED.items():
        row = result["thresholds"][t]
        assert row["CC"]["adn"] == pytest.approx(cc, rel=2e-3), t
        assert row["ES"]["adn"] == pytest.approx(es, rel=2e-3), t
        assert row["ratio"] == pytest.approx(es / cc, rel=3e-3), t


def test_same_rates_as_the_rate_script(result):
    rates = load("dune_phase1_rates").rates()
    for ch in ("CC", "ES"):
        for period in ("day", "night"):
            assert result["thresholds"][5.0][ch][period] == pytest.approx(rates[ch, "Te", 5.0][period], rel=1e-3)


def test_one_number_estimate_overstates_the_ratio(result):
    """A constant regeneration gives about 0.63; the spectra give about 0.5, because CC samples higher E_nu."""
    for row in result["thresholds"].values():
        e = row["estimate"]
        assert 0.25 < e["P_ee_day_cc_weighted"] < 0.35 and 0.13 < e["r_es"] < 0.17
        assert e["ratio"] > row["ratio"] + 0.08
