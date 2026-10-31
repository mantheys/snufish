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
    from snufish.sections import EARTH_APPROXIMATIONS, SOLVER_APPROXIMATION

    data = json.loads(path.read_text())["observables"]
    adn = {r["source"]: r for r in data["water_es_adn"]["rows"] if r["section"] == "B3"}
    assert set(adn) == {*EARTH_APPROXIMATIONS.values(), SOLVER_APPROXIMATION}
    assert all(r["kind"] == "approximation" for r in adn.values())
    central = data["water_es_adn"]["central"]
    assert adn[EARTH_APPROXIMATIONS["prem_four"]]["shift"] / central > 0.2   # no crust: A_DN far too large
    assert abs(adn[SOLVER_APPROXIMATION]["shift"] / central) < 0.02
