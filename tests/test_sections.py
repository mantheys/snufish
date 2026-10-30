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
