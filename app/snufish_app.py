"""SNUfish app: solar neutrino rates and their uncertainty budget, in the
browser (Panel on Pyodide) or locally (``panel serve app/snufish_app.py``).

Phase 1: one configuration, its rate and error budget, plotted with
plotipus. Data: the tables of ``snufish export-app`` (in the browser, fetched
next to the page under ``data/``; locally, ``SNUFISH_APP_DATA`` or
build/app).
"""

import glob
import os
import shlex
import sys
import tempfile

import pandas as pd
import panel as pn

from snufish import engine

pn.extension(sizing_mode="stretch_width")

IN_BROWSER = sys.platform == "emscripten"
DATA = "data" if IN_BROWSER else os.environ.get("SNUFISH_APP_DATA", "build/app")
WORK = tempfile.mkdtemp(prefix="snufish_app_")
os.makedirs(f"{WORK}/build/data", exist_ok=True)
with open(f"{WORK}/plotipus.toml", "w") as handle:
    handle.write('[project]\ndata_root = "build/data"\noutput = "output"\n')


async def fetch(name):
    """Make ``DATA/name`` available (in the browser, download it once)."""
    path = f"{DATA}/{name}"
    if IN_BROWSER and not os.path.exists(path):
        from pyodide.http import pyfetch

        response = await pyfetch(path)
        os.makedirs(DATA, exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(await response.bytes())
    return path


CHANNELS = {"ES on electrons": "es", "CC on 40Ar": "cc_nue_ar40", "CC on 16O": "cc_nue_o16"}
QUANTITIES = {"Rate": "rate", "Day-night asymmetry": "adn"}
_app = {}  # loaded inputs and tables (not "state": panel convert defines its own)

parameter_set = pn.widgets.Select(name="Oscillation parameters")
solar_model = pn.widgets.Select(name="Solar model")
b8_flux = pn.widgets.RadioButtonGroup(name="8B flux", options={"solar model": "model", "SNO NC": "sno_nc"},
                                      value="model")
detector = pn.widgets.Select(name="Detector", options=["argon", "water"], value="water")
channel = pn.widgets.Select(name="Channel", options=CHANNELS, value="es")
threshold = pn.widgets.FloatInput(name="Recoil threshold (MeV, ES)", value=3.49, step=0.5, start=0)
site = pn.widgets.Select(name="Site")
earth_model = pn.widgets.Select(name="Earth model")
quantity = pn.widgets.RadioButtonGroup(name="Quantity", options=QUANTITIES, value="rate")
exposure = pn.widgets.FloatInput(name="Exposure (kt yr, 0 = none)", value=0.0, step=10, start=0)
run = pn.widgets.Button(name="Compute", button_type="primary", disabled=True)
status = pn.pane.Markdown("Loading tables...")
result = pn.pane.Markdown("")
figure = pn.pane.PNG(None, sizing_mode="scale_width", max_width=900)


async def load():
    _app["inputs"] = engine.Inputs.load(await fetch("inputs.json"))
    inputs = _app["inputs"]
    sets = inputs["parameter_sets"]["sets"]
    parameter_set.options = {info["label"]: name for name, info in sets.items()}
    parameter_set.value = "juno_2025"
    solar_model.options = {info["label"]: name for name, info in inputs["solar_models"].items()}
    solar_model.value = "b23_gs98"
    site.options, site.value = list(inputs["sites"]), "Kamioka"
    earth_model.options, earth_model.value = list(inputs["earth_models"]), "prem_full"
    _app["tables"] = engine.TableProbabilities(DATA)
    run.disabled = False
    status.object = ""


def plot(rows, title):
    from plotipus.cli import main

    frame = pd.DataFrame(rows)
    frame.to_parquet(f"{WORK}/build/data/AppBudget.parquet")
    cwd = os.getcwd()
    os.chdir(WORK)
    try:
        for old in glob.glob("output/**/*.png", recursive=True):
            os.remove(old)
        main(shlex.split(f"cat --no_error --datafile AppBudget -x Source -y Relative --hue Kind --kind bar "
                         f"--orient h --labely 'Relative uncertainty' --title {shlex.quote(title)} --theme dark"))
        return glob.glob(f"{WORK}/output/**/*.png", recursive=True)[0]
    finally:
        os.chdir(cwd)


async def compute(event=None):
    run.disabled = True
    status.object = "Computing..."
    try:
        inputs, tables = _app["inputs"], _app["tables"]
        setup = engine.Setup(solar_model=solar_model.value, b8_flux=b8_flux.value, detector=detector.value,
                             channel=channel.value, recoil_threshold=threshold.value, site=site.value,
                             earth_model=earth_model.value, exposure=exposure.value or None)
        # The solar-model range of a rate needs only the fluxes (one day table); A_DN, where a single
        # flux cancels, needs every model's density profile (all day tables, ~12 MB).
        solar_range = "full" if quantity.value == "adn" else "fluxes"
        needed = {f"day_{m}" for m in (inputs["solar_models"] if solar_range == "full" else [setup.solar_model])}
        if engine.needs_night(quantity.value, setup.period):
            needed |= {f"night_{e}" for e in inputs["earth_models"]}
        for name in sorted(needed):
            status.object = f"Downloading {name}..."
            await fetch(f"{name}.npz")
        status.object = "Computing..."
        params = engine.parameters(inputs, parameter_set.value)
        rows, _ = engine.budget(inputs, tables, setup, params, quantity.value, n=300, seed=1, solar_range=solar_range)
        central = rows[0]["Central"]
        unit = "%" if quantity.value == "adn" else " per kt yr"
        scale = 100 if quantity.value == "adn" else 1
        lines = [f"**Central value: {central * scale:.4g}{unit}**", "", "| Source | Kind | Relative |", "|---|---|---|"]
        lines += [f"| {r['Source']} | {r['Kind']} | {100 * r['Relative']:.2f} % |" for r in rows]
        result.object = "\n".join(lines)
        figure.object = plot(rows, f"{parameter_set.value}, {channel.value}")
        status.object = f"{tables.clamped} draws outside the tables (clamped)" if tables.clamped else ""
    except Exception as error:  # shown in the page, where no console is at hand
        status.object = f"**Error:** {error!r}"
    finally:
        run.disabled = False


run.on_click(compute)
pn.state.onload(load)

pn.template.FastListTemplate(
    title="SNUfish: solar neutrino rates",
    theme="dark",
    sidebar=[parameter_set, solar_model, b8_flux, detector, channel, threshold, site, earth_model, quantity,
             exposure, run],
    main=[status, pn.Row(result, figure)],
).servable()
