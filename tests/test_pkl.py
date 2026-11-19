from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from snufish import pkl
from snufish.cli import main
from snufish.export import nc_ar40_default, vandessel2019_nc, vandessel2019_nuebar
from snufish.reference import nc_ar40


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


NC_YAML = Path(__file__).resolve().parents[1] / "reference" / "xsec" / "vandessel2019_nc_ar40.yaml"


def test_nc_ar40_vandessel2019_zero_below_threshold_monotone_above():
    table = yaml.safe_load(NC_YAML.read_text())
    threshold = table["threshold_MeV"]
    assert threshold == 10.0 and table["g_A"] == 1.27
    energy = np.linspace(0.0, 100.0, 5001)
    sigma = vandessel2019_nc(energy)
    assert np.all(sigma[energy <= threshold] == 0.0)
    above = sigma[energy > threshold]
    assert np.all(above > 0) and np.all(np.diff(above) > 0)
    nodes = np.asarray(table["energy_MeV"])
    np.testing.assert_allclose(vandessel2019_nc(nodes), np.asarray(table["total_1e-40cm2"]) * 1e-40, rtol=1e-12, atol=0)


@pytest.mark.parametrize("energy, sigma_1e40", [(20.0, 0.0431), (50.0, 1.131), (100.0, 12.15)])
def test_nc_ar40_vandessel2019_spot_values(energy, sigma_1e40):
    # fig. 8 of PRC 100, 055503, read from its vector PDF: gnuplot's 0.05 pt steps are 0.0039e-40 cm^2
    assert vandessel2019_nc(energy) * 1e40 == pytest.approx(sigma_1e40, abs=0.004)


@needs_marley
def test_export_xsec_nc_model_changes_only_the_nc_row(tmp_path):
    rows = {}
    for model in pkl.NC_MODELS:
        assert main(["export-xsec", "--marley", str(MARLEY), "--out", str(tmp_path / model), "--nc_model", model]) == 0
        rows[model] = {r["Config"]: r for r in pd.read_pickle(tmp_path / model / "theory" / "xs_comparison.pkl")}
    default = rows["default"]
    for model in pkl.NC_MODELS[1:]:
        assert all(np.array_equal(default[c]["XS"], rows[model][c]["XS"]) for c in default if c != "xs_nc_nue_Ar40")
    energy = default["xs_nc_nue_Ar40"]["Energy"]
    assert np.array_equal(default["xs_nc_nue_Ar40"]["XS"], nc_ar40_default(energy) * 1e38)
    assert np.array_equal(rows["vandessel2019"]["xs_nc_nue_Ar40"]["XS"], vandessel2019_nc(energy) * 1e38)
    assert np.array_equal(rows["tornow2025"]["xs_nc_nue_Ar40"]["XS"], nc_ar40.discrete(energy) * 1e38)
    table = yaml.safe_load((NC_YAML.parent / "snowglobes_nc_ar40.yaml").read_text())   # the old default, unchanged
    assert np.array_equal(rows["snowglobes"]["xs_nc_nue_Ar40"]["XS"],
                          np.interp(energy, table["energy_MeV"], np.asarray(table["sigma_cm2"]) * 1e38))


def test_nc_ar40_tornow2025_levels():
    ex, b_m1, err = nc_ar40.levels()
    assert len(ex) == 28 and ex.min() == pytest.approx(9.311) and ex.max() == pytest.approx(10.2758)
    assert b_m1.sum() == pytest.approx(1.306)   # the paper: 1.31 +- 0.18 mu_N^2


def test_nc_ar40_discrete_strength():
    """sigma = G_F^2/pi E'^2 (g_A/2)^2 B(sigma tau_3), B(sigma tau_3) = B(M1) / ((3/4pi) (g_IV/2)^2), without form
    factors; the form factors only lower it; zero below the first level."""
    ex, b_m1, _ = nc_ar40.levels()
    assert nc_ar40.GT0_PER_M1 == pytest.approx(0.3077, abs=1e-4)
    e = 20.0
    expected = 1.1663788e-11**2 / np.pi * np.sum((e - ex) ** 2 * b_m1) * nc_ar40.GT0_PER_M1 * (197.3269804e-13) ** 2
    assert nc_ar40.discrete(e, form_factors=False) == pytest.approx(expected, rel=1e-12)
    energy = np.array([9.0, 9.311, 12.0, 20.0, 50.0, 100.0])
    with_ff, without = nc_ar40.discrete(energy), nc_ar40.discrete(energy, form_factors=False)
    assert with_ff[0] == with_ff[1] == 0.0 and np.all(with_ff[2:] < without[2:])
    assert with_ff[3] / without[3] == pytest.approx(0.945, abs=0.005)   # form factors at 20 MeV
    assert nc_ar40.klein_nystrand(0.0) == 1.0


def test_nc_ar40_default_is_discrete_plus_continuum():
    energy = np.linspace(0.0, 100.0, 2001)
    sigma = nc_ar40_default(energy)
    np.testing.assert_allclose(sigma, nc_ar40.discrete(energy) + vandessel2019_nc(energy), rtol=1e-14)
    assert np.all(sigma[energy < 9.311] == 0) and np.all(sigma[energy > 9.311] > 0)
    assert np.all(np.diff(sigma[energy > 9.311]) > 0)
    assert nc_ar40_default(10.0) == pytest.approx(nc_ar40.discrete(10.0))   # below the continuum: discrete only
