"""Options for reproducing rate tables in the conventions of DUNE solar analyses (SOLAR, SNOwGLoBES):
the night share of the exposure, a cut in true neutrino energy, and NC on 40Ar."""

import os
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))

from snufish import engine  # noqa: E402
from snufish.spec import pmns  # noqa: E402


class DayNight:
    """Vacuum by day; by night every mass state arrives as 20 % more nu_e-like (a toy regeneration)."""

    def day(self, osc, solar_model, component, energies):
        return np.tile(np.abs(pmns(osc)[0]) ** 2, (len(energies), 1))

    def night(self, osc, earth_model, site):
        U2 = np.abs(pmns(osc)) ** 2
        return np.array([0.1, 30.0]), np.tile(np.clip(1.2 * U2[0], 0, 1), (2, 1))


@pytest.fixture(scope="module")
def inputs():
    from snufish.uncertainty import inputs

    return inputs()


@pytest.fixture(scope="module")
def osc(inputs):
    return engine.oscillation(engine.parameters(inputs, "nufit60_global"))


ARGON = dict(solar_model="b16_gs98", detector="argon", site="SURF", components=("B8", "hep"))


def rate(inputs, setup, osc, quantity="rate"):
    per = engine.component_totals(inputs, DayNight(), setup, osc, night=True)
    return engine.quantity_value(quantity, setup.period, *engine.combine(per, list(setup.components)),
                                 night_fraction=setup.night_fraction)


# ---------------------------------------------------------------- night share of the exposure

def test_night_fraction_weights_the_annual_rate(inputs, osc):
    s = engine.Setup(**ARGON, channel="cc_nue_ar40", period="annual")
    day, night = rate(inputs, s.replace(period="day"), osc), rate(inputs, s.replace(period="night"), osc)
    assert night > day
    assert rate(inputs, s, osc) == pytest.approx(0.5 * (day + night), rel=1e-12)  # default unchanged
    f = 0.507
    assert rate(inputs, s.replace(night_fraction=f), osc) == pytest.approx((1 - f) * day + f * night, rel=1e-12)
    # A_DN is a ratio of rates: the exposure split does not enter
    assert rate(inputs, s.replace(night_fraction=f), osc, "adn") == pytest.approx(rate(inputs, s, osc, "adn"))


def test_night_fraction_splits_the_statistics():
    day, night, exposure = 100.0, 110.0, 10.0
    # equal halves: the previous formulas
    s = 0.5 * (day + night)
    assert engine.statistical_sigma("rate", "annual", day, night, exposure) == pytest.approx(np.sqrt(s * exposure) / exposure)
    assert engine.statistical_sigma("rate", "night", day, night, exposure) == pytest.approx(
        np.sqrt(night * exposure / 2) / (exposure / 2))
    D, N = day * exposure / 2, night * exposure / 2
    old_adn = np.sqrt((4 * D / (D + N) ** 2) ** 2 * N + (4 * N / (D + N) ** 2) ** 2 * D)
    assert engine.statistical_sigma("adn", "annual", day, night, exposure) == pytest.approx(old_adn, rel=1e-12)
    # 0.493 / 0.507: night counts N = n X f; the A_DN error from Poisson errors on both counts
    f = 0.507
    assert engine.statistical_sigma("rate", "night", day, night, exposure, night_fraction=f) == pytest.approx(
        np.sqrt(night / (exposure * f)))
    d, n = day, night
    expected = np.sqrt((4 * n / (n + d) ** 2 * d) ** 2 / (d * exposure * (1 - f))
                       + (4 * d / (n + d) ** 2 * n) ** 2 / (n * exposure * f))
    assert engine.statistical_sigma("adn", "annual", day, night, exposure, night_fraction=f) == pytest.approx(expected)


def test_night_fraction_is_checked(inputs):
    with pytest.raises(ValueError, match="night fraction"):
        engine.check(inputs, engine.Setup(night_fraction=1.2))


# ---------------------------------------------------------------- cut in true neutrino energy

def test_quadrature_cut_is_exact_for_linear_integrands():
    energy = np.array([0.0, 1.0, 2.5, 4.0, 6.0])
    weight = np.ones_like(energy)
    f = 3.0 + 2.0 * energy  # linear: the trapezoid is exact on each interval
    for low in (0.0, 0.3, 1.0, 2.0, 3.99, 5.5):
        exact = (3.0 * (6.0 - low) + (36.0 - low**2)) if low < 6 else 0.0
        assert engine._quadrature("continuum", energy, weight, low) @ f == pytest.approx(exact, rel=1e-12)
    assert np.all(engine._quadrature("continuum", energy, weight, 7.0) == 0)
    lines = engine._quadrature("line", np.array([0.86, 1.44]), np.array([0.9, 0.1]), 1.0)
    assert lines.tolist() == [0.0, 0.1]


def test_cc_cut_in_neutrino_energy_equals_the_visible_threshold(inputs, osc):
    """CC: visible energy is E_nu - Q, so E_nu > X and E_nu - Q > X - Q are the same cut."""
    s = engine.Setup(**ARGON, channel="cc_nue_ar40", xsec_model="ar40_marley2_bhattacharya2009", period="annual")
    q = inputs["visible_offset_MeV"]["cc_nue_ar40"]
    for x in (5.0, 8.0, 10.0, 15.0):
        assert rate(inputs, s.replace(nu_threshold=x), osc) == pytest.approx(rate(inputs, s.replace(threshold=x - q), osc),
                                                                             rel=1e-5)  # exact vs interpolated cumulative


def test_es_cut_in_neutrino_energy(inputs, osc):
    s = engine.Setup(**ARGON, channel="es", period="annual")
    full = rate(inputs, s, osc)
    assert rate(inputs, s.replace(nu_threshold=0.05), osc) == pytest.approx(full, rel=1e-12)  # below the 8B grid
    cuts = [rate(inputs, s.replace(nu_threshold=x), osc) for x in np.arange(1.0, 16.0, 0.37)]
    assert np.all(np.diff(cuts) < 0)  # strictly falling: a cut inside a flux interval counts its part
    # neutrinos below E_min(T) cannot give a recoil above T: a cut at a flux-grid node below E_min removes nothing
    # (inside an interval the trapezoid's linear interpolation of the kernel is cut too, by ~1e-4)
    t = 9.0
    e_min = 0.5 * (t + np.sqrt(t * (t + 2 * inputs["constants"]["m_e_MeV"])))
    node = np.floor(e_min * 10) / 10 - 0.1  # the 8B and hep shapes are on a 0.1 MeV grid
    assert rate(inputs, s.replace(threshold=t, nu_threshold=node), osc) == pytest.approx(
        rate(inputs, s.replace(threshold=t), osc), rel=1e-9)
    # the observed_rates reference path agrees with the fast path
    cut = s.replace(nu_threshold=7.3)
    ref = engine.totals(engine.observed_rates(inputs, DayNight(), cut, osc))
    fast = engine.component_totals(inputs, DayNight(), cut, osc)
    for c in cut.components:
        assert ref[c]["day"] == pytest.approx(fast[c]["day"], rel=1e-9)


# ---------------------------------------------------------------- NC on 40Ar

def test_nc_ar40_is_snowglobes_table_folded_over_the_flux(inputs, osc):
    s = engine.Setup(**ARGON, channel="nc_ar40", period="annual")
    engine.check(inputs, s)
    e, sigma = inputs.xsec["nc_ar40"]["default"]
    assert np.all(sigma >= 0) and sigma[e < 8.0].max() == 0.0
    expected = 0.0
    for c in s.components:
        kind, energy, weight = inputs.components[c]
        expected += (inputs["seconds_per_year"] * inputs["detectors"]["argon"]["targets"]["ar40"]
                     * inputs.flux("b16_gs98", c) * np.trapezoid(weight * np.interp(energy, e, sigma, left=0, right=0),
                                                                 energy))
    assert rate(inputs, s, osc) == pytest.approx(expected, rel=1e-9)
    # all active flavours alike: no day-night difference, and the same rate without oscillations
    per = engine.component_totals(inputs, DayNight(), s, osc)
    for c in s.components:
        assert per[c]["day"] == pytest.approx(per[c]["night"]) == pytest.approx(per[c]["ref"])


def test_nc_ar40_axis_is_the_neutrino_energy(inputs, osc):
    s = engine.Setup(**ARGON, channel="nc_ar40", period="annual")
    assert engine.observable("nc_ar40") == "Neutrino energy E_nu (MeV)"
    for x in (5.0, 10.0, 12.5):
        assert rate(inputs, s.replace(threshold=x), osc) == pytest.approx(rate(inputs, s.replace(nu_threshold=x), osc),
                                                                          rel=1e-6)  # cumulative interpolated vs exact
    # zero below 8 MeV: a 5 MeV cut removes nothing
    assert rate(inputs, s.replace(nu_threshold=5.0), osc) == pytest.approx(rate(inputs, s, osc), rel=1e-12)


def test_nc_ar40_reference_value(inputs, osc):
    """B16-GS98 8B + hep, E_nu > 5 MeV: 28.8 per kt-yr (SNOwGLoBES's negative values set to zero)."""
    s = engine.Setup(**ARGON, channel="nc_ar40", period="annual", nu_threshold=5.0)
    assert rate(inputs, s, osc) == pytest.approx(28.80, abs=0.02)


# ---------------------------------------------------------------- SOLAR's night

DRIVER = ROOT / "contributions" / "nufast-earth" / "scripts" / "b3_driver"


@pytest.mark.skipif(not DRIVER.exists(), reason="NuFast-Earth driver not built")
def test_solar_night_mode(inputs, osc):
    from snufish.export import ExactProbabilities
    from snufish.exposure import solar_weight

    b3, solar = ExactProbabilities(), ExactProbabilities(night_mode="solar")
    assert (solar.depth_km, solar.latitude_deg) == (1.478, 44.35)
    e1, p1 = b3.night(osc, "prem_full", "SURF")
    e2, p2 = solar.night(osc, "prem_full", "SURF")
    assert np.array_equal(e1, e2)
    np.testing.assert_allclose(p2.sum(axis=1), 1.0, atol=1e-6)        # unitarity survives the average
    assert np.max(np.abs(p2 - p1)) < 3e-3                             # depth + sampled PDF: small next to P itself
    # the sampled PDF is W at the 80 bin centres, normalised
    c = (np.arange(80) + 0.5) / 80
    w = solar_weight(np.arccos(c), np.radians(44.35))
    assert w.sum() > 0 and np.count_nonzero(w) < 80                    # the Sun never reaches the deepest nadirs at SURF
    with pytest.raises(ValueError):
        ExactProbabilities(night_mode="nope")
