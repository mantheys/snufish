# Usage

## Installation

```bash
git clone --recurse-submodules https://github.com/mantheys/snufish && cd snufish
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,plots]"          # plots: plotipus; dev: pytest
```

Python ≥ 3.10; the package needs NumPy, pandas, PyArrow, PyYAML and SciPy
(for the BKS radiative corrections). The repository root is found by
walking up from the working directory to the folder holding `benchmarks/`,
or set with `SNUFISH_ROOT`.

Everything that runs the night solver needs the NuFast-Earth driver:

```bash
git submodule update --init                    # if cloned without --recurse-submodules
make -C contributions/nufast-earth/scripts     # builds b2_driver and b3_driver
```

## Command line

| Command | Does | Needs |
|---|---|---|
| `snufish validate [paths…]` | check contributions against their specs (all by default) | — |
| `snufish build` | validate, then write plotipus frames to `build/data/` | — |
| `snufish reference <B2_sun\|B3_earth\|B4_xsec>` | recompute the SNUfish reference contribution | — |
| `snufish scan` | solar observables against Δm²₂₁ and at each parameter set | NuFast-Earth driver |
| `snufish status` | which inputs are the state of the art, legacy or approximations (`reference/status.yaml`) | — |
| `snufish budget` | error budgets of the ⁸B rates and A_DN | `build`, NuFast-Earth driver (or `--tables`) |
| `snufish export-app` | inputs and probability tables of the web page | `build`, NuFast-Earth driver |
| `snufish export-sections` | `sections.json` of the benchmark pages: what each benchmark contributes to the uncertainty | `export-app`, `build` |

### `snufish validate`

```bash
snufish validate                                       # every contribution
snufish validate contributions/nufast-earth/B3_earth/1.2.0-3-g327586d
snufish validate --benchmark B4_xsec
snufish validate --extra ../private/contributions      # also contributions kept elsewhere
```

Prints `ok` or `INVALID` per contribution with each problem; exits 1 if any
is invalid. The checks are listed in
[architecture.md](architecture.md#validation).

### `snufish build`

```bash
snufish build                                # everything
snufish build --benchmark B3_earth B2_sun    # some benchmarks (B1 and the combinations always run)
snufish build --extra ../private/contributions --skip_invalid --out /tmp/data
```

Writes the frames below. Stops at the first invalid contribution unless
`--skip_invalid`.

### `snufish scan`

```bash
snufish scan --dm2_min 4 --dm2_max 10 --dm2_step 0.2 --site Kamioka --solar_model b16_gs98
plotipus run scan
```

Δm²₂₁ in 10⁻⁵ eV². Writes `Scan_DM21` and `Scan_Sets`
([methods.md](methods.md#snufish-scan)).

### `snufish budget`

```bash
snufish budget --sets juno_2025 solar_global_2024 --solar_model b23_mb22m --n 400 --seed 1
snufish budget --tables build/app            # the app tables instead of the exact solvers
plotipus run budget
```

Writes `Budget`, `Budget_Samples` and `Budget_Predictions`
([methods.md](methods.md#snufish-budget)). Model ranges run over the
state-of-the-art models; a legacy solar model or parameter set is
accepted, with a note.

### `snufish export-app`

```bash
snufish export-app --out build/app                       # ~3 min on 8 cores
snufish export-app --s12 0.24 0.38 0.01 --dm21 3 11 0.2  # the (sin^2 theta12, Delta m^2_21) grid
snufish export-app --inputs-only                         # rewrite inputs.json only
snufish export-app --jobs 4
```

Writes `inputs.json`, `day_<solar model>.{json,bin}`,
`night_<Earth model>.{json,bin}` and a manifest
([methods.md](methods.md#app-tables)).

### `snufish export-sections`

```bash
snufish export-sections --tables build/app   # a few seconds; writes build/app/sections.json
```

The data of `benchmarks.html`, one page per benchmark. For five reference
observables (⁸B ES in water, ⁸B and hep CC on ⁴⁰Ar, ⁷Be ES in scintillator,
the ES day-night asymmetry; `sections.OBSERVABLES`) it runs the error budget
on the app tables and assigns every source to the benchmark it comes from:
B1 the fluxes (sampled, and the range between models with the production
profiles fixed), B2 the density and production profiles (the range between
models with the fluxes fixed), B3 the Earth model, B4 the cross sections; the
oscillation parameters are shown apart. B2 also gets the shift of three
production-region approximations, computed with the exact B2 solver: every
component on ⁸B's profile, every component at the centre, and one density
for every component (n_e = 66.7 N_A/cm³, as in NuFast-Earth's examples).
With them: the curves each page plots and the agreement between tools (B2,
B3: largest difference from the reference; B5: full-chain rates over
SNUfish's folding).

## Scripts

| Script | Does |
|---|---|
| `scripts/import_ssm.py --b23 <dir> --peanuts <dir>` | convert the published solar model tables into `reference/ssm/` and `benchmarks/B1_ssm/models.yaml` (inputs read as numbers only) |
| `scripts/crosscheck.py [--exact]` | recompute the published numbers of [crosschecks.md](crosschecks.md) (app tables, or with `--exact` the B2 solver and NuFast-Earth); needs `build/app` |
| `scripts/readme_images.py` | render the README figures (`input/plots/readme_scripts.txt`) in light and dark into `docs/images/` |
| `contributions/<tool>/scripts/run_*.py` | produce a tool's contribution (see each script's docstring for how to build the tool) |

## Plots

`plotipus.toml` points plotipus at `build/data` (data),
`input/plots` (command lists) and `output/` (figures), and loads
`snufish.plotipus_plugin` (axis labels for SNUfish columns).

| `plotipus run …` | Figures | Frames |
|---|---|---|
| `b1` | solar model fluxes, densities, production profiles | `B1_*` |
| `b2` | F_i, daytime P_ee per component, day-night | `B2_*`, `B23_DayNight` |
| `b3` | P_iₑ against energy and nadir, maps, night averages, tool differences | `B3_*` |
| `b45` | cross sections, rate spectra and totals, full-chain comparison | `B4_Sigma`, `B5_*` |
| `scan` | observables against Δm²₂₁ | `Scan_*` |
| `budget` | error budgets and predictions | `Budget*` |
| `readme` | the README figures | various |
| `app` | the calculator's figures, from its download | the downloaded Parquet |

Add `--jobs N` to render in parallel.

## Output frames

All in `build/data/`, one row per series with arrays in the cells.

| Frame | Columns |
|---|---|
| `B1_Fluxes` | Model, Family, Composition, Component, Flux, RelativeFlux, RelativeFluxError |
| `B1_Profiles` | Model, Family, Composition, Radius, LogNe |
| `B1_Production` | Model, Family, Composition, Component, Radius, Density |
| `B2_Energy` | Tool, Version, Label, Variant, Quantity, RadiusBin, Energy, Fraction |
| `B2_Average` | Tool, Version, Label, Variant, Component, Energy, F1, F2, F3, PeeDay |
| `B3_Energy` | Tool, Version, Label, Variant, Quantity, Nadir, Energy, Probability, Regeneration |
| `B3_Nadir` | Tool, Version, Label, Variant, Quantity, EnergyBin, CosNadir, Probability, Regeneration |
| `B3_Map` | Tool, Version, Label, Grid, Variant, Quantity, EnergyGrid, CosNadirGrid, ProbabilityGrid, RegenerationGrid |
| `B3_Night` | Tool, Version, Label, Variant, Quantity, Site, Latitude, Energy, Night, Regeneration |
| `B23_DayNight` | Tool, Version, Label, SunVariant, EarthVariant, Site, Component, Energy, PeeDay, PeeNight, ADN |
| `B4_Sigma` | Tool, Version, Label, Variant, Channel, Model, Energy, Sigma, SigmaPerE |
| `B5_Spectrum` | SolarModel, Tool, Version, Label, Variant, Model, Detector, Channel, Component, Binning, Energy, Rate, EnergyLow, EnergyHigh |
| `B5_Totals` | SolarModel, Tool, Version, Label, Variant, Model, Detector, Channel, Component, Total, Above5, Coverage |
| `B5_Chain` | Tool, Version, Variant, SolarModel, Detector, Channel, Component, Threshold, Case, Rate, Folded, Coverage, Ratio |
| `Scan_DM21` | EarthModel, Site, SolarModel, Observable, DM21, Value |
| `Scan_Sets` | Set, Label, Kind, EarthModel, Site, DM21, adn_es, adn_pee, pee_10, slope_10, upturn, chi2_quadratic |
| `Budget` | Quantity, Label, Set, SolarModel, Flux, Central, Source, Kind, Sigma, Relative, Low, High |
| `Budget_Samples` | Quantity, Label, Set, SolarModel, Flux, Central, Source, Values |
| `Budget_Predictions` | Quantity, Label, Set, Flux, Value, Series, ValueError-, ValueError+, Position |

## Python API

The engine takes an inputs dict and a probability provider
([architecture.md](architecture.md#engine)). With the app tables:

```python
from snufish import engine

inputs = engine.Inputs.load("build/app/inputs.json")
probs = engine.TableProbabilities("build/app")      # or snufish.export.ExactProbabilities()
setup = engine.Setup(solar_model="b16_gs98", components=("B8",), detector="water", channel="es",
                     site="Kamioka", earth_model="prem_full", threshold=3.49, period="annual")
params = engine.parameters(inputs, "nufit60_global")              # custom={"dm2_21_eV2": 6.1e-5} overrides
osc = engine.oscillation(params)

per = engine.component_totals(inputs, probs, setup, osc)          # {component: {"day", "night"}}
day, night, ref = engine.combine(per, list(setup.components))     # ref: the rate without oscillations
adn = engine.quantity_value("adn", setup.period, day, night)      # 2 (N - D) / (N + D)

rows, samples = engine.budget(inputs, probs, setup, params, quantity="adn", n=400, seed=1)
for row in rows:
    print(row["Source"], row["Kind"], row["Sigma"], row["Low"], row["High"])
```

Other entry points: `engine.spectra` (rates in display bins of observed
energy, with sampled bands), `engine.component_spectra`,
`engine.flux_summary`, `engine.check` (validate a setup), `engine.Table`
(an imported efficiency curve or smearing matrix). `Setup` fields are
documented in `src/snufish/engine.py`; the main ones:

| Field | Values |
|---|---|
| `solar_model` | a B1 model id |
| `components` | tuple of pp, pep, hep, Be7, B8, N13, O15, F17 |
| `b8_flux` | `model` or `sno_nc` (measured) |
| `site`, `earth_model` | a B3 site; `prem_prob3`, `prem_four`, `prem_full` |
| `detector`, `channel` | `water` (es, cc_nue_o16), `argon` (es, cc_nue_ar40, nc_ar40), `scintillator_pc`, `scintillator_lab` (es), `heavy_water` (es, cc_nue_d, nc_d) |
| `es_model`, `xsec_model` | `bks`, `tree`, `snowglobes`; a B4 variant of the channel |
| `period` | `day`, `night`, `annual` |
| `night_fraction` | share of the exposure by night (default 0.5): annual = (1 − f) day + f night, and the statistics split the exposure the same way; SOLAR uses 0.507 at SURF |
| `nu_threshold` | MeV: a cut in true neutrino energy, on top of the observed-energy `threshold` (for tables "above E_ν"); exact inside a flux interval |
| detector response | `threshold`, `resolution_a`, `resolution_b`, `resolution_poly`, `efficiency`, `efficiency_e50`, `efficiency_width`, `efficiency_table`, `smearing_table` |
| uncertainties | `energy_scale_error`, `resolution_error`, `normalisation_error` (fractions), `exposure` (kt·yr) |

`nc_ar40` (NC on ⁴⁰Ar, all flavours) is SNOwGLoBES's table, an unpublished
QRPA calculation (`reference/xsec/snowglobes_nc_ar40.yaml`); it has no
visible-energy model, so its observed axis is the neutrino energy and
`threshold` is a cut in E_ν.

`snufish.export.ExactProbabilities(night_mode="solar")` takes the night of
the SOLAR analysis: detector 1.478 km deep, latitude 44.35°, W(η) sampled at
the centres of 80 night bins in cos nadir (SOLAR's 40 bins × 4
oversampling over [−1, 1]); the Earth model is still `setup.earth_model`
(SOLAR's is set in its NuFast-Earth binding, which is not in its
repository). `depth_km`, `latitude_deg` and `nadir_bins` override each
piece. `night_fraction`, `nu_threshold` and the SOLAR night are Python only:
the calculator does not offer them yet.

Lower-level pieces: `snufish.reference.sun.adiabatic_fractions`,
`snufish.reference.earth.probabilities_ie`,
`snufish.reference.xsec.es_total` / `es_above`,
`snufish.reference.radiative.es_differential` / `es_above`,
`snufish.exposure.solar_weight` / `cell_weights`,
`snufish.solar.electron_density` / `production_weights` / `fluxes`,
`snufish.scan.observables`.

## The calculator

[mantheys.github.io/snufish/rates.html](https://mantheys.github.io/snufish/rates.html).

**Steps.** Each step has an "i" button with the sources of what is
selected. Every choice is labelled state of the art, legacy or
approximation, with the reason under the control; the result says
whether every input is current ([status-of-inputs.md](status-of-inputs.md)).

0. **Result**: interaction rate, day-night asymmetry, or the rate over the
   rate without oscillations (SNO's φ_CC/φ_NC for CC on deuterium); day,
   night or annual; units per kt·yr, t·yr, kg·yr, g·yr, kt·day or
   cpd/100 t.
1. **Oscillation parameters**: a parameter set.
2. **Sun**: solar model, flux components, ⁸B flux from the model or
   measured (SNO NC).
3. **Earth**: site and Earth model.
4. **Interaction**: target, channel, ES cross section (BKS, tree level,
   SNOwGLoBES) or nuclear model.
5. **Detector**: a preset or custom threshold, resolution (quadrature
   formula, Super-K IV, or an imported smearing matrix), efficiency
   (logistic turn-on, or an imported curve), exposure for the statistical
   error, and detector uncertainties (energy scale, resolution, rate).
   Imported files are read in the browser and never uploaded.

**Results.** The headline value with its sampled σ and model ranges, the
flux summary, the spectrum in observed energy (per component, with the
sampled band), the distribution of sampled values, the error budget as a
figure and a table.

**Result Templates.** Sets every step to a paper's inputs (or the thumb example) and
shows its number next to SNUfish's; grouped by result (rates, flux ratios,
day-night asymmetry), each linked to its paper, several with the paper's
official figure recomputed ([crosschecks.md](crosschecks.md)).

**Actions.** "Render with plotipus" draws the plotipus figures in the
browser (Pyodide in a worker, ~15 s the first time, ~2 s after);
"Download" gives a zip with the result as Parquet, the figures, a plotipus
command list and colour registry (`plotipus run app`); "Copy link" encodes
the setup in the URL (imported files are not part of it).

**Accuracy.** Probabilities come from the app tables: 2 × 10⁻⁴ for rates
and 1 % for A_DN against the exact solvers.

### Building and deploying the page

```bash
snufish build && snufish export-app --out build/app
python web/build.py --out build/site            # --plotipus <checkout> (default ../plotipus), --tables <dir>
python -m http.server -d build/site             # http://localhost:8000
bash web/deploy.sh                              # build and force-push to gh-pages (needs a clean tree)
```

CI does the last step on every push to `main` once lint and tests pass
(the `deploy` job in `.github/workflows/ci.yml`).

`web/build.py --artifact` builds a variant for hosts that cannot fetch
from other origins (bundled Pyodide, no downloads or shareable links).
The JavaScript engine is checked by `tests/test_web_engine.py`, which
writes fixtures and runs `node web/test/engine.test.mjs <fixtures> <tables>`
(skipped without Node.js or `build/app`).
