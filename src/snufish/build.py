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


def _build_b2(contributions, spec):
    from .solar import production_weights

    vacuum = np.abs(pmns(spec["oscillation"])[0]) ** 2
    radii = spec.axis("radius")
    weights = production_weights(spec, radii)
    by_energy, averages = [], []
    for contribution in contributions:
        meta = contribution.meta
        df = contribution.data.rename(columns={"variant": "Variant", "quantity": "Quantity", "energy": "Energy",
                                               "radius": "Radius", "value": "Fraction"})
        df["RadiusBin"] = df["Radius"].map(lambda r: f"{r:.3f}")
        base = {"Tool": meta["tool"], "Version": str(meta["tool_version"]), "Label": contribution.label}
        by_energy += _series_rows(df, ["Variant", "Quantity", "RadiusBin"], "Energy", ("Fraction",), base)

        for variant, sub in df.groupby("Variant"):
            # F[radius, energy, i] on the spec grid
            cube = np.stack([sub[sub.Quantity == f"F{i}"].pivot(index="Radius", columns="Energy", values="Fraction")
                             .reindex(index=radii).to_numpy() for i in (1, 2, 3)], axis=-1)
            energies = np.sort(sub["Energy"].unique())
            for component, w in weights.items():
                F = np.einsum("r,rei->ei", w, cube)
                averages.append(dict(base, Variant=variant, Component=component, Energy=energies,
                                     F1=F[:, 0], F2=F[:, 1], F3=F[:, 2], PeeDay=F @ vacuum))
    return {"B2_Energy": pd.DataFrame(by_energy), "B2_Average": pd.DataFrame(averages)}


def _build_b4(contributions, spec):
    rows = []
    for contribution in contributions:
        meta = contribution.meta
        base = {"Tool": meta["tool"], "Version": str(meta["tool_version"]), "Label": contribution.label}
        for (variant, channel), sub in contribution.data.groupby(["variant", "quantity"]):
            sub = sub.sort_values("energy")
            energy, sigma = sub["energy"].to_numpy(), sub["value"].to_numpy()
            rows.append(dict(base, Variant=variant, Channel=channel, Model=f"{meta['tool']}: {variant}",
                             Energy=energy, Sigma=sigma, SigmaPerE=sigma / energy))
    return {"B4_Sigma": pd.DataFrame(rows)}


BUILDERS = {"B2_sun": _build_b2, "B3_earth": _build_b3, "B4_xsec": _build_b4}

def combine_rates(out_dir=None, echo=print):
    """B5: interaction rates per B4 model, detector, channel and flux
    component (daytime oscillations from the B2 reference), in events per
    kton-year: spectra in 0.1 MeV bins of neutrino energy and totals."""
    from .fluxes import components

    out_dir = Path(out_dir) if out_dir else build_dir()
    sun_path, xs_path = out_dir / "B2_Average.parquet", out_dir / "B4_Sigma.parquet"
    if not (sun_path.exists() and xs_path.exists()):
        return None
    spec, sun_spec = load_spec("B5_rates"), load_spec("B2_sun")
    U2 = np.abs(pmns(sun_spec["oscillation"])) ** 2  # [alpha, i]
    sun = pd.read_parquet(sun_path)
    sun = sun[(sun.Tool == "snufish-reference") & (sun.Variant == "b16_gs98")].set_index("Component")
    xs = pd.read_parquet(xs_path)
    fluxes = components(spec)
    seconds = spec["exposure"]["seconds_per_year"] * spec["exposure"]["kton_year"]
    edges = np.round(np.arange(0.0, 20.0001, 0.1), 6)
    centres = 0.5 * (edges[1:] + edges[:-1])

    def oscillation(component, energy):
        row = sun.loc[component]
        F = np.stack([np.interp(energy, row.Energy, row[f"F{i}"]) for i in (1, 2, 3)], axis=-1)
        return F @ U2.T  # P_{e alpha}(E), alpha = e, mu, tau

    spectra, totals = [], []
    for (tool, version, label, variant), models in xs.groupby(["Tool", "Version", "Label", "Variant"]):
        sigma = {row.Channel: row for row in models.itertuples()}
        for detector, info in spec["detectors"].items():
            for channel, target in info["channels"].items():
                flavours = spec["channels"][channel]["flavours"]
                threshold = spec["channels"][channel]["threshold_MeV"]
                if not all(name in sigma for name in flavours.values()):
                    continue
                n_targets = info["targets"][target]

                def folded(component, energy):
                    P = oscillation(component, energy)
                    total, missing = np.zeros_like(energy), np.zeros_like(energy, dtype=bool)
                    for k, flavour in enumerate(("nue", "numu", "nutau")):
                        if flavour not in flavours:
                            continue
                        row = sigma[flavours[flavour]]
                        s = np.interp(energy, row.Energy, row.Sigma, left=np.nan, right=np.nan)
                        zero = (energy < threshold) | (energy < row.Energy[0])
                        s = np.where(zero, 0.0, s)
                        missing |= np.isnan(s)
                        total += P[..., k] * np.nan_to_num(s)
                    return total, missing

                total_spectrum = np.zeros(len(centres))
                for component, flux in fluxes.items():
                    content = np.zeros(len(centres))
                    # coverage: fraction of the flux above threshold where sigma is known
                    if len(flux) == 2:  # lines
                        known, above = 0.0, 0.0
                        for energy, branching in flux[1]:
                            value, missing = folded(component, np.array([energy]))
                            rate = n_targets * flux[0] * branching * value[0] * seconds
                            content[min(np.searchsorted(edges, energy) - 1, len(centres) - 1)] += rate
                            if energy >= threshold:
                                above += branching
                                known += 0.0 if missing[0] else branching
                    else:
                        _, energy, shape = flux
                        value, missing = folded(component, energy)
                        density = n_targets * flux[0] * shape * value * seconds  # per MeV
                        cumulative = np.concatenate([[0.0], np.cumsum(0.5 * (density[1:] + density[:-1]) * np.diff(energy))])
                        content = np.diff(np.interp(edges, energy, cumulative))
                        weight = shape * (energy >= threshold)
                        above = np.trapezoid(weight, energy)
                        known = np.trapezoid(weight * ~missing, energy)
                    coverage = known / above if above > 0 else 1.0
                    total_spectrum += content
                    base = dict(Tool=tool, Version=version, Label=label, Variant=variant,
                                Model=f"{tool}: {variant}", Detector=detector, Channel=channel, Component=component)
                    spectra.append(dict(base, Energy=centres, Rate=content / 0.1))
                    totals.append(dict(base, Total=content.sum(), Above5=content[centres > 5].sum(), Coverage=coverage))
                base = dict(Tool=tool, Version=version, Label=label, Variant=variant, Model=f"{tool}: {variant}",
                            Detector=detector, Channel=channel, Component="all")
                spectra.append(dict(base, Energy=centres, Rate=total_spectrum / 0.1))
                parts = totals[-len(fluxes):]
                rate = sum(t["Total"] for t in parts)
                coverage = min(t["Coverage"] for t in parts if t["Total"] > 1e-3 * rate) if rate > 0 else 1.0
                totals.append(dict(base, Total=total_spectrum.sum(), Above5=total_spectrum[centres > 5].sum(),
                                   Coverage=coverage))
    spectrum_frame, total_frame = pd.DataFrame(spectra), pd.DataFrame(totals)
    _write_frame(spectrum_frame, out_dir / "B5_Spectrum.parquet")
    _write_frame(total_frame, out_dir / "B5_Totals.parquet")
    echo(f"wrote   {out_dir / 'B5_Spectrum'}.parquet ({len(spectrum_frame)} rows), B5_Totals ({len(total_frame)} rows)")
    return total_frame


# Flux components combined with B3 (spectra reaching the B3 energy range).
DAY_NIGHT_COMPONENTS = ("B8", "hep")


def combine_day_night(out_dir=None, echo=print):
    """B2 x B3: day and night P_ee and the day-night asymmetry
    A_DN = 2 (N - D) / (N + D) per tool, solar model, Earth model, site and
    component, on the B3 exposure energies. Tools are paired with themselves."""
    out_dir = Path(out_dir) if out_dir else build_dir()
    sun_path, earth_path = out_dir / "B2_Average.parquet", out_dir / "B3_Night.parquet"
    if not (sun_path.exists() and earth_path.exists()):
        return None
    sun, earth = pd.read_parquet(sun_path), pd.read_parquet(earth_path)
    rows = []
    for _, s in sun[sun.Component.isin(DAY_NIGHT_COMPONENTS)].iterrows():
        nights = earth[earth.Tool == s.Tool]
        for (earth_variant, site), group in nights.groupby(["Variant", "Site"]):
            night = {q: group[group.Quantity == q].iloc[0] for q in ("P1e", "P2e", "P3e")}
            energy = np.asarray(night["P1e"].Energy)
            index = np.searchsorted(s.Energy, energy)
            assert np.allclose(np.asarray(s.Energy)[index], energy)
            F = [np.asarray(s[f"F{i}"])[index] for i in (1, 2, 3)]
            day = np.asarray(s.PeeDay)[index]
            pee_night = sum(F[i] * np.asarray(night[f"P{i + 1}e"].Night) for i in range(3))
            rows.append(dict(Tool=s.Tool, Version=s.Version, Label=s.Label, SunVariant=s.Variant,
                             EarthVariant=earth_variant, Site=site, Component=s.Component, Energy=energy,
                             PeeDay=day, PeeNight=pee_night, ADN=2 * (pee_night - day) / (pee_night + day)))
    frame = pd.DataFrame(rows)
    _write_frame(frame, out_dir / "B23_DayNight.parquet")
    echo(f"wrote   {out_dir / 'B23_DayNight'}.parquet ({len(frame)} rows)")
    return frame


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
