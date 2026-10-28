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

Lines (7Be, pep): SNOwGLoBES evaluates flux x sigma at one sampling point per
0.4975 MeV bin from 0.5 MeV. A line written as one point of the flux table
is counted 0 to 2.5 times depending on where it falls (probe with 1e6 nu_e
on electrons: 0.86 MeV -> 1.55, 1.0 -> 0, 1.2 -> 2.0, 1.44 -> 0.48,
5.2 -> 2.17, 10 -> 0). The wrapper therefore spreads each line flat over
the sampling bin that holds it, which gives its flux to that bin's sample
(sigma taken at the bin centre); `--naive_lines` writes the single point.
Nothing below 0.5 MeV is ever sampled (pp, the 384 keV 7Be line).
"""

import argparse
import datetime
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from snufish.contribution import write_contribution
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
    totals = {}
    for channel, sg_channels in groups.items():
        all_e, above5 = 0.0, 0.0
        for sg in sg_channels:
            path = snowglobes / "out" / f"{flux_name}_{sg}_{config}_events_unweighted.dat"
            rows = [line.split() for line in path.read_text().splitlines()]
            table = np.array([[float(a), float(b)] for a, b, *_ in (r for r in rows if len(r) >= 2
                                                                   and r[0][0].isdigit())])
            rate = table[:, 1] * factors[sg] * seconds / mass  # per kton-year
            all_e += rate.sum()
            above5 += rate[table[:, 0] * 1e3 > 5.0].sum()
        totals[channel] = (all_e, above5)
    return totals


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

    records = []
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
                for channel, (all_e, above5) in run(sg, name, detector, env).items():
                    for threshold, value in ((0.0, all_e), (5.0, above5)):
                        records.append(("totals", variant, f"{detector}/{channel}/{component}", threshold, value))
                        key = (detector, channel, threshold)
                        sums[key] = sums.get(key, 0.0) + value
        for (detector, channel, threshold), value in sums.items():
            records.append(("totals", variant, f"{detector}/{channel}/all", threshold, value))

    for detector in RUNS:  # SNOwGLoBES's own solar flux
        for channel, (all_e, above5) in run(sg, "solar_bs05op_mixed", detector, env).items():
            records += [("totals", "native", f"{detector}/{channel}/all", 0.0, all_e),
                        ("totals", "native", f"{detector}/{channel}/all", 5.0, above5)]

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
        },
        "license": "CC-BY-4.0",
        "notes": "Weighted output files (_events.dat) were written only for the last channel of each channel "
                 "file in our runs; the wrapper applies the target factors itself from the unweighted files.",
    }
    path = contributions_dir() / meta["tool"] / spec.id / meta["tool_version"]
    write_contribution(path, meta, records, spec)
    print(f"wrote {path} ({len(records)} rows)")


if __name__ == "__main__":
    main()
