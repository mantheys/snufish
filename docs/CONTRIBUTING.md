# Contributing results

What each benchmark asks for is in [benchmarks.md](benchmarks.md); open work
that needs a contributor is listed in [status.md](status.md).

1. Add or update your tool in `catalogue/tools/<tool>.yaml`.
2. Run your tool on the benchmark exactly as `benchmarks/<id>/spec.yaml`
   defines it (grid, parameters, matter model). Use the `native` variant,
   where offered, for your tool's own defaults.
3. Write `contributions/<tool>/<benchmark>/<tool_version>/data.parquet`
   (columns listed in the spec, one row per grid point and quantity) and
   `meta.yaml`:

   ```yaml
   tool: nufast-earth
   tool_version: "1.0"
   tool_commit: abc1234
   benchmark: B3_earth
   benchmark_version: 0.1.0
   contributor: Name (Institute)
   date: 2026-11-01
   command: ./bench_b3 --precision high > out.csv; python to_parquet.py
   settings: {precision: high}
   license: CC-BY-4.0
   reference: arXiv:xxxx.xxxxx     # optional
   notes: ...                      # optional
   ```

   `snufish.contribution.write_contribution` writes both from Python.
4. `snufish validate contributions/<tool>/<benchmark>/<version>` must pass:
   grid, required variants, value ranges and the benchmark's physics checks
   (for B3: unitarity and the vacuum limit at the horizon).
5. Open a pull request. CI lints (`ruff check .`), runs the tests and regenerates every plot with your results.

Keep the script that produced the data in your tool's repository (or under
`contributions/<tool>/scripts/`, as for `nufast-earth`) so anyone can
reproduce it.
