import os
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))

from snufish import engine  # noqa: E402
from snufish.spec import pmns  # noqa: E402

APP = ROOT / "build" / "app"
DRIVER = ROOT / "contributions" / "nufast-earth" / "scripts" / "b3_driver"
needs_tables = pytest.mark.skipif(not (APP / "inputs.json").exists() or not DRIVER.exists(),
                                  reason="no app tables (snufish export-app) or NuFast-Earth driver")


class Vacuum:
    """Provider without matter effects: F_i = |U_ei|^2 by day, no regeneration by night."""

    def day(self, osc, solar_model, component, energies):
        return np.tile(np.abs(pmns(osc)[0]) ** 2, (len(energies), 1))

    def night(self, osc, earth_model, site):
        U2 = np.abs(pmns(osc)) ** 2
        return np.array([1.0, 20.0]), np.tile(U2[0], (2, 1))


@pytest.fixture(scope="module")
def inputs():
    from snufish.uncertainty import inputs

    return inputs()


def test_parameters_merge_set_and_custom(inputs):
    params = engine.parameters(inputs, "juno_2025", custom={"dm2_21_eV2": 6e-5})
    assert params["sin2_theta12"]["value"] == pytest.approx(0.3092)
    assert params["dm2_21_eV2"] == {"value": 6e-5, "error": [0.0, 0.0]}
    assert params["sin2_theta13"]["value"] == pytest.approx(0.02195)  # from the defaults


def test_vacuum_rates_have_no_day_night_and_scale_with_flux(inputs):
    params = engine.parameters(inputs, "juno_2025")
    setup = engine.Setup(components=("Be7", "B8"), detector="argon", recoil_threshold=0.0)
    per = engine.totals(engine.component_rates(inputs, Vacuum(), setup, engine.oscillation(params)))
    day, night = engine.combine(per, ["Be7", "B8"])
    assert night == pytest.approx(day, rel=1e-12)
    assert engine.quantity_value("adn", "day", day, night) == pytest.approx(0.0, abs=1e-12)
    doubled = engine.combine(per, ["Be7", "B8"], np.array([1.0, 2.0]))[0]
    assert doubled == pytest.approx(day + per["B8"]["day"])


def test_statistics_and_measured_flux(inputs):
    sigma = engine.statistical_sigma("rate", "annual", 100.0, 100.0, 4.0)
    assert sigma == pytest.approx(np.sqrt(400) / 4)  # 400 events in 4 kt yr
    draws = engine.sample_fluxes(inputs, np.random.default_rng(2), "bs05_op", ["B8"], 20000, b8_flux="sno_nc")
    assert np.std(draws) == pytest.approx(inputs["b8_measured"]["error"], rel=0.03)
    assert engine.sample_fluxes(inputs, np.random.default_rng(2), "bs05_op", ["B8"], 10) is None  # no errors


def test_budget_rows_keep_sampled_and_ranges_apart(inputs):
    params = engine.parameters(inputs, "juno_2025")
    setup = engine.Setup(detector="argon", channel="cc_nue_ar40", exposure=10.0)
    rows, samples = engine.budget(inputs, Vacuum(), setup, params, "rate", n=200, seed=3)
    kinds = {r["Source"]: r["Kind"] for r in rows}
    assert kinds["40Ar nuclear model"] == kinds["solar model"] == "model range"
    assert kinds["total sampled"] == kinds["statistics (10 kt yr)"] == "sampled"
    assert "Earth model" not in kinds  # daytime rate
    sigma = {r["Source"]: r["Sigma"] for r in rows}
    parts = [v for k, v in sigma.items() if kinds[k] == "sampled" and k != "total sampled"]
    assert sigma["total sampled"] == pytest.approx(np.sqrt(np.sum(np.square(parts))), rel=0.15)


@needs_tables
@pytest.mark.parametrize("set_name", ["juno_2025", "solar_global_2024"])
def test_tables_reproduce_exact_solvers(inputs, set_name):
    from snufish.export import ExactProbabilities

    tables, exact = engine.TableProbabilities(APP), ExactProbabilities()
    osc = engine.oscillation(engine.parameters(inputs, set_name, custom={"sin2_theta12": 0.3137}))  # off grid
    cases = [(engine.Setup(detector="argon", channel="cc_nue_ar40"), "rate", 1e-3),
             (engine.Setup(recoil_threshold=3.49), "rate", 1e-3),
             (engine.Setup(components=("pp", "Be7", "pep", "N13", "O15"), detector="argon"), "rate", 1e-3),
             # A_DN is a small difference: the night tables' interpolation in Delta m^2_21 leaves up to
             # ~1% of it (~3e-4 absolute, 1/30 of Super-K's error)
             (engine.Setup(recoil_threshold=3.49, site="Kamioka"), "adn", 1e-2),
             (engine.Setup(detector="argon", channel="cc_nue_ar40", site="SURF", earth_model="prem_four"), "adn",
              1e-2)]
    for setup, quantity, tolerance in cases:
        values = []
        for provider in (tables, exact):
            rates = engine.component_rates(inputs, provider, setup, osc, engine.needs_night(quantity, setup.period))
            per = engine.totals(rates)
            values.append(engine.quantity_value(quantity, setup.period, *engine.combine(per, list(setup.components))))
        assert values[0] == pytest.approx(values[1], rel=tolerance), (setup, quantity)
    assert tables.clamped == 0


@needs_tables
def test_table_budget_matches_exact_budget():
    from snufish.uncertainty import budget

    kwargs = dict(set_name="solar_global_2024", n=40, seed=5, quantities=["water_es_b8_t349", "kamioka_adn_es"])
    exact = budget(**kwargs)["Budget"].set_index(["Quantity", "Source"])
    table = budget(**kwargs, probabilities=engine.TableProbabilities(APP))["Budget"].set_index(["Quantity", "Source"])
    assert list(table.index) == list(exact.index)
    assert np.allclose(table.Central, exact.Central, rtol=5e-3)
    assert np.allclose(table.Relative, exact.Relative, rtol=0.03)
