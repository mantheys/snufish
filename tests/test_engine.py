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
    setup = engine.Setup(components=("Be7", "B8"), detector="argon", threshold=0.0)
    per = engine.totals(engine.observed_rates(inputs, Vacuum(), setup, engine.oscillation(params)))
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
             (engine.Setup(threshold=3.49), "rate", 1e-3),
             (engine.Setup(components=("pp", "Be7", "pep", "N13", "O15"), detector="argon"), "rate", 1e-3),
             # A_DN is a small difference: the night tables' interpolation in Delta m^2_21 leaves up to
             # ~1% of it (~3e-4 absolute, 1/30 of Super-K's error)
             (engine.Setup(threshold=3.49, site="Kamioka"), "adn", 1e-2),
             (engine.Setup(detector="argon", channel="cc_nue_ar40", site="SURF", earth_model="prem_four"), "adn",
              1e-2)]
    for setup, quantity, tolerance in cases:
        values = []
        for provider in (tables, exact):
            rates = engine.observed_rates(inputs, provider, setup, osc, engine.needs_night(quantity, setup.period))
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


def test_check_rejects_mismatched_options(inputs):
    with pytest.raises(ValueError, match="not available in water"):
        engine.check(inputs, engine.Setup(detector="water", channel="cc_nue_ar40"))
    with pytest.raises(ValueError, match="cross-section model"):
        engine.check(inputs, engine.Setup(detector="argon", channel="cc_nue_ar40", xsec_model="nope"))
    with pytest.raises(ValueError, match="at least one"):
        engine.check(inputs, engine.Setup(components=()))
    engine.check(inputs, engine.Setup(detector="argon", channel="cc_nue_ar40", xsec_model="ar40_marley"))


def test_spectra_sum_to_budget_draws(inputs):
    params = engine.parameters(inputs, "solar_global_2024")
    setup = engine.Setup(components=("Be7", "pep", "B8"), detector="argon")
    spec = engine.spectra(inputs, Vacuum(), setup, params, n=50, seed=4, night=False)
    rows, samples = engine.budget(inputs, Vacuum(), setup, params, "rate", n=50, seed=4, ranges=())
    assert spec["day"].sum() == pytest.approx(rows[0]["Central"], rel=1e-9)
    assert spec["draws_day"].sum(axis=1) == pytest.approx(samples["total sampled"], rel=1e-9)
    assert spec["components"]["Be7"]["day"].sum() > 0 and spec["night"] is None


def test_zero_asymmetry_has_no_relative_error(inputs):
    params = engine.parameters(inputs, "juno_2025")
    rows, _ = engine.budget(inputs, Vacuum(), engine.Setup(), params, "adn", n=20, ranges=())
    assert rows[0]["Central"] == pytest.approx(0, abs=1e-12) and np.isnan(rows[0]["Relative"])


def true_energy_total(inputs, provider, setup, osc):
    """The rate integrated over neutrino energy, as before the detector response
    existed: tree-level ES above the threshold, or the CC cross section."""
    from snufish.reference.xsec import es_above

    total = 0.0
    seconds, targets = inputs["seconds_per_year"], engine._targets(inputs, setup)
    for c, (pee, _) in engine.survival(inputs, provider, setup, osc, night=False).items():
        kind, energy, weight = inputs.components[c]
        if setup.channel == "es":
            s_e, s_x = (es_above(energy, f, inputs["constants"], setup.threshold) for f in ("nue", "numu"))
            f = pee * s_e + (1 - pee) * s_x
        else:
            f = pee * engine._kernels(inputs, setup, c, engine.observed_edges(setup.threshold)[0])
        values = targets * inputs.flux(setup.solar_model, c) * seconds * weight * f
        total += float(np.trapezoid(values, energy)) if kind == "continuum" else float(np.sum(values))
    return total


@pytest.mark.parametrize("changes", [
    dict(components=("pp", "Be7", "pep", "B8", "hep"), detector="argon", threshold=0.0),
    dict(threshold=3.49),
    dict(components=("Be7",), threshold=0.25),
    dict(detector="argon", channel="cc_nue_ar40", xsec_model="ar40_marley"),
    dict(channel="cc_nue_o16", components=("B8", "hep")),
])
def test_perfect_detector_reproduces_true_energy_rates(inputs, changes):
    setup = engine.Setup(**changes)
    osc = engine.oscillation(engine.parameters(inputs, "juno_2025"))
    observed = sum(v["day"] for v in engine.totals(engine.observed_rates(inputs, Vacuum(), setup, osc, False)).values())
    assert observed == pytest.approx(true_energy_total(inputs, Vacuum(), setup, osc), rel=1e-9)


def test_resolution_efficiency_and_threshold(inputs):
    osc = engine.oscillation(engine.parameters(inputs, "juno_2025"))

    def rate(**changes):
        setup = engine.Setup(detector="argon", channel="cc_nue_ar40", **changes)
        return engine.totals(engine.observed_rates(inputs, Vacuum(), setup, osc, False))["B8"]["day"]

    perfect = rate()
    assert rate(resolution_a=0.2, resolution_b=0.05) == pytest.approx(perfect, rel=1e-3)  # smearing keeps events
    assert rate(efficiency=0.8) == pytest.approx(0.8 * perfect, rel=1e-12)
    assert rate(efficiency_e50=5.0, efficiency_width=0.5) < rate(efficiency_e50=2.0, efficiency_width=0.5) < perfect
    assert rate(threshold=8.0) < rate(threshold=5.0) < perfect
    # smearing moves events across a threshold: above the spectrum's peak more leave than enter
    assert rate(threshold=8.0, resolution_a=0.3) != pytest.approx(rate(threshold=8.0), rel=1e-3)
    fine, display = engine.observed_edges(5.0)
    assert np.any(np.isclose(fine, 5.0)) and display[0] == 0 and display[-1] == pytest.approx(25.0)


def test_spectrum_is_in_observed_energy(inputs):
    params = engine.parameters(inputs, "juno_2025")
    es = engine.spectra(inputs, Vacuum(), engine.Setup(threshold=3.49), params, n=5, night=False)
    cc = engine.spectra(inputs, Vacuum(), engine.Setup(detector="argon", channel="cc_nue_ar40"), params, n=5, night=False)
    centres = np.sqrt(es["edges"][1:] * np.maximum(es["edges"][:-1], 1e-3))
    assert es["day"][centres < 3.3].sum() == 0 and es["day"].sum() > 0          # nothing below the threshold
    assert cc["day"][centres > 16.5 - 1.504 + 0.6].sum() == 0                   # 8B ends at ~16.5 MeV, minus Q
    assert es["observable"].startswith("Electron") and cc["observable"].startswith("Visible")


@pytest.mark.parametrize("changes", [
    dict(components=("pp", "Be7", "pep", "B8", "hep", "O15"), detector="argon", threshold=0.2, resolution_a=0.1),
    dict(threshold=3.49, resolution_a=0.45, resolution_b=0.02, efficiency=0.9, efficiency_e50=5.0),
    dict(detector="argon", channel="cc_nue_ar40", components=("B8", "hep"), threshold=4.0, resolution_a=0.3),
    dict(channel="cc_nue_o16", components=("B8", "hep")),
])
def test_fast_paths_match_the_reference(inputs, changes):
    setup = engine.Setup(**changes)
    osc = engine.oscillation(engine.parameters(inputs, "solar_global_2024"))
    reference = engine.observed_rates(inputs, Vacuum(), setup, osc)
    fast, spectra = engine.component_totals(inputs, Vacuum(), setup, osc), engine.component_spectra(inputs, Vacuum(), setup, osc)
    fine, display = engine.observed_edges(setup.threshold)
    for c, r in reference.items():
        for p in ("day", "night"):
            assert fast[c][p] == pytest.approx(r[p].sum(), rel=1e-10)
            assert spectra[c][p] == pytest.approx(engine.rebin(r[p], fine, display), rel=1e-9, abs=1e-12 * r[p].sum())
