"""The independent nu_e 40Ar calculations against the folded 8B cross sections their papers publish."""

import numpy as np
import pytest

from snufish import engine
from snufish.export import kostensalo2018
from snufish.paths import repo_root


def b8_spectrum():
    data = np.genfromtxt(repo_root() / "reference" / "ssm" / "shapes" / "8B_shape_Winter_et_al.csv", delimiter=",",
                         comments="#")
    data = data[~np.isnan(data).any(axis=1)]
    return data[:, 0], data[:, 1] / np.trapezoid(data[:, 1], data[:, 0])


@pytest.fixture(scope="module")
def inputs():
    from snufish.uncertainty import inputs

    return inputs()


def test_kostensalo_table_reproduces_its_folded_8b_cross_section():
    """Phys. Rev. C 97, 034309: 1.777e-42 cm^2 over 8B; the 5 MeV table interpolated in log-log is 3 % low."""
    energy, phi = b8_spectrum()
    folded = np.trapezoid(phi * kostensalo2018(energy), energy)
    assert folded == pytest.approx(1.777e-42, rel=0.05)
    assert kostensalo2018(np.array([1.0, 1.5]))[0] == 0.0  # below the 40K* threshold


def test_marley2_agrees_with_the_suzuki_honma_shell_model_above_5_mev(inputs):
    """Suzuki & Honma, PRC 87, 014607 (2013), table I: GT + IA over 8B with electrons above 5 MeV,
    14.05e-43 cm^2 (shell model reproducing the (p,n) B(GT)). MARLEY 2 with the same strengths, electron alone
    (each measured level's share to T = E - Q - E_level): within 5 %."""
    model = "ar40_marley2_bhattacharya2009"
    table = engine.electron_smearing(inputs, "cc_nue_ar40", model, 0.0)
    edges, matrix = np.array(table.x), np.array(table.matrix)
    centres = 0.5 * (edges[1:] + edges[:-1])
    xsec = inputs["xsec"]["cc_nue_ar40"][model]
    sigma = np.interp(centres, xsec["energy"], xsec["sigma"], left=0.0)
    energy, phi = b8_spectrum()
    weight = np.interp(centres, energy, phi, left=0.0, right=0.0) * np.diff(edges)
    total = matrix.sum(axis=1)
    above = matrix[:, centres >= 5.0].sum(axis=1) / np.where(total > 0, total, 1.0)
    assert np.sum(weight * sigma * above) == pytest.approx(14.05e-43, rel=0.05)
