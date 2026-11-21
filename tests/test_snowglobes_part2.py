"""SNOwGLoBES part 2 (B5 observed rates): the wrapper reads GLoBES smearing matrices by detected bin, spreads each
detected bin uniformly for the rate above a threshold, and its contribution, folded by SNUfish through the same
matrices and SNOwGLoBES's cross sections, agrees with SNUfish's folding."""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))
sys.path.insert(0, str(ROOT / "contributions" / "snowglobes" / "scripts"))

import run_b5  # noqa: E402

from snufish.contribution import load_contribution, validate  # noqa: E402
from snufish.paths import build_dir  # noqa: E402
from snufish.spec import load_spec  # noqa: E402

CONTRIBUTION = ROOT / "contributions" / "snowglobes" / "B5_rates" / "git-6fa928e"


def test_glb_matrix_is_read_by_detected_bin(tmp_path):
    # detected bin i fed by sampling points i (0.75) and i + 1 (0.25): as [true, detected], row k holds 0.75 at k
    # and 0.25 at k - 1
    lines = [f"{{{i},{min(i + 1, 199)},0.75,0.25}}" if i < 199 else "{199,199,0.75}" for i in range(200)]
    path = tmp_path / "smear.dat"
    path.write_text("energy(#x_smear)<\n@energy = " + ",\n".join(lines) + "\n>\n")
    m = run_b5.glb_matrix(path)
    assert m.shape == (200, 200)
    assert m[0, 0] == 0.75 and m[1, 0] == 0.25 and m[1, 1] == 0.75 and m[0, 1] == 0.0


def test_above_grid_spreads_each_detected_bin():
    content = np.zeros(200)
    content[3] = 2.0                         # 1.9925 - 2.49 MeV
    low, width = run_b5.DETECTED_EDGES[3], run_b5.SAMPLING_WIDTH
    out = run_b5.above_grid(content, [0.0, low, low + width / 4, low + width, 30.0])
    assert out == pytest.approx([2.0, 2.0, 1.5, 0.0, 0.0])
    top = np.zeros(200)
    top[39] = 1.0                            # 19.9025 - 20.4 MeV: counted up to 20 MeV
    assert run_b5.above_grid(top, [0.0])[0] == pytest.approx((20.0 - run_b5.DETECTED_EDGES[39]) / width)
    assert run_b5.kept_bins() == 40


@pytest.mark.skipif(not CONTRIBUTION.joinpath("response.parquet").exists(), reason="no part 2 contribution")
def test_contribution_response():
    spec = load_spec("B5_rates", root=ROOT)
    contribution = load_contribution(CONTRIBUTION)
    assert validate(contribution, spec) == []
    response = pd.read_parquet(CONTRIBUTION / "response.parquet")
    es = response[(response.channel == "es") & (response.kind == "smearing")]
    assert set(es.flavour) == {"nue", "numu", "nutau"} and set(es.true_axis) == {"neutrino"}
    eff = response[response.kind == "efficiency"]
    assert (eff.value == 1.0).all()          # supernova.pl mode 0 includes no efficiency (run_b5.py)


@pytest.mark.skipif(not (build_dir() / "B5_ObservedChain.parquet").exists(), reason="needs snufish build")
def test_full_chain_through_its_response_agrees_with_the_folding():
    # 8B above 5 MeV: within 1 %, what remains being GLoBES's sampling of flux x sigma at the 0.4975 MeV bin centres
    # (the test below) and, in argon, SNOwGLoBES's target counts (part 1)
    chain = pd.read_parquet(build_dir() / "B5_ObservedChain.parquet")
    rows = chain[(chain.Tool == "snowglobes") & (chain.Variant == "b16_gs98") & (chain.Component == "B8")]
    assert set(rows.Case) >= {"argon es", "argon cc_nue_ar40", "water es"}
    for r in rows[rows.Case != "water cc_nue_o16"].itertuples():
        k = int(np.argmin(np.abs(np.asarray(r.Threshold) - 5.0)))
        assert r.Ratio[k] == pytest.approx(1.0, abs=1e-2), r.Case
        assert r.CrossSection == "snowglobes: default" and r.Response == "own"


@pytest.mark.skipif(not (build_dir() / "B4_Sigma.parquet").exists() or not (build_dir() / "B2_Average.parquet").exists()
                    or not CONTRIBUTION.joinpath("response.parquet").exists(), reason="needs snufish build")
def test_globes_sampling_through_the_matrices_reproduces_the_observed_rates():
    # GLoBES's sampled rates (one flux x sigma per 0.4975 MeV bin, at its midpoint) through the matrices of
    # response.parquet reproduce the contribution's observed rates (water ES, where the target counts agree): what
    # remains against SNUfish's folding is the sampling, as in part 1
    from snufish.spec import pmns

    spec, sun = load_spec("B5_rates", root=ROOT), load_spec("B2_sun", root=ROOT)
    U2 = np.abs(pmns(sun["oscillation"])) ** 2
    averages = pd.read_parquet(build_dir() / "B2_Average.parquet")
    averages = averages[(averages.Tool == "snufish-reference") & (averages.Variant == "b16_gs98")].set_index("Component")
    xs = pd.read_parquet(build_dir() / "B4_Sigma.parquet")
    xs = {r.Channel: r for r in xs[(xs.Tool == "snowglobes") & (xs.Variant == "default")].itertuples()}
    sigma = {f: (lambda e, r=xs[f"es_{f}"]: np.nan_to_num(np.interp(e, r.Energy, r.Sigma, left=np.nan, right=np.nan)))
             for f in ("nue", "numu", "nutau")}
    response = pd.read_parquet(CONTRIBUTION / "response.parquet")
    n, edges = run_b5.kept_bins(), run_b5.DETECTED_EDGES
    matrices = {}
    for f in ("nue", "numu", "nutau"):
        rows = response[(response.detector == "water") & (response.channel == "es") & (response.flavour == f)]
        m = np.zeros((n, n))
        m[np.searchsorted(edges, rows.true_low.to_numpy() + 1e-9) - 1,
          np.searchsorted(edges, rows.observed_low.to_numpy() + 1e-9) - 1] = rows.value.to_numpy()
        matrices[f] = m
    data = pd.read_parquet(CONTRIBUTION / "data.parquet")
    data = data[(data.grid == "observed") & (data.variant == "b16_gs98")]
    water = spec["detectors"]["water"]["targets"]["electron"] * spec["exposure"]["seconds_per_year"]
    thresholds = spec.axis("threshold", "observed")
    for component in ("B8", "hep", "O15"):
        table = run_b5.component_flux(spec, "b16_gs98", component, averages, U2)
        detected = np.zeros(200)
        for k, f in enumerate(("nue", "numu", "nutau")):
            detected[:n] += water * run_b5.globes_bins(table[:, k], sigma[f])[:n] @ matrices[f]
        expected = run_b5.above_grid(detected, thresholds)
        got = data[data.quantity == f"water/es/{component}"].sort_values("threshold").value.to_numpy()
        keep = expected > 1e-3 * expected[0]
        assert np.allclose(got[keep], expected[keep], rtol=1e-4), component
