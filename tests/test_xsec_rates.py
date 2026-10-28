import os
from pathlib import Path

import numpy as np
import pytest

from snufish.fluxes import components
from snufish.reference.xsec import es_total
from snufish.spec import load_spec

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))  # flux shapes are read from the repository


@pytest.fixture(scope="module")
def constants():
    return load_spec("B4_xsec", root=ROOT)["constants"]


def test_es_high_energy_limit(constants):
    # E >> m_e: sigma = (2 G_F^2 m_e E / pi) (g1^2 + g2^2 / 3)
    E, sw2 = 1000.0, constants["sin2_theta_W"]
    G, me = constants["G_F_GeV-2"] * 1e-6, constants["m_e_MeV"]
    hbarc2 = (constants["hbarc_MeV_fm"] * 1e-13) ** 2
    for flavour, g1 in (("nue", 0.5 + sw2), ("numu", -0.5 + sw2)):
        limit = 2 * G**2 * me * E / np.pi * (g1**2 + sw2**2 / 3) * hbarc2
        assert es_total(E, flavour, constants) == pytest.approx(limit, rel=1e-3)


def test_es_textbook_size(constants):
    # sigma(nu_e e) ~ 9.4e-45 (E/MeV) cm^2 and sigma(nu_mu e) ~ 1.5e-45 (E/MeV) cm^2 at 10 MeV
    assert es_total(10.0, "nue", constants) / 10 == pytest.approx(9.42e-45, rel=0.01)
    assert es_total(10.0, "numu", constants) / 10 == pytest.approx(1.50e-45, rel=0.01)
    assert es_total(10.0, "nutau", constants) == es_total(10.0, "numu", constants)


def test_flux_shapes_normalised():
    spec = load_spec("B5_rates", root=ROOT)
    fluxes = components(spec)
    assert set(fluxes) == {"pp", "pep", "hep", "Be7", "B8", "N13", "O15", "F17"}
    for name, flux in fluxes.items():
        if len(flux) == 3:
            assert np.trapezoid(flux[2], flux[1]) == pytest.approx(1.0, rel=1e-9)
        else:
            assert sum(branching for _, branching in flux[1]) == pytest.approx(1.0)
    # endpoints
    assert fluxes["pp"][1][fluxes["pp"][2] > 0].max() == pytest.approx(0.42, abs=0.01)
    # the Winter table as distributed is truncated at 15.2 MeV (see reference/ssm/shapes/README.yaml)
    assert fluxes["B8"][1][fluxes["B8"][2] > 0].max() == pytest.approx(15.2, abs=0.05)


def test_pp_es_rate_by_hand(constants):
    # pp nu_e-e interactions per electron per second, with P_ee ~ 0.55 and the
    # nu_mu,tau share ~ 0.45: the order of Borexino's 134 per day per 100 t
    spec = load_spec("B5_rates", root=ROOT)
    flux, energy, shape = components(spec)["pp"]
    sigma = 0.55 * es_total(energy, "nue", constants) + 0.45 * es_total(energy, "numu", constants)
    per_electron = flux * np.trapezoid(shape * sigma, energy)
    per_day_100t = per_electron * 3.307e31 * 86400   # Borexino electrons per 100 t
    assert 120 < per_day_100t < 150
