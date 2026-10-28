from pathlib import Path

import numpy as np
import pytest

from snufish.contribution import load_contribution, validate
from snufish.reference.sun import adiabatic_fractions
from snufish.solar import electron_density, production_weights
from snufish.spec import load_spec, pmns

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def spec():
    import os

    os.environ.setdefault("SNUFISH_ROOT", str(ROOT))  # the density table is read from the repository
    return load_spec("B2_sun", root=ROOT)


def test_density_tail_continuous_at_table_end(spec):
    inside, outside = electron_density("b16_gs98", [0.4999, 0.5001], spec)
    assert np.log10(outside / inside) == pytest.approx(0.0, abs=0.01)


def test_exponential_matches_outside_the_core_only(spec):
    # Bahcall's exponential is fitted to the outer Sun: within 0.05 dex of B16
    # for r >= 0.2, but 2.4 times too dense at the centre.
    r = np.linspace(0.2, 0.5, 7)
    ratio = electron_density("b16_gs98", r, spec) / electron_density("exponential", r, spec)
    assert np.all(np.abs(np.log10(ratio)) < 0.05)
    centre = electron_density("exponential", 0.0, spec) / electron_density("b16_gs98", 0.0, spec)
    assert centre == pytest.approx(2.4, abs=0.05)


def test_vacuum_limit_and_unitarity(spec):
    F = adiabatic_fractions(spec, "exponential", [1.0, 10.0], [3.0])  # n_e ~ 245 e^-31.6: vacuum
    assert F[0] == pytest.approx(np.tile(np.abs(pmns(spec["oscillation"])[0]) ** 2, (2, 1)), abs=1e-9)
    F = adiabatic_fractions(spec, "b16_gs98", spec.axis("energy"), spec.axis("radius"))
    assert np.abs(F.sum(axis=2) - 1).max() < 1e-12


def test_msw_textbook_values(spec):
    # LMA: high-energy 8B nu_e leave the core mostly as nu_2
    F = adiabatic_fractions(spec, "b16_gs98", [10.0], [0.05])[0, 0]
    assert F[1] > 0.85 and F[2] == pytest.approx(0.0245, abs=0.002)


def test_production_weights_normalised(spec):
    weights = production_weights("b16_gs98", spec.axis("radius"), spec)
    assert set(weights) == {"pp", "pep", "hep", "Be7", "B8", "N13", "O15", "F17"}
    for w in weights.values():
        assert w.sum() == pytest.approx(1.0) and (w >= 0).all()
    # 8B is produced closer to the centre than pp
    r = spec.axis("radius")
    assert weights["B8"] @ r < weights["pp"] @ r


def test_reference_contribution_valid(spec):
    path = ROOT / "contributions" / "snufish-reference" / "B2_sun" / "0.1.0"
    if not path.exists():
        pytest.skip("run `snufish reference B2_sun` first")
    assert validate(load_contribution(path), spec) == []
