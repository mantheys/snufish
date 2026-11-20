"""The compatibility rule of docs/compatibility.md: which spec versions a contribution may carry, and the changelog
every spec keeps."""

import datetime
import shutil
from pathlib import Path

import pytest

from snufish.contribution import load_contribution, validate
from snufish.spec import Spec, available_benchmarks, load_spec, parse_version

ROOT = Path(__file__).resolve().parents[1]
KINDS = {"initial", "patch", "minor", "major"}


def _spec(version, compatible=()):
    return Spec(id="toy", version=version, data={"compatible": list(compatible)}, path=Path("toy"))


def test_parse_version():
    assert parse_version("1.2.3") == (1, 2, 3)
    for bad in ("1.2", "1.2.3.4", "v1.2.3", "1.x.0", ""):
        with pytest.raises(ValueError):
            parse_version(bad)


def test_before_1_0_only_the_same_or_a_listed_version():
    spec = _spec("0.4.0", compatible=["0.3.0"])
    assert spec.accepts("0.4.0")
    assert spec.accepts("0.3.0")
    assert not spec.accepts("0.2.0")      # 0.x minors may break: only what the spec lists
    assert not spec.accepts("0.4.1")      # newer than the spec
    assert not spec.accepts("0.4")        # not a version


def test_from_1_0_the_same_major_up_to_the_current_version():
    spec = _spec("1.2.0", compatible=["0.3.0"])
    for ok in ("1.0.0", "1.1.5", "1.2.0", "0.3.0"):
        assert spec.accepts(ok), ok
    for bad in ("1.2.1", "1.3.0", "2.0.0", "0.4.0"):
        assert not spec.accepts(bad), bad
    assert not _spec("2.0.0").accepts("1.9.0")  # a major change invalidates the old major


@pytest.mark.parametrize("benchmark", available_benchmarks(ROOT))
def test_changelog(benchmark):
    spec = load_spec(benchmark, root=ROOT)
    log = spec["changelog"]
    versions = [parse_version(entry["version"]) for entry in log]
    assert versions == sorted(versions) and len(set(versions)) == len(versions), "changelog in increasing order"
    assert str(log[-1]["version"]) == spec.version, "the last changelog entry is the current version"
    assert log[0]["kind"] == "initial" and all(entry["kind"] in KINDS - {"initial"} for entry in log[1:])
    for entry in log:
        assert isinstance(entry["date"], (datetime.date, str)) and entry["changes"]
    listed = {str(entry["version"]) for entry in log}
    for version in spec.compatible:
        assert version in listed and parse_version(version) < parse_version(spec.version)
        # nothing listed as compatible may sit behind a major change
        later = [e for e in log if parse_version(e["version"]) > parse_version(version)]
        assert all(e["kind"] != "major" for e in later), f"{version} is behind a major change"


def test_validator_takes_a_compatible_version_and_rejects_others(tmp_path):
    spec = load_spec("B5_rates", root=ROOT)
    source = sorted((ROOT / "contributions" / "snowglobes" / "B5_rates").glob("*/meta.yaml"))[-1].parent
    target = tmp_path / "snowglobes" / "B5_rates" / source.name
    shutil.copytree(source, target)
    contribution = load_contribution(target)
    assert validate(contribution, spec) == []
    contribution.meta["benchmark_version"] = "0.4.0"   # before B5's major change of 0.5.0 (the 8B tail)
    assert any("does not accept" in p for p in validate(contribution, spec))
    listed = Spec(id=spec.id, version=spec.version, data={**spec.data, "compatible": ["0.4.0"]}, path=spec.path)
    assert validate(contribution, listed) == []
