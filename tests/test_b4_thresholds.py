"""B4 0.2.0: nu-e elastic scattering above the B5 responses' recoil thresholds, sigma(E; T > T_min), in the
reference (tree level and BKS), and the validator changes that came with it (a variant's quantities are the ones it
may give; the nu_e > nu_mu, nu_tau ordering per threshold)."""

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))

from snufish import engine  # noqa: E402
from snufish.contribution import _check_b4, load_contribution, validate, write_contribution  # noqa: E402
from snufish.reference import xsec  # noqa: E402
from snufish.reference.radiative import ratio_table  # noqa: E402
from snufish.spec import load_spec  # noqa: E402

SPEC = load_spec("B4_xsec", root=ROOT)
C = SPEC["constants"]
REFERENCE = ROOT / "contributions" / "snufish-reference" / "B4_xsec" / "0.1.0"
B5_THRESHOLDS = {d["threshold_MeV"] for d in load_spec("B5_rates", root=ROOT)["response"]["detectors"].values()}


@pytest.fixture(scope="module")
def reference():
    data = pd.read_parquet(REFERENCE / "data.parquet")
    return data.pivot_table(index="energy", columns=["variant", "quantity"], values="value")


def t_max(energy):
    return 2 * energy**2 / (C["m_e_MeV"] + 2 * energy)


def test_thresholds_are_the_b5_responses():
    thresholds = xsec.thresholds(SPEC)
    assert len(thresholds) == 15
    assert sorted({t for _, t in thresholds.values()}) == [0.05, 2.0, 3.49, 5.0, 5.5]
    assert B5_THRESHOLDS <= {t for _, t in thresholds.values()}


def test_tree_level_at_zero_threshold_is_the_total():
    energy = np.geomspace(0.05, 20, 50)
    for flavour in ("nue", "numu"):
        assert np.allclose(xsec.es_above(energy, flavour, C, 0.0), xsec.es_total(energy, flavour, C), rtol=1e-12)


def test_reference_gives_every_threshold_and_is_valid(reference):
    assert validate(load_contribution(REFERENCE)) == []
    for variant in ("default", "es_bks"):
        assert set(reference[variant].columns) == {"es_nue", "es_numu", "es_nutau", *xsec.thresholds(SPEC)}


def test_reference_vanishes_below_threshold_and_falls_with_it(reference):
    energy = reference.index.to_numpy()
    for variant in ("default", "es_bks"):
        for flavour in ("nue", "numu", "nutau"):
            previous = reference[variant][f"es_{flavour}"].to_numpy()
            for t in (0.05, 2.0, 3.49, 5.0, 5.5):
                sigma = reference[variant][f"es_{flavour}_T{t}"].to_numpy()
                below = t_max(energy) <= t
                assert (sigma[below] == 0).all() and (sigma[~below] > 0).all()
                assert (sigma <= previous * (1 + 1e-12)).all()
                previous = sigma


def test_bks_above_threshold_matches_the_engine_table(reference):
    """The engine (and the page) take the BKS correction above a threshold as tree level times an interpolated
    ratio table; the reference integrates it directly. They agree where the cross section is not tiny."""
    class Inputs(dict):
        data = {"es_bks": ratio_table(C)}

    inputs = Inputs(constants=C)
    energy = reference.index.to_numpy()
    for flavour in ("nue", "numu"):
        for t in (2.0, 5.0):
            keep = t_max(energy) > 1.2 * t
            e = energy[keep]
            table = np.array([engine.bks_ratio(inputs, flavour, [x], [t])[0, 0] for x in e])
            direct = reference["es_bks"][f"es_{flavour}_T{t}"].to_numpy()[keep]
            tree = reference["default"][f"es_{flavour}_T{t}"].to_numpy()[keep]
            assert np.abs(table * tree / direct - 1).max() < 1e-4  # 2.2e-5 at most


def test_ordering_holds_above_each_threshold(reference):
    for variant in ("default", "es_bks"):
        for t in (0.05, 2.0, 3.49, 5.0, 5.5):
            nue, numu = (reference[variant][f"es_{f}_T{t}"] for f in ("nue", "numu"))
            above = nue > 0
            assert (nue[above] > numu[above]).all()


def _records(quantities, swap=False):
    energy = SPEC.axis("energy")
    out = []
    for name in quantities:
        flavour, t = xsec.thresholds(SPEC).get(name, (name[3:], 0.0))
        if swap and name.startswith("es_nue"):
            flavour = "numu"
        elif swap and name.startswith("es_numu"):
            flavour = "nue"
        out += [("map", "default", name, e, s) for e, s in zip(energy, xsec.es_above(energy, flavour, C, t))]
    return out


def _contribution(tmp_path, records, variant="default"):
    meta = {"tool": "tool", "tool_version": "1.0", "tool_commit": None, "benchmark": "B4_xsec",
            "benchmark_version": "0.1.0", "contributor": "test", "date": "2026-11-21", "command": "test",
            "settings": {}, "license": "CC-BY-4.0"}
    records = [(g, variant, q, e, v) for g, _, q, e, v in records]
    if variant != "default":  # the required default
        records += [("map", "default", q, e, v) for g, _, q, e, v in records if q == "es_nue"]
    path = tmp_path / "tool" / "B4_xsec" / "1.0"
    write_contribution(path, meta, records, SPEC)
    return load_contribution(path)


def test_a_variant_may_give_part_of_its_quantities(tmp_path):
    """0.1.0 contributions stay valid (es_bks with its three channels), and es_bks with fewer is valid too."""
    assert validate(_contribution(tmp_path / "a", _records(["es_nue", "es_numu"]), "es_bks")) == []
    assert validate(_contribution(tmp_path / "b", _records(["es_nue", "es_numu", "es_nutau"]), "es_bks")) == []
    cc = [("map", "es_bks", "cc_nue_ar40", e, 1e-42) for e in SPEC.axis("energy")]
    problems = validate(_contribution(tmp_path / "c", _records(["es_nue"]) + cc, "es_bks"))
    assert any("not among" in p for p in problems)


def test_ordering_check_skips_zeros_and_catches_a_swap():
    names = ["es_nue_T5.0", "es_numu_T5.0", "es_nutau_T5.0"]
    df = pd.DataFrame.from_records(_records(names), columns=["grid", "variant", "quantity", "energy", "value"])
    assert (df.value == 0).any() and _check_b4(df, SPEC) == []
    swapped = pd.DataFrame.from_records(_records(names, swap=True), columns=df.columns)
    problems = _check_b4(swapped, SPEC)
    assert [p.split(" at ")[0] for p in problems] == ["es_nue_T5.0 <= es_numu_T5.0", "es_nue_T5.0 <= es_nutau_T5.0"]
