import numpy as np
import pytest

from snufish.exposure import cell_weights, night_exposure, orbital_factors, solar_weight

# NuFast-Earth Solar_Weight (src/Solar.cpp @ 327586d) at Kamioka, 36.48 deg
NUFAST_KAMIOKA = [(0.0157079632679, 0.0), (0.314159265359, 0.335522367577492),
                  (0.628318530718, 0.570033739984872), (0.942477796077, 0.9189623857218),
                  (1.25663706144, 0.908116695492658)]


def test_matches_nufast_earth():
    eta, expected = np.array(NUFAST_KAMIOKA).T
    assert solar_weight(eta, np.radians(36.48)) == pytest.approx(expected, rel=1e-9, abs=1e-12)


@pytest.mark.parametrize("latitude_deg", [0.0, 22.12, 36.48, 44.356, 70.0, 89.9])
def test_normalised_over_the_night(latitude_deg):
    lat = np.radians(latitude_deg)
    assert night_exposure(lat, 0, np.pi / 2) == pytest.approx(1.0, abs=1e-6)
    weights = cell_weights(np.round(np.arange(0, 1.0005, 0.001), 3), lat)
    assert weights.sum() == pytest.approx(1.0, abs=1e-6) and (weights >= 0).all()


def test_no_core_crossing_near_the_pole():
    # the Sun stays within 23.4 deg of the horizon: eta > 66.6 deg, so cos eta < 0.40
    lat = np.radians(89.9)
    assert night_exposure(lat, 0, np.arccos(0.40)) == pytest.approx(0.0, abs=1e-12)


def test_zero_above_the_horizon():
    assert solar_weight([1.6, 2.5, 3.0], np.radians(36.48)) == pytest.approx([0, 0, 0])


# Han et al., arXiv:2607.24421, table 7.1: A_DN of the flux minus A_DN of the survival probability
# (percentage points), the part of the flux asymmetry due to the detector-Sun distance (2026 ephemeris)
HAN_2026 = {36.48: 2.052 - 1.407, 42.45: 2.161 - 1.353, 44.356: 2.258 - 1.391, 46.47: 2.332 - 1.393,
            22.12: 1.824 - 1.477}


@pytest.mark.parametrize("latitude_deg", list(HAN_2026))
def test_orbital_asymmetry_matches_ephemeris_calculation(latitude_deg):
    g_day, g_night = orbital_factors(np.radians(latitude_deg))
    assert 200 * (g_night - g_day) / (g_night + g_day) == pytest.approx(HAN_2026[latitude_deg], abs=0.007)


def test_orbital_factors_flip_south():
    north, south = orbital_factors(np.radians(40.0)), orbital_factors(np.radians(-40.0))
    assert north[1] > 1 > north[0] and south[0] > 1 > south[1]
