"""B5 night and annual totals (B5_DayNight), the BKS variant of the B4 reference, and the B1 registry checks."""

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))

from snufish import solar  # noqa: E402
from snufish.contribution import validate_ssm  # noqa: E402

DATA = ROOT / "build" / "data"
APP = ROOT / "build" / "app"
DRIVER = ROOT / "contributions" / "nufast-earth" / "scripts" / "b3_driver"
needs_build = pytest.mark.skipif(not (DATA / "B5_DayNight.parquet").exists(), reason="run snufish build first")
needs_solvers = pytest.mark.skipif(not (APP / "inputs.json").exists() or not DRIVER.exists(),
                                   reason="no app inputs (snufish export-app) or NuFast-Earth driver")


@pytest.fixture(scope="module")
def day_night():
    return pd.read_parquet(DATA / "B5_DayNight.parquet")


@needs_build
def test_day_column_is_the_daytime_total(day_night):
    totals = pd.read_parquet(DATA / "B5_Totals.parquet")
    keys = ["SolarModel", "Model", "Detector", "Channel", "Component"]
    merged = day_night.merge(totals, on=keys)
    assert len(merged) == len(day_night)
    assert np.allclose(merged.Day, merged.Total, rtol=1e-12)
    assert np.allclose(merged.DayAbove5, merged.Above5, rtol=1e-12)
    assert np.allclose(merged.Annual, 0.5 * (merged.Day + merged.Night), rtol=1e-12)


@needs_build
def test_no_night_effect_below_the_b3_grid(day_night):
    # pp and 7Be end below 1 MeV, where B3 has no grid: night = day
    low = day_night[day_night.Component.isin(["pp", "Be7"])]
    assert len(low) and np.allclose(low.Night, low.Day, rtol=1e-12)


@needs_build
def test_night_excess_where_matter_regenerates(day_night):
    b8 = day_night[(day_night.Component == "B8") & (day_night.Channel == "cc_nue_ar40") & (day_night.Day > 0)]
    assert (b8.ADN > 0.02).all() and (b8.ADN < 0.06).all()  # 8B nu_e CC: a few % night excess
    # ES dilutes it with the nu_mu,tau scattering
    es = day_night[(day_night.Component == "B8") & (day_night.Channel == "es")]
    assert (es.ADN > 0).all() and es.ADN.max() < b8.ADN.min()
    assert set(day_night.EarthModel) == {"prem_prob3", "prem_four", "prem_full"}


@needs_build
@needs_solvers
@pytest.mark.parametrize("detector, channel, model, choice, site, earth_model, component", [
    ("argon", "cc_nue_ar40", "snowglobes: ar40_marley", dict(xsec_model="ar40_marley"), "SURF", "prem_prob3", "B8"),
    ("water", "es", "snufish-reference: es_bks", dict(es_model="bks"), "Kamioka", "prem_prob3", "B8"),
    ("argon", "es", "snufish-reference: default", dict(es_model="tree"), "LNGS", "prem_prob3", "hep"),
    # continuous density: the engine's NuFast-Earth takes each region crossing's mean density, B5 the converged
    # B3 reference; they differ by that approximation (docs/crosschecks.md), here 0.2 %
    ("water", "es", "snufish-reference: es_bks", dict(es_model="bks"), "Kamioka", "prem_full", "B8"),
    ("argon", "es", "snufish-reference: default", dict(es_model="tree"), "LNGS", "prem_four", "hep"),
])
def test_night_matches_the_engine_with_the_exact_solvers(day_night, detector, channel, model, choice, site,
                                                         earth_model, component):
    """Independent folding (engine kernels) and probabilities (B2 solver and NuFast-Earth rerun, not the B3
    contribution grids) at the B2/B3 parameters, NuFIT 6.0."""
    exact = earth_model == "prem_prob3"  # both solvers exact on constant shells
    from snufish import engine
    from snufish.export import ExactProbabilities

    inputs = engine.Inputs.load(APP / "inputs.json")
    osc = engine.oscillation(engine.parameters(inputs, "nufit60_global"))
    row = day_night[(day_night.SolarModel == "b16_gs98") & (day_night.Model == model) & (day_night.Detector == detector)
                    & (day_night.Channel == channel) & (day_night.Site == site) & (day_night.EarthModel == earth_model)
                    & (day_night.Component == component)].iloc[0]
    setup = engine.Setup(solar_model="b16_gs98", components=(component,), detector=detector, channel=channel, site=site,
                         earth_model=earth_model, **choice)
    day, night, _ = engine.combine(engine.component_totals(inputs, ExactProbabilities(), setup, osc), [component])
    assert row.Day == pytest.approx(day, rel=1e-4)
    assert row.Night == pytest.approx(night, rel=1e-4 if exact else 1e-3)
    assert row.ADN == pytest.approx(2 * (night - day) / (night + day), rel=1e-3 if exact else 0.03)


def test_b4_reference_bks_variant():
    data = pd.read_parquet(ROOT / "contributions" / "snufish-reference" / "B4_xsec" / "0.1.0" / "data.parquet")
    wide = data.pivot_table(index=["quantity", "energy"], columns="variant", values="value")
    ratio = wide["es_bks"] / wide["default"]
    # against tree level with sin^2 theta_W = 0.23857: nu_e about -4 to -5 %, nu_mu,tau about +3 to +5 %
    assert ratio["es_nue"].between(0.95, 0.965).all()
    assert ratio["es_numu"].between(1.025, 1.05).all()
    assert np.allclose(ratio["es_numu"], ratio["es_nutau"])


def test_b1_registry_passes_its_checks():
    assert validate_ssm() == {name: [] for name in solar.models()}


def test_b1_checks_catch_a_broken_model(monkeypatch):
    registry = solar.models()
    name = "b23_gs98"
    broken = dict(registry[name], flux_correlation=(-np.eye(8)).tolist(), fluxes=dict(registry[name]["fluxes"], B8=0.0))
    monkeypatch.setattr(solar, "models", lambda: {name: broken})
    problems = validate_ssm()[name]
    assert any("B8" in p for p in problems)
    assert any("correlation" in p for p in problems)
