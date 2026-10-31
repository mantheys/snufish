# Architecture

SNUfish has two halves that share their inputs:

- the **benchmarks**: fixed problems, contributed results, validation and
  side-by-side plots;
- the **engine**: rates, asymmetries and uncertainty budgets computed with
  the solvers the benchmarks validate, from the command line or in the web
  page.

```text
                     reference/ (solar models, spectra, parameter sets, measurements, detectors)
                                │
  benchmarks/<id>/spec.yaml ────┼──────────────────────────────┐
        │                       │                              │
        ▼                       ▼                              ▼
  tool runs the spec     snufish reference <id>          snufish.export.collect_inputs
        │                       │                              │
        ▼                       ▼                              ▼
  contributions/<tool>/<id>/<version>/{data.parquet, meta.yaml}    inputs.json + probability tables
        │                                                      │        (snufish export-app)
        ▼                                                      ▼
  snufish validate  ──►  snufish build  ──►  build/data/*.parquet       snufish.engine  ◄──►  web/engine.js
                                                 │                       │         │              │
                                                 ▼                       ▼         ▼              ▼
                                         plotipus run b1|b2|b3|b45   snufish scan  snufish budget  rates.html
```

## Specs

`benchmarks/<id>/spec.yaml` fixes everything a contribution depends on:
grids, oscillation parameters, physical constants, matter models, variants
(model alternatives a tool may also run), the long-format columns and the
checks. `snufish.spec.load_spec` reads it (guarding against YAML 1.1
reading numbers such as `1e23` as strings) and `snufish.spec.pmns` builds
the PMNS matrix from its `oscillation` block. A spec has a `version`; once
frozen, any change bumps it and old contributions keep the version they
were computed with.

## Contributions

`contributions/<tool>/<benchmark>/<tool_version>/` holds:

- `data.parquet`: long format, one row per grid, grid point and quantity,
  with the columns the spec lists (`grid`, `variant`, `quantity`, the grid
  axes, `value`);
- `meta.yaml`: tool, version, commit, benchmark and its version,
  contributor, date, command, settings, licence, optional reference and
  notes.

`snufish.contribution.write_contribution` writes both. The scripts that
produced a contribution live in the tool's repository or under
`contributions/<tool>/scripts/` (NuFast-Earth is pinned as a git
submodule there).

## Validation

`snufish validate` (`snufish.contribution.validate`) checks each
contribution against its spec:

- `meta.yaml` has every required key and no unknown one, matches its
  directory (`<tool>/<benchmark>/<tool_version>`), and was computed with
  the current spec version;
- the columns, variants, grids and quantities are the spec's; required
  variants are present; every grid point appears exactly once, on the
  spec's axes;
- values are finite and within the spec's `range` (NaN allowed only where
  the spec sets `allow_missing`, as for cross sections outside a tool's
  table);
- physics checks: B2 and B3 unitarity (F₁ + F₂ + F₃ = 1,
  P₁ₑ + P₂ₑ + P₃ₑ = 1 to 10⁻⁶), the B3 vacuum limit at the horizon
  (P_iₑ = |U_eᵢ|² at cos η = 0, to 10⁻⁶), and for B4
  σ(νₑe) > σ(ν_μe), σ(ν_τe) wherever given.

## Build

`snufish build` (`snufish.build`) validates every contribution (stopping
at the first invalid one unless `--skip_invalid`), then pivots the long
format into plotipus frames, one row per series with whole arrays in the
cells, in `build/data/` (never committed). It also derives:

- `B1_*`: flux ratios to the reference solar model, electron density and
  production profiles;
- `B23_DayNight`: day and night P_ee and A_DN from every B2 × B3 pair
  (tool, solar model, Earth model, site, component);
- `B5_Spectrum`, `B5_Totals`: SNUfish's folding of every B4 cross-section
  model with every B1 solar model and the B2 reference oscillations;
- `B5_DayNight`: the same totals by day, by night and over the year, per
  site and Earth model (B3 reference night excess);
- `B5_Chain`: full-chain tool rates next to SNUfish's folding of the same
  inputs.

`--extra <dir>` adds contribution roots outside the repository (private
overlays) to a local build. The frames and their columns are listed in
[usage.md](usage.md#output-frames).

## Reference solvers

`src/snufish/reference/` holds one baseline per benchmark, contributed as
the tool `snufish-reference` by `snufish reference <id>`:

| Module | Benchmark | Method |
|---|---|---|
| `sun.py` | B2 | adiabatic three-flavour fractions at the production point |
| `earth.py` | B3 | exact evolution through piecewise-constant matter (one matrix exponential per segment) |
| `xsec.py` | B4 | tree-level Standard Model ν–e elastic scattering |
| `radiative.py` | (engine) | ν–e elastic scattering with the Bahcall–Kamionkowski–Sirlin radiative corrections |

The methods are in [methods.md](methods.md).

## Engine

`snufish.engine` computes observed spectra, totals, A_DN, flux ratios and
error budgets from two things:

- an **inputs dict** (fluxes, spectral shapes, cross-section tables,
  detector targets, sites, parameter sets, measurements, efficiency
  curves), built by `snufish.export.collect_inputs` from the repository
  and the build (it needs `build/data/B4_Sigma.parquet`);
- a **probability provider** with `day(osc, solar_model, component,
  energies)` → F_i(E) and `night(osc, earth_model, site)` → night-averaged
  P(νᵢ → νₑ). `ExactProbabilities` runs the B2 solver and NuFast-Earth;
  `TableProbabilities` interpolates the tables of an app bundle.

A `Setup` holds every choice except the oscillation parameters (solar
model, components, ⁸B flux treatment, site, Earth model, detector, channel,
cross-section model, period, detector response, exposure, detector
uncertainties); `engine.check` rejects inconsistent setups with what is
allowed. Everything is NumPy, so the same code ports to JavaScript.

`snufish scan` (`snufish.scan`) and `snufish budget`
(`snufish.uncertainty`) are analyses on top of it.

## Web page

`web/` is a static site: `index.html` (home and credits) and `rates.html`
(the calculator). `web/engine.js` ports `snufish.engine`;
`tests/test_web_engine.py` runs both on the same inputs and random draws and
requires agreement to 10⁻⁹ (it is ~10⁻¹⁴). Other modules:

| File | Role |
|---|---|
| `app.js` | the form, presets, published checks, sharing links, result rendering |
| `plots.js` | Plotly figures in plotipus's look |
| `sources.js` | the source of every input, per calculator step, and the home page credits |
| `checks.js` | published numbers the page reproduces with one selection |
| `official.js` | official figures of those papers, recomputed |
| `export.js` | the download: Parquet, figures, plotipus command list and colour registry |
| `plotipus-worker.js` | plotipus in a Web Worker through Pyodide |
| `build.py`, `deploy.sh` | assemble `build/site` and publish it to the `gh-pages` branch |

## Tests and CI

`pytest` covers the contribution format and validator, the B2 and B3
reference solvers, the solar model registry, the night exposure, the
cross sections and rate folding, the scan and budget, the engine against
the exact solvers (`test_engine.py`) and the JavaScript port
(`test_web_engine.py`, `web/test/engine.test.mjs`). CI
(`.github/workflows/ci.yml`) runs the tests, validates and builds every
contribution and regenerates the plots of `b1`, `b2`, `b3` and `b45` as an
artifact.
