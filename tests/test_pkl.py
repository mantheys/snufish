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


def test_nuebar_ar40_quenched_legacy_variant():
    table = yaml.safe_load((Path(__file__).resolve().parents[1] / "reference" / "xsec" / "vandessel2019_nuebar_ar40.yaml").read_text())
    nodes = np.asarray(table["energy_MeV"])
    total, natural, unnatural = (np.asarray(table[k]) for k in ("total_1e-40cm2", "natural_1e-40cm2", "unnatural_1e-40cm2"))
    assert np.max(np.abs(natural + unnatural - total)) < 0.003   # the parity panels add up to the total panel
    factor = (1.00 / 1.27) ** 2
    np.testing.assert_allclose(vandessel2019_nuebar(nodes, quenched=True), (total - (1 - factor) * unnatural) * 1e-40,
                               rtol=1e-12, atol=0)
    energy = np.linspace(18.0, 100.0, 411)
    ratio = vandessel2019_nuebar(energy, quenched=True) / vandessel2019_nuebar(energy)
    assert np.all((ratio > 0.85) & (ratio < 0.89))
    assert np.all(vandessel2019_nuebar(np.linspace(0, 16, 50), quenched=True) == 0.0)
    status = yaml.safe_load((Path(__file__).resolve().parents[1] / "reference" / "status.yaml").read_text())
    entries = status["xsec_model"]["cc_nuebar_ar40"]
    assert set(entries) == set(pkl.NUEBAR_MODELS)
    assert entries["vandessel2019"]["status"] == "current"
    assert entries["vandessel2019_quenched"] == {**entries["vandessel2019_quenched"], "status": "legacy", "superseded_by": "vandessel2019"}


@needs_marley
def test_export_xsec_quenched_variant_changes_only_the_nuebar_row(tmp_path, capsys):
    rows = {}
    for model in pkl.NUEBAR_MODELS:
        assert main(["export-xsec", "--marley", str(MARLEY), "--out", str(tmp_path / model), "--nuebar_model", model]) == 0
        rows[model] = {r["Config"]: r["XS"] for r in pd.read_pickle(tmp_path / model / "theory" / "xs_comparison.pkl")}
    assert "vandessel2019_quenched is legacy" in capsys.readouterr().out
    published, quenched = rows["vandessel2019"], rows["vandessel2019_quenched"]
    assert all(np.array_equal(published[c], quenched[c]) for c in published if c != "xs_nuebar_Ar40")
    assert np.all(quenched["xs_nuebar_Ar40"] <= published["xs_nuebar_Ar40"])


@pytest.mark.parametrize("energy, sigma_1e40", [(30.0, 0.0896), (50.0, 0.8336), (100.0, 8.662)])
def test_nuebar_ar40_spot_values(energy, sigma_1e40):
    # fig. 9 of PRC 100, 055503, read from its vector PDF: gnuplot's 0.05 pt steps are 0.0025e-40 cm^2
    assert vandessel2019_nuebar(energy) * 1e40 == pytest.approx(sigma_1e40, abs=0.0025)
