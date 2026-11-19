from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from snufish import pkl
from snufish.cli import main
from snufish.export import vandessel2019_nuebar


def test_solar_spectrum_layout_and_normalisation():
    frame = pkl.solar_spectrum("b16_gs98")
    assert list(frame.columns) == ["Flux", "Energy", "Source", "Plot"]
    assert set(frame.Source) == {"pp", "pep", "hep", "b7", "b8", "n13", "o15", "f17"}
    assert (frame.Plot == "B16-GS98").all()
    pp = frame[frame.Source == "pp"].iloc[0]
    assert np.trapezoid(pp.Flux, pp.Energy) == pytest.approx(5.98e10, rel=1e-3)   # B16-GS98 pp flux
    b7 = frame[frame.Source == "b7"]
    assert len(b7) == 2   # one row per line, [0, F] at [E, E]
    assert b7.Flux.map(lambda f: f[1]).sum() == pytest.approx(4.93e9, rel=1e-3)
    assert all(e[0] == e[1] for e in b7.Energy)


def test_day_survival_lowers_b8_and_cli_writes_pkl(tmp_path):
    vacuum = pkl.solar_spectrum("b16_gs98")
    day = pkl.solar_spectrum("b16_gs98", period="day")
    b8 = lambda f: np.trapezoid(*[f[f.Source == "b8"].iloc[0][k] for k in ("Flux", "Energy")])
    assert 0.3 < b8(day) / b8(vacuum) < 0.5   # P_ee ~ 0.35-0.4 at 8B energies
    assert main(["export-pkl", "--out", str(tmp_path)]) == 0
    back = pd.read_pickle(tmp_path / "theory" / "Solar_Neutrino_Spectrum.pkl")
    assert len(back) == len(vacuum)


MARLEY = Path("/home/smanthey/Code/marley")
needs_marley = pytest.mark.skipif(not (MARLEY / "build" / "bin" / "marley").exists(), reason="needs a built MARLEY checkout")


@needs_marley
def test_xsec_comparison_layout():
    curves = {r["Config"]: r for r in pkl.xsec_comparison(MARLEY)}
    assert set(curves) == {"xs_nue_Ar40", "xs_nuebar_Ar40", "xs_nue_e", "xs_nuebar_e", "xs_numu_nutau_e", "xs_nc_nue_Ar40"}
    cc = curves["xs_nue_Ar40"]
    assert cc["Energy"][0] == 0.5 and cc["Energy"][-1] == 100.0
    assert np.interp(10.0, cc["Energy"], cc["XS"]) == pytest.approx(7.24e-4, rel=1e-2)   # ar40_marley1_allowed, 1e-38 cm^2
    assert np.interp(100.0, cc["Energy"], cc["XS"]) == pytest.approx(0.446, rel=1e-2)
    anti = curves["xs_nuebar_Ar40"]   # Van Dessel et al. 2019, in 1e-38 cm^2
    assert np.array_equal(anti["XS"], vandessel2019_nuebar(anti["Energy"]) * 1e38)


@needs_marley
def test_export_xsec_needs_no_snowglobes(tmp_path):
    assert main(["export-xsec", "--marley", str(MARLEY), "--out", str(tmp_path)]) == 0
    back = pd.read_pickle(tmp_path / "theory" / "xs_comparison.pkl")
    assert [r["Config"] for r in back] == [c for c, _, _ in pkl.XSEC_CONFIGS]


def test_nuebar_ar40_zero_below_threshold_monotone_above():
    table = yaml.safe_load((Path(__file__).resolve().parents[1] / "reference" / "xsec" / "vandessel2019_nuebar_ar40.yaml").read_text())
    threshold = table["threshold_MeV"]
    assert threshold == 16.0 and table["reaction_threshold_MeV"] == pytest.approx(8.50, abs=0.01) and table["g_A"] == 1.27
    energy = np.linspace(0.0, 100.0, 5001)
    sigma = vandessel2019_nuebar(energy)
    assert np.all(sigma[energy <= threshold] == 0.0)
    above = sigma[energy > threshold]
    assert np.all(above > 0) and np.all(np.diff(above) > 0)
    # the YAML's nodes, the zeros at 10 and 16 MeV included
    nodes = np.asarray(table["energy_MeV"])
    np.testing.assert_allclose(vandessel2019_nuebar(nodes), np.asarray(table["total_1e-40cm2"]) * 1e-40, rtol=1e-12, atol=0)


@pytest.mark.parametrize("energy, sigma_1e40", [(30.0, 0.0896), (50.0, 0.8336), (100.0, 8.662)])
def test_nuebar_ar40_spot_values(energy, sigma_1e40):
    # fig. 9 of PRC 100, 055503, read from its vector PDF: gnuplot's 0.05 pt steps are 0.0025e-40 cm^2
    assert vandessel2019_nuebar(energy) * 1e40 == pytest.approx(sigma_1e40, abs=0.0025)
