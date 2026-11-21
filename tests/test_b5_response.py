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
    juno, lab = presets["juno"], RESPONSES["scintillator_lab"]
    assert juno["detector"] == "scintillator_lab" and juno["threshold"] == lab["threshold_MeV"]
    assert juno["res-a"] == lab["resolution"]["a"] and juno["res-b"] == lab["resolution"]["b"]
    assert [juno["unc-scale"], juno["unc-norm"]] == pytest.approx(
        [100 * lab["uncertainties"][k] for k in ("energy_scale", "normalisation")])


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
    juno = engine.published_response(inputs, "scintillator_lab")
    assert juno["resolution_a"] == 0.03 and juno["threshold"] == 2.0 and juno["efficiency"] == 1.0
    assert juno["energy_scale_error"] == 0.003 and juno["normalisation_error"] == 0.01
    assert engine.published_response(inputs, "no_such_detector") == {}


def _observed_contribution(tmp_path, values, response=None, mode="spec", quantity="argon/cc_nue_ar40/B8",
                           cross_sections=None):
    path = tmp_path / "toy" / "B5_rates" / "1.0"
    path.mkdir(parents=True)
    thresholds = SPEC.axis("threshold", "observed")
    records = [("observed", "b16_gs98", quantity, t, v) for t, v in zip(thresholds, values)]
    pd.DataFrame.from_records(records, columns=["grid", "variant", "quantity", "threshold", "value"]).to_parquet(
        path / "data.parquet", index=False)
    meta = dict(tool="toy", tool_version="1.0", tool_commit=None, benchmark="B5_rates", benchmark_version=SPEC.version,
                contributor="test", date="2026-11-07", command="test", license="CC-BY-4.0",
                settings=({} if mode is None else {"response": mode})
                | ({"cross_sections": cross_sections} if cross_sections else {}))
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


def test_marley_full_chain_matches_the_folding_of_its_tables():
    # MARLEY integrates its own cross sections over each oscillated spectrum; SNUfish folds its B4 tables (0.02 MeV)
    import numpy as np
    import pandas as pd
    import pytest

    from snufish.paths import build_dir

    path = build_dir() / "B5_Chain.parquet"
    if not path.exists():
        pytest.skip("run snufish build")
    chain = pd.read_parquet(path)
    marley = chain[(chain.Tool == "marley") & (chain.Rate > 0)]
    if marley.empty:
        pytest.skip("no MARLEY B5 contribution")
    assert set(marley.Channel) == {"es", "cc_nue_ar40"} and set(marley.Detector) == {"argon"}
    assert np.all(np.abs(marley.Ratio - 1) < 5e-4)


def _es_neutrino_response(width=0.1, swap=False):
    """A toy ES response of water in neutrino energy: per flavour, the tree-level recoil distribution of the bin
    centre on 0.1 MeV recoil bins (a perfect detector), full efficiency. ``swap``: nu_e's matrix given as nu_mu's."""
    from snufish.reference.xsec import es_above

    constants = load_spec("B4_xsec", root=ROOT)["constants"]
    true = np.round(np.arange(0.1, 20.0 + width / 2, width), 6)
    obs = np.round(np.arange(0.0, 20.0 + 0.05, 0.1), 6)
    rows = []
    for flavour in ("nue", "numu", "nutau"):
        shape = "nue" if (flavour == "nue") != swap else "numu"
        for lo, hi in zip(true[:-1], true[1:]):
            above = es_above(np.full(len(obs), 0.5 * (lo + hi)), shape, constants, obs)
            p = (above[:-1] - above[1:]) / above[0]
            rows += [("water", "es", "smearing", "neutrino", lo, hi, a, b, v, flavour)
                     for a, b, v in zip(obs[:-1], obs[1:], p) if v > 0]
    rows += [("water", "es", "efficiency", "observed", np.nan, np.nan, a, b, 1.0, "") for a, b in zip(obs[:-1], obs[1:])]
    return pd.DataFrame(rows, columns=["detector", "channel", "kind", "true_axis", "true_low", "true_high",
                                       "observed_low", "observed_high", "value", "flavour"])


def test_flavour_and_neutrino_energy_rows_are_validated(tmp_path):
    values = np.linspace(100.0, 0.0, 2001)

    def problems(name, table, quantity="water/es/B8"):
        return validate(_observed_contribution(tmp_path / name, values, table, "own", quantity), SPEC)

    good = _es_neutrino_response(width=1.0)
    assert problems("ok", good) == []
    assert problems("no_tau", good[good.flavour != "nutau"]) == []
    assert any("needs flavour nue and numu" in p for p in problems("no_mu", good[good.flavour != "numu"]))
    tau = good.copy()
    tau.loc[tau.flavour == "nutau", "value"] *= 0.5
    assert any("nutau matrix" in p for p in problems("tau", tau))
    odd = good.copy()
    odd.loc[odd.kind == "smearing", "flavour"] = odd.loc[odd.kind == "smearing", "flavour"].replace("nutau", "nux")
    assert any("flavour of water/es" in p for p in problems("odd", odd))
    cc = _gaussian_response().assign(flavour="nue")
    assert any("flavour applies to ES matrices" in p for p in problems("cc", cc, "argon/cc_nue_ar40/B8"))
    nc = _gaussian_response().assign(channel="nc_ar40", true_axis="neutrino")
    nc.loc[nc.kind == "efficiency", "true_axis"] = "observed"
    assert validate(_observed_contribution(tmp_path / "nc", values, nc, "own", "argon/nc_ar40/B8"), SPEC)


@needs_build
def test_es_matrix_in_neutrino_energy_is_folded_per_flavour():
    """A matrix in neutrino energy that is the recoil distribution itself gives the perfect detector's rates: exactly
    over all energies, and above a threshold up to the bias of evaluating each true bin at its centre, which falls
    with the bin width. The nu_e and nu_mu matrices are used for their own flavours."""
    averages = pd.read_parquet(build_dir() / "B2_Average.parquet")
    provider = build.AverageProbabilities(averages[averages.Tool == "snufish-reference"])
    inputs = build._engine_inputs()

    def above(table):
        setup = build.observed_setup(SPEC, inputs, "b16_gs98", "water", "es",
                                     None if table is None else build.response_tables(table, "water", "es"))
        setup = setup.replace(es_model="tree")   # the toy matrices are tree-level recoil distributions
        if table is None:
            setup = setup.replace(resolution_a=0.0, resolution_b=0.0, resolution_poly=(), efficiency=1.0,
                                  efficiency_table=None)
        return build.above(build.observed_spectra(SPEC, inputs, provider, setup)[1]["B8"])

    perfect = above(None)
    coarse, fine = above(_es_neutrino_response(0.2)), above(_es_neutrino_response(0.05))
    assert coarse[0] == pytest.approx(perfect[0], rel=1e-9) and fine[0] == pytest.approx(perfect[0], rel=1e-9)
    k = 500   # T > 5 MeV
    assert 0 < fine[k] / perfect[k] - 1 < 0.01 and fine[k] < coarse[k] < 1.02 * perfect[k]
    swapped = above(_es_neutrino_response(0.05, swap=True))
    assert swapped[k] / perfect[k] - 1 < -0.05   # nu_e's harder recoils given to the nu_mu and nu_tau


def test_cross_sections_of_the_folding():
    assert build.xsec_models({"tool": "snowglobes", "variant": "default"}, "es") == ("snowglobes", "default")
    assert build.xsec_models({"tool": "snufish-reference", "variant": "es_bks"}, "es") == ("bks", "default")
    assert build.xsec_models({"tool": "snufish-reference", "variant": "default"}, "es") == ("tree", "default")
    assert build.xsec_models({"tool": "snowglobes", "variant": "default"}, "cc_nue_ar40") == ("bks", "default")
    assert build.xsec_models({"tool": "marley", "variant": "ar40_marley1"}, "cc_nue_ar40") == ("bks", "ar40_marley1")
    assert build.xsec_models({"table": "reference/xsec/nakamura2002.yaml"}, "cc_nue_d") == ("bks", "default")
    for entry, channel in (("snowglobes", "es"), ({"tool": "marley", "variant": "default"}, "es"),
                           ({"tool": "marley", "variant": "default"}, "cc_nue_ar40"), ({"tool": "toy"}, "cc_nue_ar40")):
        with pytest.raises(ValueError):
            build.xsec_models(entry, channel)
    for channel in SPEC["response"]["cross_sections"]:   # the spec's own resolve
        build._xsec_model(SPEC, channel)
    stated = {"settings": {"cross_sections": {"es": {"tool": "snowglobes", "variant": "default"}}}}
    assert build.observed_cross_section(SPEC, stated, "es") == {"tool": "snowglobes", "variant": "default"}
    assert build.observed_cross_section(SPEC, stated, "cc_nue_ar40") == SPEC["response"]["cross_sections"]["cc_nue_ar40"]
    assert build.observed_cross_section(SPEC, None, "es") == SPEC["response"]["cross_sections"]["es"]


def test_stated_cross_sections_are_validated(tmp_path):
    values = np.linspace(100.0, 0.0, 2001)
    good = {"cc_nue_ar40": {"tool": "snowglobes", "variant": "default"}}
    assert validate(_observed_contribution(tmp_path / "a", values, cross_sections=good), SPEC) == []
    bad = {"cc_nue_ar40": "SNOwGLoBES's own"}
    assert any("settings.cross_sections" in p
               for p in validate(_observed_contribution(tmp_path / "b", values, cross_sections=bad), SPEC))
    # a channel the contribution gives no observed rates for is not checked (free text, as MARLEY's part 1)
    other = {"es": "MARLEY ES.react"}
    assert validate(_observed_contribution(tmp_path / "c", values, cross_sections=other), SPEC) == []


def test_rounded_rows_are_accepted(tmp_path):
    values = np.linspace(100.0, 0.0, 2001)
    rounded = _gaussian_response()
    rounded.loc[rounded.kind == "smearing", "value"] *= 1.0005   # rows up to 1 + 5e-4
    assert validate(_observed_contribution(tmp_path / "a", values, rounded, "own"), SPEC) == []
    over = _gaussian_response()
    over.loc[over.kind == "smearing", "value"] *= 1.01
    assert any("sum to more than 1" in p for p in validate(_observed_contribution(tmp_path / "b", values, over, "own"), SPEC))


@needs_build
def test_the_folding_takes_the_stated_cross_section(tmp_path):
    # the same contribution with SNOwGLoBES's CC table stated is folded through it, not through MARLEY 2 (the spec's)
    averages = pd.read_parquet(build_dir() / "B2_Average.parquet")
    provider = build.AverageProbabilities(averages[averages.Tool == "snufish-reference"])
    inputs = build._engine_inputs()
    stated = {"cc_nue_ar40": {"tool": "snowglobes", "variant": "default"}}
    setup = build.observed_setup(SPEC, inputs, "b16_gs98", "argon", "cc_nue_ar40",
                                 cross_section=stated["cc_nue_ar40"])
    expected = build.above(build.observed_spectra(SPEC, inputs, provider, setup)[1]["B8"])
    contribution = _observed_contribution(tmp_path, expected, cross_sections=stated)
    assert validate(contribution, SPEC) == []
    row = build._observed_chain([contribution], SPEC).iloc[0]
    assert row.CrossSection == "snowglobes: default" and row.RatioAbove == pytest.approx(1.0, rel=1e-12)
    spec_fold = build.above(build.observed_spectra(SPEC, inputs, provider, setup.replace(
        xsec_model="ar40_marley2_bhattacharya2009"))[1]["B8"])
    assert abs(expected[500] / spec_fold[500] - 1) > 0.01   # the two tables differ by more than the test resolves
