import numpy as np

from snufish.scan import day_fractions, oscillation
from snufish.sections import SINGLE_DENSITY, ProductionTreatment, _section
from snufish.solar import electron_density


def test_own_profile_is_the_b2_average():
    osc, energies = oscillation("juno_2025"), np.array([1.0, 5.0, 15.0])
    for component in ("B8", "hep"):
        own = ProductionTreatment("own", None).day(osc, "b16_gs98", component, energies)
        assert np.allclose(own, day_fractions(osc, "b16_gs98", energies, component))


def test_treatments_move_hep_towards_the_core():
    # hep is produced further out than 8B: on 8B's profile, at the centre or at n_e = 66.7 its P_ee is lower
    osc, energies = oscillation("juno_2025"), np.array([10.0])
    ue2 = np.array([0.67, 0.31, 0.022])
    pee = {t: float((ProductionTreatment(t, None).day(osc, "b16_gs98", "hep", energies) @ ue2)[0])
           for t in ("own", "B8", "centre", "single")}
    assert pee["centre"] < pee["B8"] < pee["single"] < pee["own"]
    assert electron_density("b16_gs98", 0.0) > SINGLE_DENSITY


def test_every_budget_source_has_a_step():
    for source in ("oscillation parameters", "solar fluxes", "8B flux (solar model)", "solar model", "Earth model",
                   "40Ar nuclear model", "ES radiative corrections", "measured B(GT) (11 levels)"):
        assert _section(source) is not None
    assert _section("oscillation parameters") == "B1"  # the benchmarks are the calculator's steps
    assert _section("solar fluxes") == _section("solar model") == "B2"
    assert _section("total sampled") is None


def test_split_regions_thin_the_polynomial_regions_only():
    from snufish import crust
    from snufish.spec import load_spec

    regions = crust.regions("prem_crust1", "Kamioka")
    thin = crust.split(regions, 25.0)
    assert thin[-1]["outer_radius_km"] == regions[-1]["outer_radius_km"]
    assert {r["outer_radius_km"] for r in regions} <= {r["outer_radius_km"] for r in thin}  # borders kept
    inner = 0.0
    for r in thin:
        if len(r["coefficients"]) > 1:
            assert r["outer_radius_km"] - inner <= 25.0 + 1e-6
        inner = r["outer_radius_km"]
    shells = load_spec("B3_earth")["earth_models"]["prem_full"]["regions"][-3:]  # constant: left as they are
    assert crust.split(shells, 1.0)[-2:] == shells[-2:]


def test_b3_shows_its_approximations_on_night_observables():
    import json
    from pathlib import Path

    import pytest

    path = Path(__file__).resolve().parents[1] / "build" / "app" / "sections.json"
    if not path.exists():
        pytest.skip("run snufish export-sections")
    from snufish.sections import CRUST_PROXY, EARTH_LABELS, SOLVER_APPROXIMATION

    data = json.loads(path.read_text())["observables"]
    adn = {r["source"]: r for r in data["water_es_adn"]["rows"] if r["section"] == "B3"}
    assert set(EARTH_LABELS.values()) <= set(adn) <= {*EARTH_LABELS.values(), SOLVER_APPROXIMATION}
    assert all(r["kind"] == "approximation" for r in adn.values())
    assert [r["source"] for r in adn.values() if r.get("overview")] == [EARTH_LABELS[CRUST_PROXY]]
    central = data["water_es_adn"]["central"]
    assert adn[EARTH_LABELS["prem_four"]]["shift"] / central > 0.2   # no crust: A_DN far too large
    if SOLVER_APPROXIMATION in adn:  # written with the NuFast-Earth driver only
        assert abs(adn[SOLVER_APPROXIMATION]["shift"] / central) < 0.02


def test_tool_agreement_lists_every_tool_on_the_comparison_variant():
    # every contributed tool appears; on the spec's tool comparison (identical inputs) each agrees with the reference
    # within its own known differences (docs/crosschecks.md: PEANUTS's hard-coded matter potential, 1.2e-4 in B2)
    from snufish.contribution import find_contributions
    from snufish.sections import tool_agreement

    tools = tool_agreement()
    for benchmark, tolerance in (("B2_sun", 2e-4), ("B3_earth", 2e-5)):
        contributed = {p.parents[1].name for p in find_contributions(benchmark)} - {"snufish-reference"}
        rows = [r for r in tools[benchmark] if r["comparison"]]
        assert {r["tool"] for r in rows} == contributed
        assert all(r["max_abs"] < tolerance for r in rows)
    assert {r["quantity"] for r in tools["B4_xsec"]} == {"es_nue", "es_numu", "es_nutau"}
    assert all(r["max_rel"] < 0.01 for r in tools["B4_xsec"])  # ES with radiative corrections, SNOwGLoBES vs BKS
