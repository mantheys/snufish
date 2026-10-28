import numpy as np
import pytest

from snufish.reference.earth import KM_TO_INV_EV, chord_segments, matter_potential, probabilities_ie
from snufish.spec import load_spec, pmns

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def spec():
    return load_spec("B3_earth", root=ROOT)


def shells(spec):
    return spec["earth_models"]["prem_prob3"]["shells"]


def test_matter_potential_textbook_value():
    # V = 7.63e-14 eV per (g/cm^3 x Ye); 2 E V = 1.5264932e-4 eV^2 at 1 GeV in NuFast-Earth
    assert matter_potential(1.0, 1.0) == pytest.approx(7.63e-14, rel=1e-3)
    assert 2e9 * matter_potential(1.0, 1.0) == pytest.approx(1.5264932e-4, rel=1e-6)


def test_constants_match_spec(spec):
    from snufish.reference import earth

    constants = spec["constants"]
    assert earth.G_F == pytest.approx(constants["G_F_GeV-2"] * 1e-18, rel=1e-12)
    assert earth.HBARC_EV_CM == pytest.approx(constants["hbarc_MeV_fm"] * 1e-7, rel=1e-12)
    assert earth.N_A == constants["N_A_mol-1"]


@pytest.mark.parametrize("cos_nadir", [0.1, 0.5, 0.84, 0.9, 1.0])
def test_chord_length_and_symmetry(spec, cos_nadir):
    earth = spec["earth"]
    segments = chord_segments(cos_nadir, earth["radius_km"], shells(spec))
    assert sum(s[0] for s in segments) == pytest.approx(2 * earth["radius_km"] * cos_nadir)
    assert segments == segments[::-1]


def test_core_crossing_threshold(spec):
    earth = spec["earth"]
    core = shells(spec)[1]["outer_radius_km"] / earth["radius_km"]
    cos_core = np.sqrt(1 - core**2)
    densities = lambda c: {s[1] for s in chord_segments(c, earth["radius_km"], shells(spec))}
    assert 11.3 not in densities(cos_core - 1e-3)
    assert 11.3 in densities(cos_core + 1e-3)


def test_horizon_and_unitarity(spec):
    osc, earth = spec["oscillation"], spec["earth"]
    U = pmns(osc)
    args = (U, osc["dm2_21_eV2"], osc["dm2_31_eV2"], earth["radius_km"], shells(spec))
    assert probabilities_ie(10.0, 0.0, *args) == pytest.approx(np.abs(U[0]) ** 2, abs=1e-12)
    for c in (0.3, 0.9, 1.0):
        assert probabilities_ie(10.0, c, *args).sum() == pytest.approx(1.0, abs=1e-12)


def test_independent_of_theta23_and_delta(spec):
    osc, earth = dict(spec["oscillation"]), spec["earth"]
    reference = probabilities_ie(10.0, 0.95, pmns(osc), osc["dm2_21_eV2"], osc["dm2_31_eV2"],
                                 earth["radius_km"], shells(spec))
    osc.update(sin2_theta23=0.45, delta_cp_deg=270.0)
    changed = probabilities_ie(10.0, 0.95, pmns(osc), osc["dm2_21_eV2"], osc["dm2_31_eV2"],
                               earth["radius_km"], shells(spec))
    assert changed == pytest.approx(reference, abs=1e-12)


@pytest.mark.parametrize("energy", [3.0, 8.0, 15.0])
def test_two_flavour_constant_density(energy):
    """theta13 = 0 and one uniform shell: P2e = s12^2 + sin2(th_m - th) sin2th_m sin^2(dm2_m L / 4E)."""
    osc = {"sin2_theta12": 0.307, "sin2_theta13": 0.0, "sin2_theta23": 0.5, "delta_cp_deg": 0.0}
    dm2, radius, cos_nadir = 7.49e-5, 6371.0, 0.6
    shells = [{"outer_radius_km": radius, "density": 4.5, "ye": 0.49}]
    p2e = probabilities_ie(energy, cos_nadir, pmns(osc), dm2, 2.5e-3, radius, shells)[1]

    theta = np.arcsin(np.sqrt(osc["sin2_theta12"]))
    x = 2 * energy * 1e6 * matter_potential(4.5, 0.49) / dm2
    theta_m = 0.5 * np.arctan2(np.sin(2 * theta), np.cos(2 * theta) - x)
    dm2_m = dm2 * np.hypot(np.cos(2 * theta) - x, np.sin(2 * theta))
    length = 2 * radius * cos_nadir * KM_TO_INV_EV
    expected = np.sin(theta) ** 2 + np.sin(2 * (theta_m - theta)) * np.sin(2 * theta_m) * np.sin(
        dm2_m * length / (4 * energy * 1e6)) ** 2
    assert p2e == pytest.approx(expected, abs=1e-10)
