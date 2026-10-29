"""The web page's engine (web/engine.js) against the Python engine: the same
tables, setups and random draws must give the same numbers to 1e-9."""

import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SNUFISH_ROOT", str(ROOT))

from snufish import engine  # noqa: E402

APP = ROOT / "build" / "app"
pytestmark = pytest.mark.skipif(shutil.which("node") is None or not (APP / "inputs.json").exists(),
                                reason="needs node and the app tables (snufish export-app)")

CASES = [
    ("water ES 8B rate, day", dict(threshold=3.49), "rate", "juno_2025", "fluxes"),
    ("argon CC 8B+hep annual, SNO NC, exposure", dict(detector="argon", channel="cc_nue_ar40", components=["B8", "hep"],
                                                      b8_flux="sno_nc", period="annual", exposure=40.0,
                                                      site="SURF", earth_model="prem_four"), "rate",
     "solar_global_2024", "fluxes"),
    ("argon ES low-energy night", dict(detector="argon", components=["pp", "Be7", "pep", "N13", "O15", "F17"],
                                       period="night", site="LNGS", es_model="snowglobes"), "rate", "kamland_2013",
     "fluxes"),
    ("Kamioka ES A_DN", dict(threshold=3.49), "adn", "solar_global_2024", "full"),
    ("water CC O16 A_DN, exposure", dict(channel="cc_nue_o16", components=["B8", "hep"], exposure=500.0,
                                         site="SNOLAB"), "adn", "nufit60_global", "full"),
    ("BS05 (no flux errors) argon CC", dict(solar_model="bs05_op", detector="argon", channel="cc_nue_ar40",
                                            xsec_model="ar40_marley"), "rate", "juno_2025", "fluxes"),
    ("water ES with a full detector response", dict(threshold=4.5, resolution_a=0.45, resolution_b=0.02, efficiency=0.9,
                                                    efficiency_e50=5.0, efficiency_width=0.4, period="annual",
                                                    components=["B8", "hep"]), "rate", "juno_2025", "fluxes"),
    ("argon CC A_DN, smeared", dict(detector="argon", channel="cc_nue_ar40", threshold=5.0, resolution_a=0.3,
                                    site="SURF"), "adn", "solar_global_2024", "full"),
    ("Super-K IV preset with its detector uncertainties",
     dict(threshold=3.49, resolution_poly=[-0.05525, 0.3162, 0.04572], energy_scale_error=0.0048,
          resolution_error=0.03, normalisation_error=0.011, exposure=183.0, components=["B8", "hep"]),
     "rate", "solar_global_2024", "fluxes"),
    ("Super-K IV A_DN with detector uncertainties", dict(threshold=3.49, resolution_poly=[-0.05525, 0.3162, 0.04572],
                                                       energy_scale_error=0.0048, resolution_error=0.03,
                                                       normalisation_error=0.011), "adn", "juno_2025", "full"),
    ("argon CC, energy scale shifted", dict(detector="argon", channel="cc_nue_ar40", threshold=5.0, energy_scale=1.01),
     "rate", "juno_2025", "fluxes"),
    ("argon ES 7Be line, smeared, low threshold", dict(detector="argon", components=["Be7", "pep"], threshold=0.3,
                                                      resolution_a=0.1, period="night", site="LNGS"), "rate",
     "nufit60_global", "fluxes"),
]
INVALID = [
    (dict(detector="water", channel="cc_nue_ar40"), "rate", "not available in water"),
    (dict(detector="argon", channel="cc_nue_ar40", xsec_model="nope"), "rate", "cross-section model"),
    (dict(components=[]), "rate", "at least one"),
    (dict(period="week"), "rate", "period"),
]


def clean(value):
    """JSON-safe: arrays to lists, NaN to null."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return None if math.isnan(value) else float(value)
    if isinstance(value, np.integer):
        return int(value)
    return value


def test_web_engine_matches_python(tmp_path):
    inputs, tables = engine.Inputs.load(APP / "inputs.json"), engine.TableProbabilities(APP)
    cases = []
    for name, changes, quantity, set_name, solar_range in CASES:
        setup = engine.Setup(**{**changes, "components": tuple(changes.get("components", ("B8",))),
                                "resolution_poly": tuple(changes.get("resolution_poly", ()))})
        params = engine.parameters(inputs, set_name)
        n, seed = 12, 7
        rng, osc_draws, flux_draws = engine._draws(inputs, setup, params, n, seed)
        # the Gaussian draws budget() takes next: statistics (two), then one per detector uncertainty
        extra = (2 if setup.exposure else 0) + (setup.energy_scale_error > 0) + (setup.resolution_error > 0) \
            + (setup.normalisation_error > 0 and quantity == "rate")
        state = rng.bit_generator.state
        noise = [rng.standard_normal(n) for _ in range(extra)]
        rng.bit_generator.state = state
        rows, _ = engine.budget(inputs, tables, setup, params, quantity, n=n, seed=seed, solar_range=solar_range)
        night = engine.needs_night(quantity, setup.period)
        spec = engine.spectra(inputs, tables, setup, params, n=n, seed=seed, night=night)
        cases.append(dict(name=name, setup={**changes, "components": list(setup.components)}, quantity=quantity,
                          params=params, solar_range=solar_range, rows=rows,
                          draws=dict(osc=osc_draws, flux=flux_draws, noise=noise),
                          flux=engine.flux_summary(inputs, tables, setup, engine.oscillation(params)),
                          spectra=dict(edges=spec["edges"], day=spec["day"], night=spec["night"],
                                       draws_day=spec["draws_day"]),
                          ))
    invalid = [dict(setup=s, quantity=q, message=m) for s, q, m in INVALID]
    path = tmp_path / "fixtures.json"
    path.write_text(json.dumps(clean(dict(cases=cases, invalid=invalid))))
    result = subprocess.run(["node", str(ROOT / "web" / "test" / "engine.test.mjs"), str(path), str(APP)],
                            capture_output=True, text=True)
    print(result.stdout, result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
