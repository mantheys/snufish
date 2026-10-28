# SNUfish

Community benchmarks of solar neutrino tools. Every tool computes the same
fixed problem; SNUfish validates the outputs and plots them side by side
with [plotipus](https://github.com/mantheys/plotipus), so users can see
which tools agree, where and by how much.

(The name: the Solar Neutrino Unit, the Sun, nu, and a fish to swim with
plotipus.)

## Layout

```
benchmarks/<id>/spec.yaml        fixed inputs, grids and checks of one benchmark
catalogue/tools/<tool>.yaml      tool entries
contributions/<tool>/<benchmark>/<tool_version>/
    data.parquet                 long format, columns set by the spec
    meta.yaml                    provenance (tool, version, commit, settings, ...)
reference/                       shared inputs (solar models, measurements)
input/plots/<list>_scripts.txt   plotipus command lists
src/snufish/                     validator, builder, reference solvers
```

## Use

```bash
pip install -e ".[dev,plots]"
snufish validate                 # check every contribution against its spec
snufish build                    # validated Parquet -> build/data/*.pkl for plotipus
plotipus run b3                  # figures in output/plots
pytest
```

Pickles exist only in `build/` and are made locally from Parquet: they are
never committed or exchanged.

`snufish build --extra ../some-overlay/contributions` adds contributions kept
outside this repository (e.g. results not yet public) to a local build.

## Benchmarks

See [benchmarks/README.md](benchmarks/README.md). The first one is
**B3_earth**: P(nu_i -> nu_e) for mass eigenstates crossing a fixed
four-shell Earth, on a (E, cos nadir) grid. The SNUfish reference solver
(exact matrix exponentials per shell) and NuFast-Earth are its first
contributions; on the constant-shell `prem_prob3` Earth they agree to
6e-8 at every grid point.

## Contributing

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).
