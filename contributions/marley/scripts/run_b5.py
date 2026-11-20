"""MARLEY full-chain contribution to SNUfish B5 (interaction rates in argon).

    snufish build                                   # B2 averages are read from build/data
    python contributions/marley/scripts/run_b5.py --marley <built MARLEY checkout>

MARLEY folds a neutrino source spectrum with its own cross sections and logs the
flux-averaged total cross section of the job before generating events
(JSONConfig.cc: "Flux-averaged total cross section per atom: X * 10^(-40) cm^2",
<sigma> = integral of pdf(E) sigma(E) over the integral of pdf(E), both integrated
by MARLEY). For every solar model and flux component the wrapper gives MARLEY the
oscillated spectrum of one flavour as a `grid` source (linear-linear between nodes;
`mono` for the 7Be and pep lines) and reads <sigma>:

    rate = N_targets * Phi * <sigma> * integral of s(E) P_ea(E) dE * seconds per year

with s the B2 spectral shape and P_ea = sum_i F_i |U_ai|^2 the B2 reference daytime
probabilities averaged over the component's production (as the SNOwGLoBES wrapper).
The integral is the exact trapezoid of the same nodes MARLEY interpolates linearly.

Channels (detector argon):
- cc_nue_ar40: nu_e source, MARLEY 2's recommended model (HF-CRPA continuum + bound
  40K levels from the (p,n) B(GT) of Bhattacharya et al. 2009), on 40Ar targets;
- es: nu_e, nu_mu and nu_tau sources with P_ee, P_emu, P_etau, MARLEY's ES.react
  (tree level), per electron = per atom / 18, on the spec's electrons per kt.

Totals at E_nu > 0 and E_nu > 5 MeV (the source restricted to E >= 5 MeV, a node at
5 MeV in both). A source wholly below a reaction's threshold has no rate (MARLEY
refuses it, e.g. 15O and 17F for CC, below the first allowed 40K level): 0. The nodes are the shape table, the B2 energy grid and every 0.1 MeV,
so the product s P is linear between nodes to the precision of SNUfish's folding.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from snufish.contribution import write_contribution
from snufish.fluxes import components
from snufish.paths import build_dir, contributions_dir
from snufish.spec import load_spec, pmns

CC = ["ve40ArCC_HF-CRPA.react", "ve40ArCC_Bhattacharya2009-Discrete.react"]  # MARLEY 2's recommended model
ES = ["ES.react"]
FLAVOURS = (("nue", "ve"), ("numu", "vu"), ("nutau", "vt"))  # SNUfish flavour, MARLEY neutrino
ARGON_Z = 18  # MARLEY's ES cross section is per atom: Z electrons
CC_THRESHOLD = 1.504  # MeV, as the B5 spec
NO_FLUX = "integral of the cross-section-weighted neutrino flux is <= 0"
AVERAGE = re.compile(r"Flux-averaged total cross section per atom:\s*([0-9.eE+-]+)\s*\*\s*10\^\(-40\)")


def executable(checkout):
    for candidate in (checkout / "build" / "bin" / "marley", checkout / "build" / "marley", checkout / "marley"):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise SystemExit(f"no marley executable in {checkout} (build it first: make IGNORE_ROOT=1 IGNORE_HEPMC3=1)")


class Marley:
    def __init__(self, checkout, work):
        self.checkout, self.marley, self.work, self.runs = checkout, executable(checkout), work, 0
        self.env = dict(os.environ, MARLEY=str(checkout),
                        LD_LIBRARY_PATH=f"{checkout / 'build' / 'lib'}:{os.environ.get('LD_LIBRARY_PATH', '')}")

    def average(self, reactions, source):
        """<sigma> in cm^2 per atom for one source (a MARLEY `source` object)."""
        self.runs += 1
        events = self.work / f"events_{self.runs}.hepmc3"
        config = {"reactions": reactions, "target": {"nuclides": [1000180400], "atom_fractions": [1.0]},
                  "source": source,
                  "generate": {"events": 1, "output": [{"file": str(events), "format": "ascii", "mode": "overwrite",
                                                        "force": True}]}}
        path = self.work / f"config_{self.runs}.js"
        path.write_text(json.dumps(config))
        result = subprocess.run([str(self.marley), str(path)], cwd=self.checkout, env=self.env, capture_output=True,
                                text=True)
        events.unlink(missing_ok=True)
        if result.returncode != 0 and NO_FLUX in result.stdout + result.stderr:
            return 0.0  # no flux above the reaction's effective threshold (CC: the first allowed 40K level)
        match = AVERAGE.search(result.stdout + result.stderr)
        if result.returncode != 0 or not match:
            raise RuntimeError(f"marley failed for {reactions}, {source.get('type')}:\n{result.stdout[-2000:]}"
                               f"{result.stderr[-2000:]}")
        return float(match.group(1)) * 1e-40


def nodes(energy, oscillation_energy, low=0.0):
    """The shape table, the B2 grid and every 0.1 MeV inside the table, from ``low`` (a node itself)."""
    fine = np.arange(0.0, energy[-1], 0.1)
    grid = np.unique(np.round(np.concatenate([energy, oscillation_energy, fine, [low]]), 9))
    return grid[(grid >= max(low, energy[0])) & (grid <= energy[-1])]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--marley", type=Path, required=True, help="built MARLEY checkout")
    parser.add_argument("--models", nargs="+", default=["b16_gs98", "bs05_op"])
    args = parser.parse_args()
    checkout = args.marley.resolve()

    spec, sun_spec = load_spec("B5_rates"), load_spec("B2_sun")
    seconds = spec["exposure"]["seconds_per_year"]
    targets = spec["detectors"]["argon"]["targets"]
    U2 = np.abs(pmns(sun_spec["oscillation"])) ** 2
    averages = pd.read_parquet(build_dir() / "B2_Average.parquet")
    averages = averages[averages.Tool == "snufish-reference"]

    records = []
    with tempfile.TemporaryDirectory() as tmp:
        marley = Marley(checkout, Path(tmp))
        for model in args.models:
            oscillation = averages[averages.Variant == model].set_index("Component")
            sums = {}
            for component, flux in components(spec, model).items():
                row = oscillation.loc[component]

                def p_e(e, row=row):
                    F = np.stack([np.interp(e, row.Energy, row[f"F{i}"]) for i in (1, 2, 3)], axis=-1)
                    return F @ U2.T  # [..., alpha]: P_ee, P_emu, P_etau

                rates = {}  # (channel, threshold): interactions per kt yr
                for threshold in (0.0, 5.0):
                    cc, es = 0.0, 0.0
                    if len(flux) == 2:  # lines: sigma at the line energy
                        for energy, branching in flux[1]:
                            if energy < threshold:
                                continue
                            P = p_e(np.array([energy]))[0]
                            if energy > CC_THRESHOLD:
                                cc += targets["ar40"] * flux[0] * branching * P[0] * marley.average(
                                    CC, {"type": "mono", "neutrino": "ve", "energy": energy})
                            for k, (_, nu) in enumerate(FLAVOURS):
                                sigma = marley.average(ES, {"type": "mono", "neutrino": nu, "energy": energy}) / ARGON_Z
                                es += targets["electron"] * flux[0] * branching * P[k] * sigma
                    else:
                        _, energy, shape = flux
                        e = nodes(energy, row.Energy, threshold)
                        if len(e) < 2:
                            rates[("cc_nue_ar40", threshold)] = rates[("es", threshold)] = 0.0
                            continue
                        s, P = np.interp(e, energy, shape), p_e(e)
                        for k, (_, nu) in enumerate(FLAVOURS):
                            density = s * P[:, k]
                            weight = np.trapezoid(density, e)
                            if weight <= 0:
                                continue
                            source = {"type": "grid", "neutrino": nu, "energies": e.tolist(),
                                      "prob_densities": density.tolist(), "rule": "linlin"}
                            es += targets["electron"] * flux[0] * weight * marley.average(ES, source) / ARGON_Z
                            if k == 0 and e[-1] > CC_THRESHOLD and np.any(density[e > CC_THRESHOLD] > 0):
                                cc += targets["ar40"] * flux[0] * weight * marley.average(CC, source)
                    rates[("cc_nue_ar40", threshold)], rates[("es", threshold)] = cc * seconds, es * seconds
                for (channel, threshold), value in rates.items():
                    records.append(("totals", model, f"argon/{channel}/{component}", threshold, value))
                    sums[(channel, threshold)] = sums.get((channel, threshold), 0.0) + value
                print(f"{model} {component}: " + ", ".join(f"{c} >{t:g}: {v:.5g}" for (c, t), v in rates.items()),
                      flush=True)
            for (channel, threshold), value in sums.items():
                records.append(("totals", model, f"argon/{channel}/all", threshold, value))

    version = (checkout / ".VERSION").read_text().strip() if (checkout / ".VERSION").exists() else "2.0.0"
    commit = subprocess.run(["git", "-C", str(checkout), "rev-parse", "--short", "HEAD"], capture_output=True,
                            text=True).stdout.strip() or None
    meta = {
        "tool": "marley",
        "tool_version": version,
        "tool_commit": commit,
        "benchmark": spec.id,
        "benchmark_version": spec.version,
        "contributor": "SNUfish maintainers (wrapper)",
        "date": datetime.date.today().isoformat(),
        "command": "snufish build && python contributions/marley/scripts/run_b5.py --marley <built MARLEY checkout>",
        "settings": {
            "detector": "argon only (MARLEY's 40Ar target): es and cc_nue_ar40",
            "cross_sections": {"cc_nue_ar40": " + ".join(CC) + " (MARLEY 2 recommended; B4 variant "
                                                               "ar40_marley2_bhattacharya2009)",
                               "es": "ES.react (tree level), per atom / 18"},
            "sources": "grid (linlin) of s(E) P_ea(E) per flavour on the shape table, the B2 grid and every 0.1 MeV; "
                       "mono for lines; E_nu > 5 MeV: the grid from a node at 5 MeV",
            "rates": "N_targets x Phi x MARLEY's logged flux-averaged total cross section x integral of the source "
                     "(trapezoid on the same nodes) x seconds per year",
            "targets": "the B5 spec's argon targets (electrons, 40Ar) per kt",
            "oscillations": "B2 snufish-reference, daytime, production-averaged per component",
        },
        "license": "CC-BY-4.0",
        "notes": "MARLEY's own cross sections, integrated by MARLEY over the source spectrum: independent of SNUfish's "
                 "folding of its B4 tables. Cite Gardiner, PRC 103, 044604 (2021) and CPC (arXiv:2101.11867).",
    }
    path = contributions_dir() / meta["tool"] / spec.id / meta["tool_version"]
    write_contribution(path, meta, records, spec)
    print(f"wrote {path} ({len(records)} rows)")


if __name__ == "__main__":
    main()
