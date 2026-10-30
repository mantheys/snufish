import shutil
from pathlib import Path

import pytest

from snufish.contribution import load_contribution, validate
from snufish.spec import load_spec

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "contributions" / "snufish-reference" / "B3_earth"


@pytest.fixture(scope="module")
def spec():
    return load_spec("B3_earth", root=ROOT)


@pytest.fixture(scope="module")
def reference_dir():
    versions = sorted(REFERENCE.glob("*/meta.yaml"))
    if not versions:
        pytest.skip("run `snufish reference B3_earth` first")
    return versions[-1].parent


def test_reference_contribution_is_valid(reference_dir, spec):
    assert validate(load_contribution(reference_dir), spec) == []


def _copy(reference_dir, tmp_path):
    target = tmp_path / "toy" / "B3_earth" / "1.0"
    shutil.copytree(reference_dir, target)
    contribution = load_contribution(target)
    contribution.meta.update(tool="toy", tool_version="1.0")
    return contribution


def test_detects_unitarity_violation(reference_dir, spec, tmp_path):
    contribution = _copy(reference_dir, tmp_path)
    df = contribution.data
    df.loc[(df.quantity == "P2e") & (df.cos_nadir == 0.9), "value"] += 1e-3
    assert any("unitarity" in p for p in validate(contribution, spec))


def test_detects_wrong_grid(reference_dir, spec, tmp_path):
    contribution = _copy(reference_dir, tmp_path)
    contribution.data = contribution.data[contribution.data.energy < 19.95]
    assert any("grid" in p for p in validate(contribution, spec))


def test_detects_missing_meta(reference_dir, spec, tmp_path):
    contribution = _copy(reference_dir, tmp_path)
    del contribution.meta["command"]
    assert any("command" in p for p in validate(contribution, spec))


def test_detects_missing_grid(reference_dir, spec, tmp_path):
    contribution = _copy(reference_dir, tmp_path)
    contribution.data = contribution.data[contribution.data.grid == "map"]
    assert any("grids ['exposure'] missing" in p for p in validate(contribution, spec))
