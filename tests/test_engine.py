import os
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))

from snufish import engine  # noqa: E402
from snufish.spec import load_spec, pmns  # noqa: E402

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
    day, night, _ = engine.combine(per, ["Be7", "B8"])
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
    setup = engine.Setup(es_model="tree", **changes)
    osc = engine.oscillation(engine.parameters(inputs, "juno_2025"))
    observed = sum(v["day"] for v in engine.totals(engine.observed_rates(inputs, Vacuum(), setup, osc, False)).values())
    assert observed == pytest.approx(true_energy_total(inputs, Vacuum(), setup, osc), rel=1e-9)


def test_resolution_efficiency_and_threshold(inputs):
    osc = engine.oscillation(engine.parameters(inputs, "juno_2025"))

    def rate(**changes):
        setup = engine.Setup(detector="argon", channel="cc_nue_ar40", **changes)
        return engine.totals(engine.observed_rates(inputs, Vacuum(), setup, osc, False))["B8"]["day"]

    perfect = rate()
    assert rate(resolution_a=0.2, resolution_b=0.05) == pytest.approx(perfect, rel=1e-9)  # smearing keeps events
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


SK_IV = dict(threshold=3.49, resolution_poly=(-0.05525, 0.3162, 0.04572))  # arXiv:2312.12907, eq. 9


def test_energy_scale_and_super_k_resolution(inputs):
    osc = engine.oscillation(engine.parameters(inputs, "juno_2025"))

    def rate(**changes):
        return engine.totals(engine.observed_rates(inputs, Vacuum(), engine.Setup(**changes), osc, False))["B8"]["day"]

    base = rate(threshold=3.49)
    # a higher energy scale moves events up across the threshold; the shift is small and smooth
    up, down = rate(threshold=3.49, energy_scale=1.005), rate(threshold=3.49, energy_scale=0.995)
    assert down < base < up and (up - down) / base == pytest.approx(0.0096, abs=0.002)  # ~1 % per 1 % of scale
    assert rate(threshold=0.0, energy_scale=1.02) == pytest.approx(rate(threshold=0.0), rel=1e-6)  # no threshold: no change
    sk = rate(**SK_IV)
    sigma = engine.resolution(inputs, engine.Setup(**SK_IV), np.array([3.49, 10.0 - 0.511]))
    assert sigma == pytest.approx([-0.05525 + 0.3162 * 2 + 0.04572 * 4.001, -0.05525 + 0.3162 * 10 ** 0.5 + 0.4572], rel=1e-3)
    # Super-K's sigma grows with energy (0.76 MeV at the threshold, 0.4 MeV at 1 MeV): more events spread down
    # across the threshold than up, though the recoil spectrum falls; the rate above it drops by ~1.5 %
    assert sk == pytest.approx(0.985 * base, rel=0.005)
    assert rate(resolution_poly=SK_IV["resolution_poly"]) == pytest.approx(rate(), rel=1e-9)  # smearing keeps every event


def test_detector_uncertainties_in_the_budget(inputs):
    params = engine.parameters(inputs, "juno_2025")
    setup = engine.Setup(**SK_IV, energy_scale_error=0.0048, resolution_error=0.03, normalisation_error=0.011)
    rows, _ = engine.budget(inputs, Vacuum(), setup, params, "rate", n=300, ranges=())
    sigma = {r["Source"]: r["Relative"] for r in rows}
    assert sigma["detector normalisation (±1.1 %)"] == pytest.approx(0.011, rel=0.15)
    assert 0 < sigma["energy scale (±0.48 %)"] < 0.02 and 0 < sigma["energy resolution (±3 %)"] < 0.02
    rows, _ = engine.budget(inputs, Vacuum(), setup, params, "adn", n=50, ranges=())
    assert not any("normalisation" in r["Source"] for r in rows)  # cancels in the asymmetry



def gaussian_table(inputs, setup, true_edges, obs_edges):
    """A smearing matrix built like an experiment would publish one, from the engine's own resolution."""
    rows = []
    for lo, hi in zip(true_edges[:-1], true_edges[1:]):
        c = 0.5 * (lo + hi)
        sigma = float(engine.resolution(inputs, setup, [c])[0])
        cdf = [0.5 * (1 + __import__("math").erf((e - c) / sigma / 2 ** 0.5)) for e in obs_edges]
        rows.append(tuple(np.diff(cdf)))
    return engine.Table("gauss", tuple(true_edges), tuple(obs_edges), tuple(rows))


def test_imported_response(inputs):
    osc = engine.oscillation(engine.parameters(inputs, "juno_2025"))

    def rate(**changes):
        return engine.totals(engine.observed_rates(inputs, Vacuum(), engine.Setup(**changes), osc, False))["B8"]["day"]

    grid = np.arange(0.0, 25.01, 0.25)
    identity = engine.Table("identity", tuple(grid), tuple(grid), tuple(map(tuple, np.eye(len(grid) - 1))))
    assert rate(smearing_table=identity) == pytest.approx(rate(), rel=1e-9)            # keeps every event
    flat = engine.Table("flat", (0.0, 30.0), (0.8, 0.8))
    assert rate(threshold=3.49, efficiency_table=flat) == pytest.approx(0.8 * rate(threshold=3.49), rel=1e-12)
    sk = engine.Setup(threshold=3.49, resolution_poly=(-0.05525, 0.3162, 0.04572))
    table = gaussian_table(inputs, sk, grid, grid)
    assert rate(threshold=3.49, smearing_table=table) == pytest.approx(rate(**{**sk.__dict__}), rel=0.01)
    # a CC matrix in neutrino energy is shifted by Q
    cc = dict(detector="argon", channel="cc_nue_ar40")
    shifted = engine.Table("nu", tuple(grid + 1.504), tuple(grid), tuple(map(tuple, np.eye(len(grid) - 1))), "neutrino")
    assert rate(**cc, smearing_table=shifted) == pytest.approx(rate(**cc), rel=1e-9)
    with pytest.raises(ValueError, match="CC channels only"):
        engine.check(inputs, engine.Setup(smearing_table=shifted))


def test_electron_alone_drops_the_level_energy(inputs):
    osc = engine.oscillation(engine.parameters(inputs, "juno_2025"))
    marley = "ar40_marley2_bhattacharya2009"
    cc = dict(detector="argon", channel="cc_nue_ar40", xsec_model=marley)

    def rate(**changes):
        return engine.totals(engine.observed_rates(inputs, Vacuum(), engine.Setup(**cc, **changes), osc, False))["B8"]["day"]

    table = engine.electron_smearing(inputs, "cc_nue_ar40", marley, 0.0)
    xsec = inputs["xsec"]["cc_nue_ar40"][marley]
    centres = 0.5 * (np.array(table.x[1:]) + np.array(table.x[:-1]))
    open_ = np.interp(centres, xsec["energy"], xsec["sigma"], left=0.0) > 0
    assert np.allclose(np.sum(table.matrix, axis=1)[open_], 1, atol=2e-3)   # every event goes somewhere
    assert rate(smearing_table=table) == pytest.approx(rate(), rel=1e-3)
    # the 2.3-6.1 MeV of the 40K level is lost: about half the events above 5 MeV remain
    assert 0.4 < rate(threshold=5.0, smearing_table=table) / rate(threshold=5.0) < 0.6



def with_levels(inputs, shifts):
    """A copy of the inputs with synthetic B(GT)-shifted tables of the default argon CC model."""
    data = dict(inputs.data, xsec={k: dict(v) for k, v in inputs.data["xsec"].items()})
    base = data["xsec"]["cc_nue_ar40"]["default"]
    entries = []
    for n, factor in enumerate(shifts, 1):
        name = f"default#bgt{n}"
        data["xsec"]["cc_nue_ar40"][name] = {"energy": base["energy"], "sigma": [factor * v for v in base["sigma"]]}
        entries.append({"name": name})
    data["xsec_levels"] = {"cc_nue_ar40": {"default": entries}}
    return engine.Inputs(data)


def test_measured_strengths_propagate_in_quadrature(inputs):
    shifted = with_levels(inputs, [1.01, 1.02])  # two "levels" raising sigma by 1 % and 2 %
    assert "default#bgt1" not in shifted.xsec_models("cc_nue_ar40")
    params = engine.parameters(inputs, "juno_2025")
    setup = engine.Setup(detector="argon", channel="cc_nue_ar40")
    central = engine.budget(shifted, Vacuum(), setup, params, "rate", n=20, ranges=())[0][0]["Central"]
    [(source, sigma)] = engine.level_sigmas(shifted, Vacuum(), setup, params, "rate", central, False)
    assert source == "measured B(GT) (2 levels)" and sigma / central == pytest.approx(np.hypot(0.01, 0.02), rel=1e-9)
    rows, _ = engine.budget(shifted, Vacuum(), setup, params, "rate", n=20, ranges=())
    assert any(r["Source"] == source for r in rows)  # sampled in the budget
    assert "measured B(GT)" not in str(engine.budget(inputs, Vacuum(), setup, params, "rate", n=5, ranges=())[0])


def test_incomplete_tables_stay_out_of_the_model_range(inputs):
    data = dict(inputs.data, xsec_incomplete={"cc_nue_ar40": ["ar40_marley", "ar40_marley1"]})
    options = engine.alternatives(engine.Inputs(data), engine.Setup(detector="argon", channel="cc_nue_ar40"), "xsec_model",
                                  scope="all")
    assert "ar40_marley" not in options and "ar40_klmv" in options


def test_model_ranges_compare_the_state_of_the_art_only(inputs):
    """reference/status.yaml: ranges run over the current models; legacy ones and approximations are selectable,
    and their spread is reported apart ("legacy spread") on request."""
    argon, water = engine.Setup(detector="argon", channel="cc_nue_ar40"), engine.Setup(threshold=3.49)
    assert set(engine.alternatives(inputs, argon, "xsec_model")) == {
        "ar40_marley2_bhattacharya2009", "ar40_marley2_liu1998", "ar40_marley2_bhattacharya1998", "ar40_ksz2018"}
    assert set(engine.alternatives(inputs, argon, "solar_model")) == {"b23_mb22m", "b23_mb22p", "b23_aag21"}
    assert engine.alternatives(inputs, water, "earth_model") == ["prem_crust1"]
    assert engine.alternatives(inputs, water, "es_model") == ["bks", "snowglobes"]
    assert "tree" in engine.alternatives(inputs, water, "es_model", scope="all")
    assert engine.status(inputs, "solar_model", "b16_gs98")["superseded_by"] == "b23_mb22m"
    assert engine.status(inputs, "parameter_set", "nufit61_global")["status"] == "current"
    assert engine.status(inputs, "earth_model", "prem_prob3")["status"] == "approximation"
    assert engine.status(inputs, "solar_model", "no_such_model")["status"] == "current"  # unlisted
    legacy = engine.Setup(detector="argon", channel="cc_nue_ar40", solar_model="b16_gs98", xsec_model="ar40_klmv",
                          earth_model="prem_prob3", period="night")
    found = {c["category"]: c["status"] for c in engine.not_current(inputs, legacy, "rate", "kamland_2013")}
    assert found == {"parameter_set": "legacy", "solar_model": "legacy", "earth_model": "approximation",
                     "xsec_model": "legacy"}
    by_day = engine.not_current(inputs, legacy.replace(period="day"), "rate")
    assert "earth_model" not in {c["category"] for c in by_day}  # the Earth does not enter by day
    assert engine.not_current(inputs, engine.Setup(solar_model="b23_mb22m"), "rate", "juno_2025") == []
    params = engine.parameters(inputs, "juno_2025")
    rows, _ = engine.budget(inputs, Vacuum(), argon, params, "rate", n=5, legacy=True)
    current = {r["Source"]: r for r in rows if r["Kind"] == "model range"}
    spread = {r["Source"]: r for r in rows if r["Kind"] == "legacy spread"}
    assert {"40Ar nuclear model", "solar model"} <= set(current) and set(spread) == set(current)
    for source in current:
        assert spread[source]["Low"] <= current[source]["Low"] and spread[source]["High"] >= current[source]["High"]
    assert not [r for r in engine.budget(inputs, Vacuum(), argon, params, "rate", n=5)[0] if r["Kind"] == "legacy spread"]


@needs_tables
def test_against_published_experiment_predictions():
    """Borexino's B16-GS98 predictions (arXiv:1707.09279, table II) and JUNO's 8B rate (arXiv:2006.11760)."""
    inputs, tables = engine.Inputs.load(APP / "inputs.json"), engine.TableProbabilities(APP)
    per_100t_day = 0.1 * 86400 / inputs["seconds_per_year"]
    osc = engine.oscillation(engine.parameters(inputs, "nufit60_global"))
    for component, published in (("pp", 131.1), ("Be7", 47.9), ("pep", 2.74)):
        setup = engine.Setup(solar_model="b16_gs98", components=(component,), detector="scintillator_pc", site="LNGS",
                             period="annual")
        per = engine.component_totals(inputs, tables, setup, osc)[component]
        rate = 0.5 * (per["day"] + per["night"]) * per_100t_day
        assert rate / published == pytest.approx(1.0, abs=0.01), component  # with BKS radiative corrections
    osc = engine.oscillation(engine.parameters(inputs, "nufit60_global", custom={"dm2_21_eV2": 7.5e-5}))
    setup = engine.Setup(components=("B8", "hep"), b8_flux="sno_nc", detector="scintillator_lab", site="Jiangmen")
    day, night, _ = engine.combine(engine.component_totals(inputs, tables, setup, osc), ["B8", "hep"])
    assert 0.5 * (day + night) / 365.25 == pytest.approx(4.36, rel=0.03)  # counts per day per kt, all energies


def test_bks_radiative_corrections_against_the_paper():
    """Total cross sections of BKS 1995 table VII (1e-46 cm^2) and the 0.384 MeV line's recoil spectrum (table II)."""
    from snufish.reference import radiative

    c = load_spec("B4_xsec")["constants"]
    q = np.array([0.384, 0.862, 1.0, 2.0, 5.0, 10.0, 20.0])
    for flavour, table in (("nue", [19.2, 57.9, 69.8, 159, 435, 896, 1820]), ("numu", [5.09, 12.8, 15.0, 31.1, 78.7, 158, 316])):
        assert radiative.es_above(q, flavour, c, [0.0])[:, 0] / 1e-46 == pytest.approx(table, rel=6e-3)
    T = np.array([0.0023, 0.1153, 0.2260])
    for flavour, table in (("nue", [5.1591, 4.3232, 3.5812]), ("numu", [4.3716, 4.2830, 4.4966])):
        p = radiative.es_differential(0.384, T, flavour, c) / radiative.es_above([0.384], flavour, c, [0.0])[0, 0]
        assert p == pytest.approx(table, rel=3e-3)


@pytest.mark.parametrize("threshold", [0.0, 0.25, 3.49])
def test_bks_engine_matches_direct_integration(inputs, threshold):
    """The engine's interpolated BKS kernels against the direct integral above threshold."""
    from snufish.reference import radiative

    osc = engine.oscillation(engine.parameters(inputs, "juno_2025"))
    setup = engine.Setup(components=("Be7", "B8"), threshold=threshold)
    totals = engine.totals(engine.observed_rates(inputs, Vacuum(), setup, osc, False))
    me = inputs["constants"]["m_e_MeV"]
    for c, (pee, _) in engine.survival(inputs, Vacuum(), setup, osc, night=False).items():
        kind, energy, weight = inputs.components[c]
        t_max = 2 * energy**2 / (me + 2 * energy)
        s = [np.array([radiative.es_above([e], f, inputs["constants"], [min(threshold / t, 1.0)])[0, 0]
                       for e, t in zip(energy, t_max)]) for f in ("nue", "numu")]
        values = engine._targets(inputs, setup) * inputs.flux(setup.solar_model, c) * inputs["seconds_per_year"] \
            * weight * (pee * s[0] + (1 - pee) * s[1])
        direct = float(np.trapezoid(values, energy)) if kind == "continuum" else float(np.sum(values))
        assert totals[c]["day"] == pytest.approx(direct, rel=1e-3), c


@needs_tables
def test_against_super_k_iv_and_sno():
    """Super-K IV with its fig. 28 efficiency (arXiv:2312.12907): the energy-scale effect (table IV: 0.8 %) and the
    65,443 extracted events; SNO salt phi_CC/phi_NC (nucl-ex/0502021); NC is flavour-blind."""
    inputs, tables = engine.Inputs.load(APP / "inputs.json"), engine.TableProbabilities(APP)
    curve = inputs["efficiency_curves"]["sk4_final"]
    sk = engine.Setup(components=("B8", "hep"), b8_flux="sno_nc", threshold=3.49, resolution_poly=(-0.05525, 0.3162, 0.04572),
                      energy_scale_error=0.0048, efficiency_table=engine.Table("sk4", tuple(curve["x"]), tuple(curve["y"])),
                      period="annual")
    params = engine.parameters(inputs, "solar_global_2024")
    central = engine.quantity_value("rate", "annual", *engine.combine(
        engine.component_totals(inputs, tables, sk, engine.oscillation(params)), ["B8", "hep"]))
    (_, shift), = engine.detector_sigmas(inputs, tables, sk, params, "rate", central, True)
    assert shift / central == pytest.approx(0.008, abs=0.0005)  # without the efficiency: 0.48 %
    events = central * 22.5 * 2970 / 365.25
    assert events == pytest.approx(65443, rel=0.03)  # the SNO NC flux alone is known to 3.8 %
    params = engine.parameters(inputs, "nufit60_global")
    sno = dict(components=("B8", "hep"), b8_flux="sno_nc", detector="heavy_water", site="SNOLAB", threshold=5.5, period="annual")
    rows, _ = engine.budget(inputs, tables, engine.Setup(channel="cc_nue_d", **sno), params, "ratio", n=50)
    assert rows[0]["Central"] == pytest.approx(0.340, abs=0.038)
    rows, _ = engine.budget(inputs, tables, engine.Setup(channel="nc_d", **sno), params, "ratio", n=10)
    assert rows[0]["Central"] == pytest.approx(1.0, abs=1e-12)


@needs_tables
def test_tables_follow_theta13():
    """The app tables are made at one theta13; the nu_3-decoupling rescaling keeps them on the exact solvers."""
    from snufish.export import ExactProbabilities

    inputs, tables, exact = engine.Inputs.load(APP / "inputs.json"), engine.TableProbabilities(APP), ExactProbabilities()
    setup = engine.Setup(components=("B8",), threshold=4.49, site="Kamioka")
    for s13 in (0.015, 0.03):
        osc = engine.oscillation(engine.parameters(inputs, "nufit60_global", custom={"sin2_theta13": s13}))
        (d, n, _), (d0, n0, _) = (engine.combine(engine.component_totals(inputs, p, setup, osc), ["B8"]) for p in (tables, exact))
        assert d == pytest.approx(d0, rel=1e-3)
        assert 2 * (n - d) / (n + d) == pytest.approx(2 * (n0 - d0) / (n0 + d0), rel=0.025)  # tables: ~1 % at any theta13


def test_orbit_scales_day_and_night(inputs):
    params = engine.parameters(inputs, "juno_2025")
    setup = engine.Setup(components=("B8",), detector="argon", site="SURF")
    osc = engine.oscillation(params)
    plain = engine.component_totals(inputs, Vacuum(), setup, osc)["B8"]
    orbit = engine.component_totals(inputs, Vacuum(), setup.replace(orbit=True), osc)["B8"]
    g_day, g_night = engine.orbital(inputs, setup.replace(orbit=True))
    assert orbit["day"] == pytest.approx(g_day * plain["day"]) and orbit["night"] == pytest.approx(g_night * plain["night"])
    reference = engine.totals(engine.observed_rates(inputs, Vacuum(), setup.replace(orbit=True), osc))["B8"]
    assert reference["day"] == pytest.approx(orbit["day"], rel=1e-9)
    # without matter effects the whole asymmetry is the Earth-Sun distance's: ~0.9 % at SURF
    adn = engine.quantity_value("adn", "day", orbit["day"], orbit["night"])
    assert adn == pytest.approx(2 * (g_night - g_day) / (g_night + g_day)) and 0.008 < adn < 0.01
    with pytest.raises(ValueError, match="Earth-Sun distance"):
        engine.check(inputs, setup.replace(orbit=True), "ratio")
