"""Contributions: ``contributions/<tool>/<benchmark>/<tool_version>/``
holding ``data.parquet`` (long format, columns from the spec) and
``meta.yaml`` (provenance)."""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .paths import contributions_dir
from .spec import load_spec, pmns

META_REQUIRED = {
    "tool": "catalogue id of the tool (catalogue/tools/<tool>.yaml)",
    "tool_version": "release or tag used",
    "tool_commit": "commit hash, or null for a release tarball",
    "benchmark": "benchmark id",
    "benchmark_version": "spec version the data was computed with",
    "contributor": "name (and affiliation)",
    "date": "YYYY-MM-DD",
    "command": "how the data was produced (script, command line)",
    "settings": "tool settings that matter (precision, Earth model for `native`, ...)",
    "license": "licence of the data (CC-BY-4.0 recommended)",
}
META_OPTIONAL = ("reference", "notes")


@dataclass
class Contribution:
    path: Path
    meta: dict
    data: pd.DataFrame
    problems: list = field(default_factory=list)

    @property
    def label(self):
        return f"{self.meta.get('tool')} {self.meta.get('tool_version')}"


def find_contributions(benchmark=None, roots=()):
    """Contribution directories (holding meta.yaml) under the repository's
    contributions/ and any extra roots (e.g. a private overlay)."""
    found = []
    for root in [contributions_dir(), *map(Path, roots)]:
        for meta in sorted(root.glob("*/*/*/meta.yaml")):
            if benchmark is None or meta.parent.parent.name == benchmark:
                found.append(meta.parent)
    return found


def load_contribution(path):
    path = Path(path)
    with (path / "meta.yaml").open() as handle:
        meta = yaml.safe_load(handle) or {}
    data = pd.read_parquet(path / "data.parquet")
    return Contribution(path=path, meta=meta, data=data)


def write_contribution(path, meta, records, spec):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    columns = ["grid", "variant", "quantity", *spec.grid_names, "value"]
    pd.DataFrame.from_records(records, columns=columns).to_parquet(path / "data.parquet", index=False)
    with (path / "meta.yaml").open("w") as handle:
        yaml.safe_dump(meta, handle, sort_keys=False)


def validate(contribution, spec=None):
    """Fill ``contribution.problems`` (empty when valid) and return it."""
    problems = contribution.problems = []
    meta, df = contribution.meta, contribution.data

    for key in META_REQUIRED:
        if key not in meta:
            problems.append(f"meta.yaml: missing '{key}' ({META_REQUIRED[key]})")
    for key in meta:
        if key not in META_REQUIRED and key not in META_OPTIONAL:
            problems.append(f"meta.yaml: unknown key '{key}'")
    if problems:
        return problems

    spec = spec or load_spec(meta["benchmark"])
    tool_dir, bench_dir, version_dir = contribution.path.parts[-3:]
    if (tool_dir, bench_dir, version_dir) != (meta["tool"], meta["benchmark"], str(meta["tool_version"])):
        problems.append(f"directory {tool_dir}/{bench_dir}/{version_dir} does not match meta.yaml")
    if str(meta["benchmark_version"]) != spec.version:
        problems.append(f"computed with spec {meta['benchmark_version']}, current spec is {spec.version}")

    columns = ["grid", "variant", "quantity", *spec.grid_names, "value"]
    missing = [c for c in columns if c not in df.columns]
    if missing:
        problems.append(f"data.parquet: missing columns {missing}")
        return problems

    unknown = set(df["variant"]) - set(spec.variants)
    if unknown:
        problems.append(f"unknown variants {sorted(unknown)}")
    unknown = set(df["grid"]) - set(spec.grids)
    if unknown:
        problems.append(f"unknown grids {sorted(unknown)}")
    for name, variant in spec.variants.items():
        if variant.get("required") and name not in set(df["variant"]):
            problems.append(f"required variant '{name}' missing")
    for variant, sub in df.groupby("variant"):
        missing = set(spec.grids) - set(sub["grid"])
        if missing:
            problems.append(f"[{variant}] grids {sorted(missing)} missing")
    if problems:
        return problems

    for (variant, grid), sub in df.groupby(["variant", "grid"]):
        problems += _check_grid(sub, spec, variant, grid)
    if problems:
        return problems

    low, high = spec["checks"]["range"]
    outside = df[(df["value"] < low) | (df["value"] > high) | ~np.isfinite(df["value"])]
    if len(outside):
        problems.append(f"{len(outside)} values outside [{low}, {high}] or not finite")

    checker = BENCHMARK_CHECKS.get(spec.id)
    if checker:
        problems += checker(df, spec)
    return problems


def _check_grid(df, spec, variant, grid):
    problems = []
    where = f"[{variant}/{grid}]"
    for name in spec.grid_names:
        expected = spec.axis(name, grid)
        got = np.sort(df[name].unique())
        if len(got) != len(expected) or not np.allclose(got, expected, atol=1e-9):
            problems.append(f"{where} {name} grid differs from the spec ({len(got)} vs {len(expected)} points)")
    quantities = set(df["quantity"])
    if quantities != set(spec.quantities):
        problems.append(f"{where} quantities {sorted(quantities)}, expected {spec.quantities}")
    n_expected = len(spec.quantities) * int(np.prod([len(spec.axis(n, grid)) for n in spec.grid_names]))
    if len(df) != n_expected or df.duplicated(["quantity", *spec.grid_names]).any():
        problems.append(f"{where} {len(df)} rows, expected {n_expected} unique grid points")
    return problems


def _check_b3(df, spec):
    problems = []
    checks = spec["checks"]
    wide = df.pivot_table(index=["grid", "variant", "energy", "cos_nadir"], columns="quantity", values="value")
    total = wide[["P1e", "P2e", "P3e"]].sum(axis=1)
    worst = np.abs(total - 1).max()
    if worst > checks["unitarity_tolerance"]:
        problems.append(f"unitarity: |P1e + P2e + P3e - 1| reaches {worst:.2e}")

    vacuum = np.abs(pmns(spec["oscillation"])[0]) ** 2
    horizon = wide.xs(0.0, level="cos_nadir")
    for i, name in enumerate(("P1e", "P2e", "P3e")):
        worst = np.abs(horizon[name] - vacuum[i]).max()
        if worst > checks["horizon_tolerance"]:
            problems.append(f"horizon: {name} differs from |U_e{i + 1}|^2 by {worst:.2e} at cos_nadir = 0")
    return problems


BENCHMARK_CHECKS = {"B3_earth": _check_b3}
