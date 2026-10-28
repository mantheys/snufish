"""Turn validated contributions into the frames plotipus reads
(``build/data/*.parquet``, never committed).

plotipus wants one row per series with whole arrays in the cells; the
builders below pivot the long-format contributions into those rows.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from .contribution import find_contributions, load_contribution, validate
from .paths import build_dir
from .spec import load_spec, pmns


def _series_rows(df, keys, x, values, base):
    rows = []
    for group, sub in df.groupby(keys, sort=True):
        sub = sub.sort_values(x)
        row = dict(base, **dict(zip(keys, group)))
        row[x] = sub[x].to_numpy()
        for name in values:
            row[name] = sub[name].to_numpy()
        rows.append(row)
    return rows


def _build_b3(contributions, spec):
    from .exposure import cell_weights

    vacuum = dict(zip(("P1e", "P2e", "P3e"), np.abs(pmns(spec["oscillation"])[0]) ** 2))
    cos_exposure = spec.axis("cos_nadir", "exposure")
    weights = {site: cell_weights(cos_exposure, np.radians(info["latitude_deg"]))
               for site, info in spec["sites"].items()}
    by_energy, by_nadir, maps, nights = [], [], [], []
    for contribution in contributions:
        meta = contribution.meta
        df = contribution.data.rename(columns={"grid": "Grid", "variant": "Variant", "quantity": "Quantity",
                                               "energy": "Energy", "cos_nadir": "CosNadir",
                                               "value": "Probability"})
        df["Regeneration"] = df["Probability"] - df["Quantity"].map(vacuum)
        df["Nadir"] = df["CosNadir"].map(lambda c: f"{c:.2f}")
        df["EnergyBin"] = df["Energy"].map(lambda e: f"{e:.1f}")
        base = {"Tool": meta["tool"], "Version": str(meta["tool_version"]), "Label": contribution.label}
        fine = df[df["Grid"] == "exposure"]

        # Curves against energy from the map grid (fine in E), against the
        # nadir from the exposure grid (fine in cos eta).
        values = ("Probability", "Regeneration")
        by_energy += _series_rows(df[df["Grid"] == "map"], ["Variant", "Quantity", "Nadir"], "Energy", values, base)
        by_nadir += _series_rows(fine, ["Variant", "Quantity", "EnergyBin"], "CosNadir", values, base)
        for (grid_name, variant, quantity), sub in df.groupby(["Grid", "Variant", "Quantity"]):
            grid = sub.pivot(index="CosNadir", columns="Energy", values="Probability")
            regeneration = sub.pivot(index="CosNadir", columns="Energy", values="Regeneration")
            maps.append(dict(base, Grid=grid_name, Variant=variant, Quantity=quantity,
                             EnergyGrid=grid.columns.to_numpy(), CosNadirGrid=grid.index.to_numpy(),
                             ProbabilityGrid=grid.to_numpy(), RegenerationGrid=regeneration.to_numpy()))

        # Night averages per site: P_ie weighted with the annual exposure.
        for (variant, quantity), sub in fine.groupby(["Variant", "Quantity"]):
            grid = sub.pivot(index="Energy", columns="CosNadir", values="Probability")
            assert np.allclose(grid.columns.to_numpy(), cos_exposure)
            for site, w in weights.items():
                night = grid.to_numpy() @ w
                nights.append(dict(base, Variant=variant, Quantity=quantity, Site=site,
                                   Latitude=spec["sites"][site]["latitude_deg"], Energy=grid.index.to_numpy(),
                                   Night=night, Regeneration=night - vacuum[quantity]))
    return {
        "B3_Energy": pd.DataFrame(by_energy),
        "B3_Nadir": pd.DataFrame(by_nadir),
        "B3_Map": pd.DataFrame(maps),
        "B3_Night": pd.DataFrame(nights),
    }


BUILDERS = {"B3_earth": _build_b3}


def _write_frame(frame, path):
    # As plotipus.save_frame: 2D array cells are stored as lists of rows,
    # which plotipus reads back as 2D arrays.
    frame = frame.copy()
    for column in frame.columns:
        if frame[column].dtype == object:
            frame[column] = frame[column].map(
                lambda value: list(value) if isinstance(value, np.ndarray) and value.ndim == 2 else value)
    frame.to_parquet(path, index=False)


def build(benchmark, extra_roots=(), out_dir=None, strict=True, echo=print):
    """Validate every contribution to ``benchmark`` and write its plotipus
    frames. Invalid contributions stop the build (``strict``) or are skipped."""
    spec = load_spec(benchmark)
    good = []
    for path in find_contributions(benchmark, extra_roots):
        contribution = load_contribution(path)
        problems = validate(contribution, spec)
        if problems:
            echo(f"INVALID {path}")
            for problem in problems:
                echo(f"  - {problem}")
            if strict:
                raise SystemExit(1)
            continue
        echo(f"ok      {path}")
        good.append(contribution)
    if not good:
        echo(f"no valid contributions for {benchmark}")
        return {}

    out_dir = Path(out_dir) if out_dir else build_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = BUILDERS[benchmark](good, spec)
    for name, frame in frames.items():
        _write_frame(frame, out_dir / f"{name}.parquet")
        echo(f"wrote   {out_dir / name}.parquet ({len(frame)} rows)")
    return frames
