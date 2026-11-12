import numpy as np
import pandas as pd
import pytest

from snufish import pkl
from snufish.cli import main


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
