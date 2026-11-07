"""The SNOwGLoBES full chain below 2 MeV (B5): its deficit against SNUfish's folding is GLoBES's rate integral,
one evaluation of flux x sigma per 0.4975 MeV sampling bin at the bin midpoint. Emulated on the flux files the
wrapper writes, with SNOwGLoBES's own cross-section tables (B4), it reproduces the contribution (water ES, where
the target counts agree) to 1e-4 for every component and both ways of writing the lines."""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))
sys.path.insert(0, str(ROOT / "contributions" / "snowglobes" / "scripts"))

from snufish.paths import build_dir  # noqa: E402
from snufish.spec import load_spec, pmns  # noqa: E402

pytestmark = pytest.mark.skipif(not (build_dir() / "B4_Sigma.parquet").exists()
                                or not (build_dir() / "B2_Average.parquet").exists(), reason="needs snufish build")


def test_globes_sampling_reproduces_snowglobes():
    import run_b5

    spec, sun = load_spec("B5_rates"), load_spec("B2_sun")
    U2 = np.abs(pmns(sun["oscillation"])) ** 2
    averages = pd.read_parquet(build_dir() / "B2_Average.parquet")
    averages = averages[(averages.Tool == "snufish-reference") & (averages.Variant == "b16_gs98")].set_index("Component")
    xs = pd.read_parquet(build_dir() / "B4_Sigma.parquet")
    xs = {r.Channel: r for r in xs[(xs.Tool == "snowglobes") & (xs.Variant == "default")].itertuples()}
    sigma = {f: (lambda e, r=xs[f"es_{f}"]: np.nan_to_num(np.interp(e, r.Energy, r.Sigma, left=np.nan, right=np.nan)))
             for f in ("nue", "numu", "nutau")}
    paths = sorted((ROOT / "contributions" / "snowglobes" / "B5_rates").glob("*/data.parquet"))
    data = pd.read_parquet(paths[-1]).set_index(["variant", "quantity", "threshold"])["value"]
    water = spec["detectors"]["water"]["targets"]["electron"] * spec["exposure"]["seconds_per_year"]
    for variant, naive in (("b16_gs98", False), ("b16_gs98_point_lines", True)):
        for component in ("pep", "Be7", "N13", "O15", "F17", "B8", "hep"):
            table = run_b5.component_flux(spec, "b16_gs98", component, averages, U2, naive)
            rate = water * sum(run_b5.globes_rate(table[:, k], sigma[f]) for k, f in enumerate(("nue", "numu", "nutau")))
            assert rate == pytest.approx(data[(variant, f"water/es/{component}", 0.0)], rel=1e-4), (variant, component)
