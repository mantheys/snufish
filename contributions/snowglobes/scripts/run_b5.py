"""SNOwGLoBES full-chain contribution to SNUfish B5 (interaction rates).

    snufish build                                   # B2 averages are read from build/data
    python run_b5.py --snowglobes <built SNOwGLoBES checkout at the pinned commit>

Building that checkout (GLoBES installed, GLB_DIR set):
    git clone <snowglobes> sg && git -C sg checkout 6fa928e && mkdir sg/out
    cd sg/src && SNOWGLOBES=$PWD/.. make supernova && cp supernova ../bin/
(only the `supernova` target: the CEvNS library rule uses `ar clq`, which
binutils >= 2.36 rejects; `out/` is not in the repository and SNOwGLoBES
silently writes nothing without it).

For every solar model and flux component this writes a SNOwGLoBES flux file
(energies 0-0.1 GeV every 0.2 MeV; columns nu_e, nu_mu, nu_tau, anti; values
in neutrinos / cm^2 / s per 0.2 MeV at each energy, i.e. Phi s(E) 0.2 MeV
P_{e alpha}(E)),
runs `supernova.pl 0 <flux> argon ar40kt` and `... water wc100kt30prct`, reads
the unweighted, unsmeared interaction rates (0.5 MeV bins of true energy, per
second for the whole detector), applies each channel's target factor from
the channel file, and converts to interactions per kton-year. The variant
`native` runs SNOwGLoBES's own solar flux (solar_bs05op_mixed: BS05-OP, P_ee
read off a figure, nu_mu = nu_tau).

Why the full chain is low below 2 MeV (docs/crosschecks.md#snowglobes-below-2-mev):
GLoBES computes the rate of sampling bin j as flux(E_j) sigma(E_j) dE with E_j
the bin's midpoint (glb_set_rates, glb_sbin_center: 200 bins of dE = 0.4975 MeV
from 0.5 MeV), the flux interpolated linearly in E between the flux-table points
(glb_get_flux) and sigma linearly in log10 E (glb_get_xsec). `globes_rate`
below does the same; on the flux files this script writes it reproduces the
contribution to 1e-5 (tests/test_snowglobes_sampling.py).

Lines (7Be, pep): SNOwGLoBES evaluates flux x sigma at one sampling point per
0.4975 MeV bin from 0.5 MeV. A line written as one point of the flux table
is counted 0 to 2.5 times depending on where it falls (probe with 1e6 nu_e
on electrons: 0.86 MeV -> 1.55, 1.0 -> 0, 1.2 -> 2.0, 1.44 -> 0.48,
5.2 -> 2.17, 10 -> 0). The wrapper therefore spreads each line flat over
the sampling bin that holds it, which gives its flux to that bin's sample
(sigma taken at the bin centre); `--naive_lines` writes the single point.
Nothing below 0.5 MeV is ever sampled (pp, the 384 keV 7Be line).

Part 2 (grid observed, settings.response "own"): the same runs' smeared outputs (_events_smeared_unweighted.dat,
0.4975 MeV bins of detected energy from 0.5 MeV) give the rate above each value of the observed grid, the
cumulative interpolated linearly within a bin (each bin spread uniformly, as SNUfish spreads an imported bin),
counted up to 20 MeV, the top of the grid. response.parquet holds what produced them: each channel's smearing
matrix (smear/<config>/smear_<channel>_<config>.dat; GLoBES lists it by detected bin, each row the sampling
points feeding that bin), in neutrino energy, per flavour for ES, and an efficiency of 1. supernova.pl at 6fa928e
reads the post-smearing efficiencies only in its custom-binning mode (run mode 1 sets $chan_name_post, mode 0 does
not): in mode 0, the one run here, it looks for effic/<config>/effic__<config>.dat, finds nothing, and includes no
efficiency. The smeared output is the unsmeared rate times the matrix, to 4e-6 of the peak bin (six printed digits);
GLoBES's sampling through these matrices reproduces the observed rates (tests/test_snowglobes_part2.py).
"""

import argparse
import datetime
import os
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from snufish.contribution import RESPONSE_COLUMNS, write_contribution
from snufish.fluxes import components
from snufish.paths import build_dir, contributions_dir
from snufish.spec import load_spec, pmns

RUNS = {  # detector -> (channel file, configuration, {SNUfish channel: [SNOwGLoBES channels]})
    "argon": ("argon", "ar40kt", {"es": ["nue_e", "numu_e", "nutau_e"], "cc_nue_ar40": ["nue_Ar40"]}),
    "water": ("water", "wc100kt30prct", {"es": ["nue_e", "numu_e", "nutau_e"], "cc_nue_o16": ["nue_O16"]}),
}
GRID_GEV = np.round(np.arange(0.0, 0.1 + 1e-9, 0.0002), 6)
# glb/preamble.glb: 200 sampling points from 0.5 to 100 MeV; flux x sigma is evaluated once per bin.
SAMPLING_MIN, SAMPLING_WIDTH = 0.5, (100.0 - 0.5) / 200  # MeV


# Part 2: the response of each SNUfish channel, from these SNOwGLoBES channels' smearing matrices (ES: per flavour).
DETECTED_EDGES = SAMPLING_MIN + np.arange(201) * SAMPLING_WIDTH   # $bins = 200 from $emin 0.5 to $emax 100 MeV
OBSERVED_TOP = 20.0   # MeV: the top of the B5 observed grid; the response stops at the bin holding it


def glb_matrix(path):
    """A GLoBES smearing matrix as [sampling (true) bin, detected bin]. The file gives one row per detected bin i,
    ``{k_low, k_high, P(i | k_low), ..., P(i | k_high)}`` over the sampling points k."""
    rows = []
    for m in re.finditer(r"\{(\d+),(\d+),([^}]*)\}", Path(path).read_text()):
        low, high = int(m.group(1)), int(m.group(2))
        values = [float(v) for v in m.group(3).split(",") if v.strip()]
        row = np.zeros(200)
        row[low:high + 1] = values[:high - low + 1]
        rows.append(row)
    return np.array(rows).T


def kept_bins():
    """Number of the 200 bins kept in response.parquet: those starting below the top of the observed grid."""
    return int(np.searchsorted(DETECTED_EDGES, OBSERVED_TOP, side="left"))


def response_rows(snowglobes, detector):
    """response.parquet rows of one detector: each SNUfish channel's smearing matrix in neutrino energy (ES: one
    per flavour, from nue_e, numu_e, nutau_e) and an efficiency of 1, on the bins below the top of the grid."""
    _, config, groups = RUNS[detector]
    n, edges = kept_bins(), DETECTED_EDGES
    rows = []
    for channel, sg_channels in groups.items():
        for sg in sg_channels:
            flavour = sg.split("_")[0] if channel == "es" else ""
            matrix = glb_matrix(snowglobes / "smear" / config / f"smear_{sg}_{config}.dat")[:n, :n]
            for i, j in zip(*np.nonzero(matrix)):
                rows.append((detector, channel, "smearing", "neutrino", edges[i], edges[i + 1], edges[j], edges[j + 1],
                             matrix[i, j], flavour))
        rows += [(detector, channel, "efficiency", "observed", np.nan, np.nan, edges[j], edges[j + 1], 1.0, "")
                 for j in range(n)]
    return rows


def above_grid(content, thresholds, top=OBSERVED_TOP):
    """Rate above each threshold, up to ``top``, from the content of the detected bins: each bin spread uniformly
    (the cumulative interpolated linearly within a bin)."""
    low, high = DETECTED_EDGES[:-1], DETECTED_EDGES[1:]
    t = np.asarray(thresholds, float)[:, None]
    overlap = np.clip(np.minimum(high, top)[None, :] - np.maximum(low[None, :], t), 0.0, None)
    return overlap / (high - low) @ np.asarray(content, float)


def read_output(path):
    """[bin, (energy GeV, rate)] of a SNOwGLoBES output file."""
    rows = [line.split() for line in Path(path).read_text().splitlines()]
    return np.array([[float(a), float(b)] for a, b, *_ in (r for r in rows if len(r) >= 2 and r[0][0].isdigit())])


def channel_factors(snowglobes, channel_file):
    factors = {}
    for line in (snowglobes / "channels" / f"channels_{channel_file}.dat").read_text().splitlines():
        parts = line.split()
        if len(parts) >= 5 and not line.startswith("%"):
            factors[parts[0]] = float(parts[4])
    return factors


def config_mass(snowglobes, config):
    for line in (snowglobes / "detector_configurations.dat").read_text().splitlines():
        parts = line.split()
        if parts and parts[0] == config:
            return float(parts[1])
    raise KeyError(config)


def write_flux(path, flavours):
    """flavours: array [grid, 3] of nu_e, nu_mu, nu_tau per 0.2 MeV."""
    table = np.zeros((len(GRID_GEV), 7))
    table[:, 0] = GRID_GEV
    table[:, 1:4] = flavours
    np.savetxt(path, table, fmt="%.6e", header="SNUfish solar flux, nu/cm^2/s per 0.2 MeV")


def sampling_centres():
    """GLoBES's sampling points (MeV): the midpoints of 200 bins of SAMPLING_WIDTH from SAMPLING_MIN."""
    return SAMPLING_MIN + (np.arange(200) + 0.5) * SAMPLING_WIDTH


def globes_bins(flux_column, sigma):
    """GLoBES's rate in each sampling bin from one flux-file column (per 0.2 MeV, on GRID_GEV): the flux interpolated
    linearly at the bin midpoint, per MeV, times ``sigma(E)`` (cm^2 per target), times the bin width. Per target and
    second; zero outside the flux table, as glb_get_flux."""
    energy, centres = GRID_GEV * 1e3, sampling_centres()
    flux = np.where((centres > energy[0]) & (centres <= energy[-1]), np.interp(centres, energy, flux_column), 0.0)
    return flux / 0.2 * sigma(centres) * SAMPLING_WIDTH


def globes_rate(flux_column, sigma):
    """GLoBES's rate integral: the sum of ``globes_bins``."""
    return float(np.sum(globes_bins(flux_column, sigma)))


def component_flux(spec, model, component, oscillation, U2, naive_lines=False):
    """Flux file columns for one component: Phi s(E) 0.2 MeV P_{e alpha}(E)."""
    energy_mev = GRID_GEV * 1e3
    flux = components(spec, model)[component]
    out = np.zeros((len(GRID_GEV), 3))
    row = oscillation.loc[component]

    def p_e_alpha(e):
        F = np.stack([np.interp(e, row.Energy, row[f"F{i}"]) for i in (1, 2, 3)], axis=-1)
        return F @ U2.T

    if len(flux) == 2:  # lines
        for energy, branching in flux[1]:
            line = flux[0] * branching * p_e_alpha(np.array([energy]))[0]
            if naive_lines:
                out[int(round(energy / 0.2))] += line
                continue
            # Spread over the sampling bin holding the line, so the midpoint sample sees its full flux
            # (a point value is counted 0 to 2.5 times depending on where it falls; see the module doc).
            k = int((energy - SAMPLING_MIN) // SAMPLING_WIDTH)
            if k < 0:
                continue  # below the first sampling point: SNOwGLoBES never sees it
            low, high = SAMPLING_MIN + k * SAMPLING_WIDTH, SAMPLING_MIN + (k + 1) * SAMPLING_WIDTH
            inside = (energy_mev >= low) & (energy_mev < high)
            out[inside] += line * 0.2 / SAMPLING_WIDTH
    else:
        _, energy, shape = flux
        s = np.interp(energy_mev, energy, shape, left=0.0, right=0.0)
        out = (flux[0] * s * 0.2)[:, None] * p_e_alpha(energy_mev)
    return out


def run(snowglobes, flux_name, detector, env):
    channel_file, config, groups = RUNS[detector]
    subprocess.run(["perl", "supernova.pl", "0", flux_name, channel_file, config], cwd=snowglobes, env=env,
                   check=True, capture_output=True)
    factors, mass = channel_factors(snowglobes, channel_file), config_mass(snowglobes, config)
    seconds = load_spec("B5_rates")["exposure"]["seconds_per_year"]
    totals, smeared = {}, {}
    for channel, sg_channels in groups.items():
        all_e, above5, detected = 0.0, 0.0, np.zeros(200)
        for sg in sg_channels:
            table = read_output(snowglobes / "out" / f"{flux_name}_{sg}_{config}_events_unweighted.dat")
            rate = table[:, 1] * factors[sg] * seconds / mass  # per kton-year
            all_e += rate.sum()
            above5 += rate[table[:, 0] * 1e3 > 5.0].sum()
            out = read_output(snowglobes / "out" / f"{flux_name}_{sg}_{config}_events_smeared_unweighted.dat")
            detected += out[:, 1] * factors[sg] * seconds / mass
        totals[channel] = (all_e, above5)
        smeared[channel] = detected
    return totals, smeared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snowglobes", type=Path, required=True)
    parser.add_argument("--models", nargs="+", default=["b16_gs98", "bs05_op"])
    parser.add_argument("--naive_lines", action="store_true", help="lines as single flux-table points")
    args = parser.parse_args()
    sg = args.snowglobes.resolve()
    env = dict(os.environ, SNOWGLOBES=str(sg))
    env.setdefault("LD_LIBRARY_PATH", str(Path(env.get("GLB_DIR", "")) / "lib"))
    (sg / "out").mkdir(exist_ok=True)

    spec, sun_spec = load_spec("B5_rates"), load_spec("B2_sun")
    U2 = np.abs(pmns(sun_spec["oscillation"])) ** 2
    averages = pd.read_parquet(build_dir() / "B2_Average.parquet")
    averages = averages[averages.Tool == "snufish-reference"]

    records, observed = [], {}
    thresholds = spec.axis("threshold", "observed")
    runs = [(model, model, args.naive_lines) for model in args.models]
    if "b16_gs98" in args.models and not args.naive_lines:
        runs.append(("b16_gs98_point_lines", "b16_gs98", True))
    for variant, model, naive in runs:
        oscillation = averages[averages.Variant == model].set_index("Component")
        sums = {}
        for component in spec["fluxes"]:
            name = f"snufish_{variant}_{component}"
            write_flux(sg / "fluxes" / f"{name}.dat", component_flux(spec, model, component, oscillation, U2, naive))
            for detector in RUNS:
                totals, smeared = run(sg, name, detector, env)
                for channel, (all_e, above5) in totals.items():
                    for threshold, value in ((0.0, all_e), (5.0, above5)):
                        records.append(("totals", variant, f"{detector}/{channel}/{component}", threshold, value))
                        key = (detector, channel, threshold)
                        sums[key] = sums.get(key, 0.0) + value
                    observed[(variant, detector, channel, component)] = smeared[channel]
        for (detector, channel, threshold), value in sums.items():
            records.append(("totals", variant, f"{detector}/{channel}/all", threshold, value))

    for detector in RUNS:  # SNOwGLoBES's own solar flux
        totals, smeared = run(sg, "solar_bs05op_mixed", detector, env)
        for channel, (all_e, above5) in totals.items():
            records += [("totals", "native", f"{detector}/{channel}/all", 0.0, all_e),
                        ("totals", "native", f"{detector}/{channel}/all", 5.0, above5)]
            observed[("native", detector, channel, "all")] = smeared[channel]

    for (variant, detector, channel) in sorted({k[:3] for k in observed}):  # part 2
        parts = {k[3]: v for k, v in observed.items() if k[:3] == (variant, detector, channel)}
        if "all" not in parts:
            parts["all"] = sum(parts.values())
        for component, content in parts.items():
            records += [("observed", variant, f"{detector}/{channel}/{component}", t, v)
                        for t, v in zip(thresholds, above_grid(content, thresholds))]

    commit = subprocess.run(["git", "-C", str(sg), "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                            check=True).stdout.strip()
    meta = {
        "tool": "snowglobes",
        "tool_version": f"git-{commit}",
        "tool_commit": commit,
        "benchmark": spec.id,
        "benchmark_version": spec.version,
        "contributor": "SNUfish maintainers (wrapper)",
        "date": datetime.date.today().isoformat(),
        "command": "snufish build && python contributions/snowglobes/scripts/run_b5.py --snowglobes <checkout>",
        "settings": {
            "runs": {d: f"supernova.pl 0 <flux> {c} {cfg}" for d, (c, cfg, _) in RUNS.items()},
            "flux_files": "0-0.1 GeV every 0.2 MeV; nu/cm^2/s per 0.2 MeV; lines spread flat over their "
                          "0.4975 MeV sampling bin (a single table point is counted 0-2.5x, see run_b5.py)",
            "rates": "unweighted, unsmeared outputs x channel-file target factor x seconds/year / config mass",
            "targets": "SNOwGLoBES conventions: argon N_A/40 per gram (pure 40Ar), water 2/18 x N_A protons "
                       "per gram (ES x5, 16O x0.5)",
            "native": "fluxes/solar_bs05op_mixed.dat (BS05-OP, survival probabilities from a figure)",
            "oscillations": "B2 snufish-reference, daytime, production-averaged per component",
            "response": "own",
            "observed": "smeared outputs (_events_smeared_unweighted.dat) x the target factor, per kton-year; the "
                        "rate above each grid value up to 20 MeV, each 0.4975 MeV detected bin spread uniformly "
                        "(the cumulative interpolated linearly within a bin)",
            "response_file": "response.parquet: smear/<config>/smear_<channel>_<config>.dat in neutrino energy "
                             "(ES per flavour), bins below 20 MeV; efficiency 1 (supernova.pl mode 0 includes no "
                             "post-smearing efficiency at 6fa928e, see run_b5.py)",
            "cross_sections": {"es": {"tool": "snowglobes", "variant": "default"},
                               "cc_nue_ar40": {"tool": "snowglobes", "variant": "default"},
                               "cc_nue_o16": {"tool": "snowglobes", "variant": "default"}},
        },
        "license": "CC-BY-4.0",
        "notes": "Weighted output files (_events.dat) were written only for the last channel of each channel "
                 "file in our runs; the wrapper applies the target factors itself from the unweighted files.",
    }
    path = contributions_dir() / meta["tool"] / spec.id / meta["tool_version"]
    response = pd.DataFrame([row for detector in RUNS for row in response_rows(sg, detector)],
                            columns=[*RESPONSE_COLUMNS, "flavour"])
    path.mkdir(parents=True, exist_ok=True)
    response.to_parquet(path / "response.parquet", index=False)
    write_contribution(path, meta, records, spec)
    print(f"wrote {path} ({len(records)} rows)")


if __name__ == "__main__":
    main()
