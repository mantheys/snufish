import os
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))

from snufish.solar import COMPONENTS, electron_density, fluxes, models, table  # noqa: E402

MODELS = list(models())


def test_registry_has_the_common_models():
    assert {"b16_gs98", "b16_agss09met", "bs05_op", "bs05_agsop", "b23_gs98", "b23_agss09",
            "b23_mb22m", "b23_mb22p"} <= set(MODELS)


@pytest.mark.parametrize("name", MODELS)
def test_production_profiles_normalised_and_positive(name):
    data = table(name)
    r = data[:, 0]
    for k in range(len(COMPONENTS)):
        assert np.trapezoid(data[:, 2 + k], r) == pytest.approx(1.0, abs=1e-6)
        assert (data[:, 2 + k] >= 0).all()


@pytest.mark.parametrize("name", MODELS)
def test_density_falls_outside_the_core_and_tail_is_continuous(name):
    r = np.linspace(0.05, 0.9, 200)
    log_ne = np.log10(electron_density(name, r))
    assert np.all(np.diff(log_ne) < 0)
    assert 1.95 < np.log10(electron_density(name, 0.0)) < 2.05      # ~100 N_A / cm^3 at the centre
    end = table(name)[-1, 0]
    if end < 0.9:
        inside, outside = np.log10(electron_density(name, [end - 1e-4, end + 1e-4]))
        assert outside == pytest.approx(inside, abs=0.01)


@pytest.mark.parametrize("name", MODELS)
def test_fluxes_in_published_ranges(name):
    f = fluxes(name)
    assert 5.9e10 < f["pp"] < 6.1e10
    assert 4.0e9 < f["Be7"] < 5.0e9
    assert 4.0e6 < f["B8"] < 5.8e6
    assert all(f[c] > 0 for c in COMPONENTS)


def test_published_values_spot_check():
    # B16 (arXiv:1611.09867 table 6), BS05 (astro-ph/0412440 table 1), B23 Zenodo fluxes files
    assert fluxes("b16_gs98")["B8"] == pytest.approx(5.46e6)
    assert fluxes("b16_agss09met")["O15"] == pytest.approx(1.44e8)
    assert fluxes("bs05_op")["B8"] == pytest.approx(5.691e6)
    assert fluxes("b23_gs98")["B8"] == pytest.approx(5.025e6)
