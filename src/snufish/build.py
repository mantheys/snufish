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
    weights = {variant: production_weights(info["solar_model"], radii, spec) for variant, info in spec.variants.items()}
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
            for component, w in weights[variant].items():  # the variant's own production profiles
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


def _build_b5(contributions, spec):
    """Full-chain tool totals next to SNUfish's folding of the same inputs
    with that tool's B4 cross sections (same solar model)."""
    totals_path = build_dir() / "B5_Totals.parquet"
    folded = pd.read_parquet(totals_path) if totals_path.exists() else None
    rows = []
    for contribution in contributions:
        meta = contribution.meta
        for _, r in contribution.data.iterrows():
            detector, channel, component = r.quantity.split("/")
            variant = spec.variants[r.variant]
            model = variant["solar_model"] or spec.data.get("native_solar_model", {}).get(meta["tool"])
            row = dict(Tool=meta["tool"], Version=str(meta["tool_version"]), Variant=r.variant, SolarModel=model,
                       Detector=detector, Channel=channel, Component=component, Threshold=r.threshold,
                       Case=f"{detector} {channel}", Rate=r.value, Folded=np.nan, Coverage=np.nan)
            if folded is not None and model is not None:
                match = folded[(folded.Model == f"{meta['tool']}: default") & (folded.SolarModel == model)
                               & (folded.Detector == detector) & (folded.Channel == channel)
                               & (folded.Component == component)]
                if len(match):
                    m = match.iloc[0]
                    row.update(Folded=m.Total if r.threshold == 0 else m.Above5, Coverage=m.Coverage)
            row["Ratio"] = row["Rate"] / row["Folded"] if row["Folded"] else np.nan
            rows.append(row)
    return {"B5_Chain": pd.DataFrame(rows)}


BUILDERS = {"B2_sun": _build_b2, "B3_earth": _build_b3, "B4_xsec": _build_b4, "B5_rates": _build_b5}

def _bins(kind, start, stop, step=None, per_decade=None):
    if kind == "linear":
        return np.round(np.arange(start, stop + step / 2, step), 6)
    n = int(round(np.log10(stop / start) * per_decade))
    return np.geomspace(start, stop, n + 1)


def _bin_lines(lines, edges):
    content = np.zeros(len(edges) - 1)
    for energy, rate in lines:
        k = np.searchsorted(edges, energy, side="right") - 1
        if 0 <= k < len(content):
            content[k] += rate
    return content


def _spectrum_row(base, binning, edges, content):
    """Rate density (per MeV) at the bin centres (geometric for log bins)."""
    centres = np.sqrt(edges[1:] * edges[:-1]) if binning == "log" else 0.5 * (edges[1:] + edges[:-1])
    return dict(base, Binning=binning, Energy=centres, Rate=content / np.diff(edges), EnergyLow=edges[:-1],
                EnergyHigh=edges[1:])


def _night_regeneration(out_dir, spec):
    """{(EarthModel, EarthTool, Site): (energy, R[i, energy])}: the night excess
    R_i = <P_ie>_night - |U_ei|^2 of B3, per Earth model from the tool the B5
    spec names for it."""
    path = out_dir / "B3_Night.parquet"
    if not path.exists():
        return {}
    nights = pd.read_parquet(path)
    out = {}
    for earth_model, tool in spec["night"]["earth_models"].items():
        sub = nights[(nights.Tool == tool) & (nights.Variant == earth_model)]
        for site, group in sub.groupby("Site"):
            rows = {q: group[group.Quantity == q].iloc[0] for q in ("P1e", "P2e", "P3e")}
            energy = np.asarray(rows["P1e"].Energy)
            out[(earth_model, tool, site)] = (energy, np.stack([np.asarray(rows[q].Regeneration) for q in rows]))
    return out


def combine_rates(out_dir=None, echo=print):
    """B5: interaction rates per B1 solar model, B4 model, detector, channel
    and flux component (daytime oscillations from the B2 reference of the
    same solar model), in events per kton-year: spectra in 0.1 MeV bins of
    neutrino energy and totals. With B3: day, night and annual totals per
    site and Earth model (B5_DayNight)."""
    from .fluxes import components
    from .solar import models as solar_models

    out_dir = Path(out_dir) if out_dir else build_dir()
    sun_path, xs_path = out_dir / "B2_Average.parquet", out_dir / "B4_Sigma.parquet"
    if not (sun_path.exists() and xs_path.exists()):
        return None
    spec, sun_spec = load_spec("B5_rates"), load_spec("B2_sun")
    U2 = np.abs(pmns(sun_spec["oscillation"])) ** 2  # [alpha, i]
    sun_all = pd.read_parquet(sun_path)
    sun_all = sun_all[sun_all.Tool == "snufish-reference"]
    xs = pd.read_parquet(xs_path)
    seconds = spec["exposure"]["seconds_per_year"] * spec["exposure"]["kton_year"]
    # Spectra in two binnings of neutrino energy: linear (totals and the 8B
    # range) and logarithmic (pp to hep on a log axis). Rates are integrated on
    # each component's own fine grid, so any binning is exact up to its edges.
    binnings = {name: _bins(**info) for name, info in spec["spectrum_bins"].items()}
    edges = binnings["linear"]
    centres = 0.5 * (edges[1:] + edges[:-1])
    nights = _night_regeneration(out_dir, spec)

    spectra, totals, day_night = [], [], []
    for solar_model in solar_models():
        sun = sun_all[sun_all.Variant == solar_model].set_index("Component")
        if sun.empty:
            continue
        fluxes = components(spec, solar_model)

        def oscillation(component, energy, night=None):
            """P_{e alpha}(E), alpha = e, mu, tau; at night P_ee gains sum_i F_i R_i (zero below the B3
            grid), and the rest is split between mu and tau as by day (sigma_mu = sigma_tau in ES)."""
            row = sun.loc[component]
            F = np.stack([np.interp(energy, row.Energy, row[f"F{i}"]) for i in (1, 2, 3)], axis=-1)
            P = F @ U2.T
            if night is None:
                return P
            grid, R = night
            excess = sum(F[..., i] * np.interp(energy, grid, R[i], left=0.0, right=R[i][-1]) for i in range(3))
            pee = P[..., 0] + excess
            rest = P[..., 1] + P[..., 2]
            share = np.divide(P[..., 1], rest, out=np.full_like(rest, 0.5), where=rest > 0)
            return np.stack([pee, (1 - pee) * share, (1 - pee) * (1 - share)], axis=-1)

        for (tool, version, label, variant), models in xs.groupby(["Tool", "Version", "Label", "Variant"]):
            sigma = {row.Channel: row for row in models.itertuples()}
            for detector, info in spec["detectors"].items():
                for channel, target in info["channels"].items():
                    flavours = spec["channels"][channel]["flavours"]
                    threshold = spec["channels"][channel]["threshold_MeV"]
                    if not all(name in sigma for name in flavours.values()):
                        continue
                    n_targets = info["targets"][target]

                    def folded(component, energy, night):
                        P = oscillation(component, energy, night)
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

                    def rates(night):
                        """{component: (contents per binning, coverage)} for the day (night None) or a night."""
                        out = {}
                        for component, flux in fluxes.items():
                            # coverage: fraction of the flux above threshold where sigma is known
                            if len(flux) == 2:  # lines
                                known, above, lines = 0.0, 0.0, []
                                for energy, branching in flux[1]:
                                    value, missing = folded(component, np.array([energy]), night)
                                    lines.append((energy, n_targets * flux[0] * branching * value[0] * seconds))
                                    if energy >= threshold:
                                        above += branching
                                        known += 0.0 if missing[0] else branching
                                contents = {name: _bin_lines(lines, e) for name, e in binnings.items()}
                            else:
                                _, energy, shape = flux
                                # The density is linear between the shape's table points; bin edges
                                # inside the table become nodes too, so bins narrower than the table
                                # spacing are not flat steps.
                                inner = [e[(e > energy[0]) & (e < energy[-1])] for e in binnings.values()]
                                fine = np.unique(np.concatenate([energy, *inner]))
                                value, _ = folded(component, fine, night)
                                density = n_targets * flux[0] * np.interp(fine, energy, shape) * value * seconds  # per MeV
                                cumulative = np.concatenate([[0.0], np.cumsum(0.5 * (density[1:] + density[:-1]) * np.diff(fine))])
                                contents = {name: np.diff(np.interp(e, fine, cumulative)) for name, e in binnings.items()}
                                _, missing = folded(component, energy, night)
                                weight = shape * (energy >= threshold)
                                above = np.trapezoid(weight, energy)
                                known = np.trapezoid(weight * ~missing, energy)
                            out[component] = contents, (known / above if above > 0 else 1.0)
                        return out

                    def total_coverage(parts):
                        rate = sum(t["Total"] for t in parts)
                        return min(t["Coverage"] for t in parts if t["Total"] > 1e-3 * rate) if rate > 0 else 1.0

                    base = dict(SolarModel=solar_model, Tool=tool, Version=version, Label=label, Variant=variant,
                                Model=f"{tool}: {variant}", Detector=detector, Channel=channel)
                    day = rates(None)
                    sums = {name: np.zeros(len(e) - 1) for name, e in binnings.items()}
                    parts = []
                    for component, (contents, coverage) in day.items():
                        for name, e in binnings.items():
                            sums[name] += contents[name]
                            spectra.append(_spectrum_row(dict(base, Component=component), name, e, contents[name]))
                        content = contents["linear"]
                        parts.append(dict(base, Component=component, Total=content.sum(),
                                          Above5=content[centres > 5].sum(), Coverage=coverage))
                    for name, e in binnings.items():
                        spectra.append(_spectrum_row(dict(base, Component="all"), name, e, sums[name]))
                    total_spectrum = sums["linear"]
                    totals += parts + [dict(base, Component="all", Total=total_spectrum.sum(),
                                            Above5=total_spectrum[centres > 5].sum(), Coverage=total_coverage(parts))]

                    day_totals = {c: contents["linear"] for c, (contents, _) in day.items()}
                    day_totals["all"] = total_spectrum
                    for (earth_model, earth_tool, site), night in nights.items():
                        night_totals = {c: contents["linear"] for c, (contents, _) in rates(night).items()}
                        night_totals["all"] = sum(night_totals.values())
                        for component, n in night_totals.items():
                            d = day_totals[component]
                            row = dict(base, Component=component, EarthModel=earth_model, EarthTool=earth_tool, Site=site)
                            for suffix, keep in (("", slice(None)), ("Above5", centres > 5)):
                                D, N = d[keep].sum(), n[keep].sum()
                                row.update({f"Day{suffix}": D, f"Night{suffix}": N, f"Annual{suffix}": 0.5 * (D + N),
                                            f"ADN{suffix}": 2 * (N - D) / (N + D) if N + D > 0 else np.nan})
                            day_night.append(row)
    spectrum_frame, total_frame, day_night_frame = pd.DataFrame(spectra), pd.DataFrame(totals), pd.DataFrame(day_night)
    _write_frame(spectrum_frame, out_dir / "B5_Spectrum.parquet")
    _write_frame(total_frame, out_dir / "B5_Totals.parquet")
    _write_frame(day_night_frame, out_dir / "B5_DayNight.parquet")
    echo(f"wrote   {out_dir / 'B5_Spectrum'}.parquet ({len(spectrum_frame)} rows), B5_Totals ({len(total_frame)} rows), "
         f"B5_DayNight ({len(day_night_frame)} rows)")
    return total_frame


def combine_ssm(out_dir=None, echo=print):
    """B1: flux ratios to the reference model, electron density and production
    profiles of every solar model in the registry."""
    from .solar import COMPONENTS, electron_density, models, table

    out_dir = Path(out_dir) if out_dir else build_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = load_spec("B1_ssm")
    registry = models()
    reference = registry[spec["reference_model"]]["fluxes"]
    radius = np.round(np.arange(0.0, 0.9001, 0.0025), 6)
    fluxes, profiles, production = [], [], []
    for name, model in registry.items():
        base = dict(Model=name, Family=model["family"], Composition=model["composition"])
        errors = model.get("flux_uncertainty") or {}
        for component in COMPONENTS:
            flux = model["fluxes"][component]
            fluxes.append(dict(base, Component=component, Flux=flux, RelativeFlux=flux / reference[component],
                               RelativeFluxError=errors.get(component, np.nan) * flux / reference[component]))
        data = table(name)
        # density on one radius grid for every model (tables differ in sampling; tails included)
        profiles.append(dict(base, Radius=radius, LogNe=np.log10(electron_density(name, radius))))
        for k, component in enumerate(COMPONENTS):
            production.append(dict(base, Component=component, Radius=data[:, 0], Density=data[:, 2 + k]))
    frames = {"B1_Fluxes": pd.DataFrame(fluxes), "B1_Profiles": pd.DataFrame(profiles),
              "B1_Production": pd.DataFrame(production)}
    for name, frame in frames.items():
        _write_frame(frame, out_dir / f"{name}.parquet")
    echo(f"wrote   {out_dir / 'B1_Fluxes'}.parquet, B1_Profiles, B1_Production ({len(registry)} models)")
    return frames


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
