import os
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))

from snufish.reference.xsec import es_above, es_total  # noqa: E402
from snufish.scan import oscillation, parameter_sets  # noqa: E402
from snufish.spec import load_spec  # noqa: E402
from snufish.uncertainty import _split_normal, sample_flux_scales  # noqa: E402

DRIVER = ROOT / "contributions" / "nufast-earth" / "scripts" / "b3_driver"


@pytest.fixture(scope="module")
def constants():
    return load_spec("B4_xsec", root=ROOT)["constants"]


def test_es_threshold_limits(constants):
    E = np.array([2.0, 5.0, 10.0])
    assert es_above(E, "nue", constants, 0.0) == pytest.approx(es_total(E, "nue", constants), rel=1e-12)
    above = [es_above(10.0, "numu", constants, t) for t in (0.0, 2.0, 5.0, 9.0)]
    assert all(a > b for a, b in zip(above, above[1:]))
    t_max = 2 * 2.0**2 / (constants["m_e_MeV"] + 4.0)
    assert es_above(2.0, "nue", constants, t_max + 0.1) == pytest.approx(0.0, abs=1e-60)


def test_parameter_sets_and_overrides():
    sets = parameter_sets()["sets"]
    assert {"nufit60_global", "juno_2025", "kamland_2013", "solar_global_2024", "sk_sno_2024"} <= set(sets)
    osc = oscillation("solar_global_2024")
    assert osc["dm2_21_eV2"] == pytest.approx(6.10e-5) and osc["sin2_theta13"] == pytest.approx(0.02195)
    assert oscillation("juno_2025", dm2_21_eV2=5e-5)["dm2_21_eV2"] == 5e-5


def test_split_normal_median_and_sides():
    x = _split_normal(np.random.default_rng(0), 1.0, (0.1, 0.3), 200000)
    assert np.median(x) == pytest.approx(1.0, abs=0.003)
    assert np.std(x[x > 1]) > 2 * np.std(x[x < 1])


def test_flux_sampling_keeps_b23_correlations():
    scales = sample_flux_scales(np.random.default_rng(1), "b23_gs98", 20000)
    corr = np.corrcoef(scales.T)
    assert corr[0, 3] == pytest.approx(-0.9634, abs=0.01)    # pp - 7Be
    assert corr[3, 4] == pytest.approx(0.8806, abs=0.01)     # 7Be - 8B


@pytest.mark.skipif(not DRIVER.exists(), reason="NuFast-Earth b3_driver not built")
def test_day_night_and_upturn_follow_dm2():
    from snufish.scan import observables

    low = observables(oscillation("nufit60_global", dm2_21_eV2=6.1e-5), earth_model="prem_prob3")
    high = observables(oscillation("nufit60_global", dm2_21_eV2=7.5e-5), earth_model="prem_prob3")
    # smaller dm2: stronger Earth regeneration, flatter spectrum (smaller upturn)
    assert low["adn_es"] > high["adn_es"] > 0
    assert low["upturn"] < high["upturn"]
    assert low["chi2_quadratic"] < high["chi2_quadratic"]
