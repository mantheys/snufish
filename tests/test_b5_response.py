"""B5 part 2, the detector response: the calculator's presets follow the spec's published responses, contributions
in observed energy are validated (settings.response, response.parquet), and the comparison folds SNUfish's rates
through the response a contribution states."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))

from snufish import build, engine  # noqa: E402
from snufish.contribution import load_contribution, validate  # noqa: E402
from snufish.paths import build_dir  # noqa: E402
from snufish.spec import load_spec  # noqa: E402

SPEC = load_spec("B5_rates", root=ROOT)
RESPONSES = SPEC["response"]["detectors"]
needs_build = pytest.mark.skipif(not (build_dir() / "B4_Sigma.parquet").exists()
                                 or not (build_dir() / "B2_Average.parquet").exists(), reason="needs snufish build")


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_presets_follow_the_published_responses():
    script = "import('./web/checks.js').then((m) => console.log(JSON.stringify({ presets: m.PRESETS, res: m.RESOLUTIONS })))"
    out = json.loads(subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, check=True,
                                    capture_output=True, text=True).stdout)
    presets, resolutions = out["presets"], out["res"]
    sk, sno, dune = (presets[k] for k in ("sk4", "sno_salt", "dune"))
    water, heavy, argon = RESPONSES["water"], RESPONSES["heavy_water"], RESPONSES["argon"]
    assert resolutions[sk["res-model"]] == "water" and sk["eff-model"] == f"curve:{water['efficiency']['curve']}"
    assert sk["threshold"] == water["threshold_MeV"]
    assert [sk["unc-scale"], sk["unc-res"], sk["unc-norm"]] == pytest.approx(
        [100 * water["uncertainties"][k] for k in ("energy_scale", "resolution", "normalisation")])
    assert resolutions[sno["res-model"]] == "heavy_water" and sno["threshold"] == heavy["threshold_MeV"]
    assert [sno["unc-scale"], sno["unc-res"]] == pytest.approx(
        [100 * heavy["uncertainties"][k] for k in ("energy_scale", "resolution")])
    assert dune["threshold"] == argon["threshold_MeV"] and dune["res-b"] == pytest.approx(100 * argon["resolution"]["b"])
    assert presets["borexino"]["res-a"] == RESPONSES["scintillator_pc"]["resolution"]["a"]


def test_published_response_fields():
    from snufish.export import efficiency_curves

    inputs = engine.Inputs.__new__(engine.Inputs)
    inputs.data = {"responses": RESPONSES, "efficiency_curves": efficiency_curves()}
    sk = engine.published_response(inputs, "water")
    assert sk["resolution_poly"] == (-0.05525, 0.3162, 0.04572) and sk["resolution_energy"] == "total"
    assert sk["efficiency_table"].id == "curve:sk4_final" and sk["threshold"] == 3.49
    sno = engine.published_response(inputs, "heavy_water")
    assert sno["resolution_energy"] == "kinetic" and sno["efficiency"] == 1.0 and sno["energy_scale_error"] == 0.0115
    assert engine.published_response(inputs, "argon")["resolution_b"] == 0.2
    assert engine.published_response(inputs, "scintillator_lab") == {}


def _observed_contribution(tmp_path, values, response=None, mode="spec"):
    path = tmp_path / "toy" / "B5_rates" / "1.0"
    path.mkdir(parents=True)
    thresholds = SPEC.axis("threshold", "observed")
    records = [("observed", "b16_gs98", "argon/cc_nue_ar40/B8", t, v) for t, v in zip(thresholds, values)]
    pd.DataFrame.from_records(records, columns=["grid", "variant", "quantity", "threshold", "value"]).to_parquet(
        path / "data.parquet", index=False)
    meta = dict(tool="toy", tool_version="1.0", tool_commit=None, benchmark="B5_rates", benchmark_version=SPEC.version,
                contributor="test", date="2026-11-07", command="test", license="CC-BY-4.0",
                settings={} if mode is None else {"response": mode})
    (path / "meta.yaml").write_text(yaml.safe_dump(meta))
    if response is not None:
        response.to_parquet(path / "response.parquet", index=False)
    return load_contribution(path)


def _gaussian_response(sigma=0.5):
    """A toy response of argon CC: Gaussian rows on 0.5 MeV bins, 90 % efficiency above 4 MeV."""
    from math import erf

    edges = np.arange(0.0, 20.01, 0.5)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        c = 0.5 * (lo + hi)
        cdf = [0.5 * (1 + erf((e - c) / (sigma * np.sqrt(2)))) for e in edges]
        for k, (olo, ohi) in enumerate(zip(edges[:-1], edges[1:])):
            p = cdf[k + 1] - cdf[k]
            if p > 1e-9:
                rows.append(("argon", "cc_nue_ar40", "smearing", "observed", lo, hi, olo, ohi, p))
        rows.append(("argon", "cc_nue_ar40", "efficiency", "observed", np.nan, np.nan, lo, hi, 0.9 if lo >= 4 else 0.0))
    return pd.DataFrame(rows, columns=["detector", "channel", "kind", "true_axis", "true_low", "true_high",
                                       "observed_low", "observed_high", "value"])


def test_observed_contributions_state_their_response(tmp_path):
    values = np.linspace(100.0, 0.0, 2001)
    assert any("settings.response" in p for p in validate(_observed_contribution(tmp_path / "a", values, mode=None), SPEC))
    assert validate(_observed_contribution(tmp_path / "b", values), SPEC) == []
    assert any("response.parquet is missing" in p
               for p in validate(_observed_contribution(tmp_path / "c", values, mode="own"), SPEC))
    assert validate(_observed_contribution(tmp_path / "d", values, _gaussian_response(), "own"), SPEC) == []
    bad = _gaussian_response()
    bad.loc[bad.kind == "efficiency", "value"] = 1.5
    assert any("outside [0, 1]" in p for p in validate(_observed_contribution(tmp_path / "e", values, bad, "own"), SPEC))


@needs_build
def test_own_response_is_folded_for_the_comparison(tmp_path):
    response = _gaussian_response()
    averages = pd.read_parquet(build_dir() / "B2_Average.parquet")
    provider = build.AverageProbabilities(averages[averages.Tool == "snufish-reference"])
    inputs = build._engine_inputs()
    setup = build.observed_setup(SPEC, inputs, "b16_gs98", "argon", "cc_nue_ar40",
                                 build.response_tables(response, "argon", "cc_nue_ar40"))
    _, spectra = build.observed_spectra(SPEC, inputs, provider, setup)
    expected = build.above(spectra["B8"])
    contribution = _observed_contribution(tmp_path, 1.01 * expected, response, "own")
    assert validate(contribution, SPEC) == []
    row = build._observed_chain([contribution], SPEC).iloc[0]
    assert row.Response == "own" and row.RatioAbove == pytest.approx(1.01, rel=1e-12)
    # the toy response loses events below 4 MeV and 10 % above: below the perfect detector's rate above 5 MeV
    perfect = build.observed_setup(SPEC, inputs, "b16_gs98", "argon", "cc_nue_ar40",
                                   dict(resolution_a=0.0, resolution_b=0.0, efficiency=1.0, threshold=0.0))
    _, true = build.observed_spectra(SPEC, inputs, provider, perfect)
    k = 500  # 5 MeV
    assert 0.85 < expected[k] / build.above(true["B8"])[k] < 0.95
