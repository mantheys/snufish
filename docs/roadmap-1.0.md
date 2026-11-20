# Roadmap to 1.0.0

In SNUfish, **1.0.0** means that the benchmark specs, the contribution
format, the command line and the public Python API are frozen: from then on
they change only under the written compatibility rule of item 1b. This page
is the plan to get there from v0.4.0. Each item has a decision (**1.0**:
implemented before the release; **out**: declared out of scope for 1.0,
with the reason and what would bring it back), an effort and what it
changes in rates and plots.

Effort: **S** up to half a day, **M** one to two days, **L** three days or
more, or CPU-hours of reruns.

## How the decisions were made

Once the compatibility rule holds, anything *additive* (a new optional
variant, quantity, grid, detector, response or site) is a minor change and
can come in 1.x without breaking a contribution. What has to be settled
before 1.0 is therefore what would be a *major* change later:

- a change of a fixed input of an existing variant (a flux shape, a constant,
  a grid point): it changes the value every contribution must give;
- a change of structure (columns, how a response or a period is named,
  what `meta.yaml` says): it changes what every contribution must contain;
- an interface that is public by accident and that users would rely on.

The open questions of [status.md](status.md#open-questions-before-freezing-the-specs)
fall on either side of that line. Items that are additive and have no tool to
contribute them are declared out of scope for 1.0, with the way back noted.

## Summary

| # | Item | Decision | Effort | Rates that change |
|---|---|---|---|---|
| 1a | B5: ⁸B tail above 15.2 MeV | 1.0 (done: B5 0.5.0) | M | ⁸B above 5 MeV: CC +8 × 10⁻⁵, ES +1 × 10⁻⁵, NC on ⁴⁰Ar +4 × 10⁻⁴; the DUNE Phase I numbers do not move at the paper's precision; above 15 MeV +5–7 % |
| 1a | B5: JUNO's response; second responses per detector | 1.0: JUNO as detector `scintillator_lab` (done: B5 0.6.0); named second responses deferred (none published: SNO+ and Hyper-K give no resolution), additive when one is | M | none (new JUNO rows only) |
| 1a | B5: night and annual quantities in contributions | out | — | — |
| 1a | B3: `prem_crust1` per site as variants | 1.0 | L (CPU) | B5 night gains `prem_crust1` rows; existing rows unchanged |
| 1a | B3: `prem_crust1_3d` (trajectory grids) | out | — | — |
| 1a | B3: energy grid down to 0.1 MeV | out (bounded and documented) | S | — |
| 1a | B4: σ(E; T > T<sub>min</sub>) at the detectors' ES thresholds | 1.0 | S | none (new quantities) |
| 1a | B2: spectral-shape variants (Ortiz ⁸B, ⁷Be line widths) | out | — | — |
| 1a | B2 × B5: B23 flux correlations in B5 uncertainties | 1.0 (product only) | S | none; error of `all` rows in `B5_Totals` |
| 1a | B2: non-adiabatic solver | out (definition frozen, bound stated) | — | — |
| 1a | B2: line of sight for off-centre production | out (definition frozen) | — | — |
| 1b | Specs to 1.0.0, compatibility policy, validator rule | 1.0 | M | none |
| 2 | B5 part 2: SNOwGLoBES's smeared output | 1.0 | M | none (new contribution) |
| 3 | Public interface: CLI, engine, presets, calculator inputs; tests | 1.0 | M | none |
| 4 | PyPI package | out | — | — |
| 4 | A third-party contribution: sntools (water) | 1.0 if ready, not blocking; SNuDD out | M | none (new contribution) |
| 4 | Citable write-up: JOSS paper | draft in 1.0, submitted after the tag | M | — |

Only item 1a's ⁸B tail changes a SNUfish rate, and by less than any quoted
digit except above 15 MeV. Everything else adds rows, quantities or
contributions next to unchanged ones.

---

## 1. Spec freeze

### 1a. The open questions

#### B5: the ⁸B tail (1.0, M; done in B5 0.5.0)

`reference/ssm/shapes/8B_shape_Winter_et_al.csv` ends at 15.2 MeV. The
truncation is a fixed input of every B5 variant, so correcting it after 1.0
would be a major change: it went in first.

- What was found: Winter et al.'s published table IV itself ends at 15.2 MeV
  (no fuller table exists): their β strength function (table II) starts at
  E<sub>x</sub>(⁸Be) = 1.55 MeV, which caps E<sub>ν</sub> near 15.4 MeV. Bahcall et al.
  1996 (PRC 54, 411, table I) tabulates the spectrum to 16.0 MeV and gives
  the same value at 15.2 MeV (0.047 per 1000 per MeV). B5 0.5.0 takes Winter
  to 15.2 MeV and Bahcall above
  (`reference/ssm/shapes/8B_shape_Winter2006_tail_Bahcall1996.csv`).
- The tail holds 1.1 × 10⁻⁵ of the ⁸B flux, not the 10⁻⁴ `status.md` stated
  nor the 3–6 × 10⁻⁴ this plan first estimated from a single allowed β shape
  (which ignored that the strength falls at low E<sub>x</sub>).
- Effect, `scripts/dune_phase1_rates.py` (annual, per kt·yr, E<sub>ν</sub> > 5 MeV): CC
  2415.9 → 2416.1, ES 1081.30 → 1081.31, NC 105.70 → 105.74. The paper's
  numbers (CC 2416, ES 1081, NC 105.7) and its LaTeX macros are unchanged;
  CC above T<sub>e</sub> = 5 MeV is 1210.3 → 1210.5 (1211 in the four-digit table of
  `dune-solar-tables.md`, 1.21 × 10³ in the paper's). Above 15 MeV, where
  the tail is the ⁸B spectrum, rates rise by 5–7 %.
- Reruns: the SNOwGLoBES and MARLEY B5 contributions; only ⁸B and `all`
  rows moved (3–8 × 10⁻⁵), every other row is bit-identical.

#### B5: JUNO's response and second responses per detector (1.0, M; done in B5 0.6.0)

Part 2 has one response per detector (`response.detectors.<detector>`), and
a contribution says `settings.response: spec` or `own`.

- JUNO (arXiv:2006.11760) is a detector of its own: its liquid scintillator
  is LAB, not Borexino's pseudocumene, so it is not a second response of
  `scintillator_pc`. B5 0.6.0 adds the detector `scintillator_lab`
  (3.38 × 10³² e⁻ per kt, until then on the page only) and its response:
  3 %/√T on the recoil kinetic energy, a 2 MeV threshold, efficiency 1, energy
  scale ±0.3 % and rate ±1 % (table 5). JUNO's light-output nonlinearity is
  not modelled (under 1 % above 2 MeV); `status.md` lists it.
- SNO+: **out**. Its water-phase ⁸B paper (arXiv:1812.03355, PRD 99,
  012012) gives the uncertainty of its resolution (0.018√T) and of its
  energy scale (2 %), but not the resolution itself.
- Hyper-K: **out**. It publishes no solar response; the calculator's
  Hyper-K preset uses Super-K IV's resolution as a stand-in, and a copy of
  Super-K IV is not a second response.
- Named responses: **deferred**. With no second published response, the
  renamed structure planned here (`response.responses.<name>`,
  `response.default`) would be machinery without data, and a major change.
  The additive form costs as little later: `response.alternatives.<name>`
  (with `detector`), `settings.response: {<detector>: <name>}` and a
  `Response` column in `B5_Observed`, all minor changes
  ([compatibility.md](compatibility.md)).
- The format points of item 2 that belong to the response were settled
  here too: `response.parquet` takes an optional `flavour` column, and an ES
  matrix in neutrino energy, per flavour (`nue`, `numu`; `nutau` equal to
  `numu`). The engine folds it per flavour (σ<sub>α</sub>(E<sub>ν</sub>) times the row of
  the true bin holding E<sub>ν</sub>).
- Rates: none change; `B5_Observed`, `B5_Totals` and the B5 tab gain JUNO
  rows (by day, B16-GS98: 1086 per kt·yr above T = 2 MeV).

#### B5: night and annual quantities in contributions (out)

No full-chain tool propagates through the Earth: SNOwGLoBES and MARLEY take
SNUfish's P<sub>eα</sub>. A night grid would test only that the wrappers multiply the
B3 reference night correctly. `B5_DayNight` stays SNUfish's folding. Way
back: optional grids `night` and `annual` at each detector's home site, a
minor change, when a full-chain tool with its own Earth model contributes.
The same holds for night and A<sub>DN</sub> in part 2.

#### B3: `prem_crust1` per site (1.0, L in CPU)

`prem_crust1` is the default Earth model of the engine and the calculator,
and B3 does not benchmark it. It is radial per site (the CRUST1.0 column
above PREM's Moho), so every radial solver can run it.

- Variants `prem_crust1_<site>` for the five sites, each written out in the
  spec (`regions`: the CRUST1.0 layers from `reference/earth/crust1_sites.yaml`
  above PREM), optional (not required). Additive: existing contributions
  stay valid.
- Contributions: the reference (Magnus), NuFast-Earth (through
  `crust.write_regions`), nuSQuIDS (hours of GSL; it integrates the
  polynomials). PEANUTS cannot take PREM's odd powers.
- Same rerun: the reference's finer Magnus step (1.5625 km, ~4× the time;
  [status.md](status.md#follow-ups-of-the-tool-comparison)), which moves no
  product by more than 10⁻⁴ of the regeneration.
- B5: `night.earth_models` gains `prem_crust1` (per site, from the reference),
  so `B5_DayNight` has the engine's default Earth model.
- Rates: new `prem_crust1` rows; the other B5 night rows move by ≤ 10⁻⁴ of
  the regeneration (finer step). The DUNE numbers do not move (they use the
  engine's NuFast-Earth night on `prem_full`). Plots: the `b3` list gains
  the variants; the B3 tab shows them.

#### B3: `prem_crust1_3d` (out)

It needs per-site trajectory grids (≈ 130 chords in each of 1001 nadir
cells) and a tool that solves single trajectories; only NuFast-Earth's
single-trajectory mode does, and it is what the engine uses, so a benchmark
would compare it with itself. It differs from `prem_crust1` by ≤ 0.17 % of
A<sub>DN</sub>, the Earth range already stated. It stays in the engine with its
cross-check in [crosschecks.md](crosschecks.md#crust-along-each-chord-3d).
Way back: a `trajectories` grid as a minor change, once a second
single-trajectory solver exists (the reference's Magnus could be one).

#### B3: energy grid down to 0.1 MeV (out; S to bound it)

Extending the existing grids would invalidate every B3 contribution; an
extra optional grid would be additive and can come in 1.x. The Earth effect
there is small: the PR computes the reference's night excess of pp and ⁷Be
(0.1 to 1 MeV) at the five sites and states the bound in `benchmarks.md`
and `status.md` (B5 sets the night excess to zero below 1 MeV).

#### B4: ES above the detectors' recoil thresholds (1.0, S)

The engine already integrates dσ/dT above T<sub>min</sub>; B4 should carry the number.
New quantities `es_<flavour>_T<threshold>` (σ(E; T > T<sub>min</sub>), cm² per
electron) at the thresholds of the B5 responses: 0.05 (Borexino), 2.0
(JUNO), 3.49 (Super-K IV), 5.0 (DUNE), 5.5 MeV (SNO salt). Optional
(B4 does not require every quantity). One validator change keeps existing
contributions valid: a variant's `quantities` list (`es_bks` names its
three channels) must become the set a contribution may give, not the set it
must give exactly, which is itself a relaxed check (minor).
Contributed by the reference (tree level and `es_bks`); MARLEY can add them
later. The B4 ordering check (σ(νₑe) > σ(ν<sub>μ</sub>e)) extends to each
threshold. Rates: none. Plots: a thresholded-ES panel in `b45`.

#### B2: spectral-shape variants (out)

The Ortiz et al. ⁸B shape and the ⁷Be line widths would be B5 flux-shape
variants, additive later. Winter et al.'s table already carries its own
shape uncertainty. The ⁷Be thermal widths (~1–2 keV) are below every
detector's resolution (Borexino: 50 keV at 1 MeV) and are declared not
modelled.

#### B2 × B5: B23 correlations in B5 uncertainties (1.0, S)

A build product, not a spec change: `B5_Totals` gives each component's
flux error, uncorrelated; for `all` rows it should use the B23 correlation
matrices (the engine and `snufish budget` do). Models without correlations
(B16, BS05) keep uncorrelated errors, stated in a column. Rates: none; the
errors of `all` rows change, and the `b45` error bars with them.

#### B2: non-adiabatic solver and line of sight (out)

The spec defines F<sub>i</sub> as the exact phase-averaged fraction along a radial
path; that definition is frozen. The adiabatic reference approximates it to
O(10⁻⁶) (stated in "Known approximations"), and the path does not enter
while propagation is adiabatic. A validated non-adiabatic solver would be a
new tool contributing to the same spec, so it needs no spec change and can
come at any time.

### 1b. Specs to 1.0.0 and the compatibility policy (1.0, M)

A new page, `docs/compatibility.md`, and the validator changes it needs.

**What a change to a spec is**:

| Change | Kind | Old contributions |
|---|---|---|
| Wording, comments, sources, descriptions; a correction that moves no value | patch (1.0.x) | valid |
| New optional variant, quantity, grid, detector, response, site; a relaxed check | minor (1.x.0) | valid |
| Any change of a value an existing variant fixes (constant, grid point, matter model, solar model, flux shape, target count, oscillation parameter); a renamed or removed key; a new required variant or quantity; a tightened check; a change of columns or `meta.yaml` keys | major (2.0.0) | invalid under the new major; listed in its changelog |

**Registries** (B1 parameter sets, B2 solar models): an entry is never
edited once released. A correction is a new id, and the old one is marked
legacy in `reference/status.yaml`. Adding an entry is minor.

**How old contributions stay valid**: `benchmark_version` keeps the version
a contribution was computed with. The validator accepts any version with the
current major and a minor at most the current one (today it requires
equality). For the move to 1.0.0, each spec lists the 0.x versions whose
contributions are still exact under 1.0.0 (`compatible: [0.3.0]` for B3,
for instance), so the contributions that need no rerun keep their
provenance instead of being restamped. B5 contributions are rerun anyway
(the ⁸B tail).

**Spec changelog**: each spec gets a `changelog` block (version, date, what
changed, kind), and `status: frozen` replaces `status: draft`. The "Open
questions" comments move to the changelog or to this page.

**Code**, in the same page: the package follows semantic versioning on the
public interface of item 3. Deprecations live for at least one minor
release with a warning before removal in a major. A change of a default
physics input (for example a new state-of-the-art cross section as the
engine default) is a minor release whose notes list every quoted number that
moves; the version DOIs keep old numbers reproducible.

Then every spec goes to 1.0.0 (B1 has no contributions; B2, B3, B4 and B5
with the items above), `benchmarks.md` and the page show `frozen`, and
`status.md` loses "Open questions before freezing the specs".

---

## 2. B5 part 2: SNOwGLoBES's smeared output (1.0, M)

The `response.parquet` path has never seen real data. SNOwGLoBES (checkout
at the pinned `6fa928e`) has smearing matrices and efficiencies for both
configurations it already runs (`ar40kt`, `wc100kt30prct`).

- `run_b5.py --part2`: the same flux files, the smeared, efficiency-weighted
  output per channel; `response.parquet` from `smear/<config>/smear_*.dat`
  and `effic/<config>/effic_*.dat`; `settings.response: own`.
- Two format points to settle while the format is still open (both in 1b):
  - SNOwGLoBES's ES matrices map neutrino energy to detected energy, and
    differ per flavour (`nue_e`, `numu_e`, `nutau_e`; the last two are
    identical in both configurations). `response.parquet`
    gains an optional `flavour` column, and `true_axis: neutrino` is allowed
    for ES. SNUfish's folding of an own response (build `B5_ObservedChain`,
    engine `_imported_matrix`) takes both. (Done in B5 0.6.0, item 4.)
  - SNOwGLoBES's detected energy comes in ~0.5 MeV bins, while the `observed`
    grid has 0.01 MeV steps. The wrapper interpolates the cumulative rate
    linearly within a bin (stated in `settings`), and `B5_ObservedChain`
    compares at the tool's bin edges only (`observed_low` of the response).
- Expected result: agreement with SNUfish's folding through the same matrices
  to the 10⁻⁵ of part 1 above 2 MeV, with the known sampling bias below. The
  comparison with the spec's responses (DUNE 20 %, Super-K IV) shows how far
  SNOwGLoBES's generic configurations are from the published ones.
- Rates: none. Plots: a part-2 tool in the `b45` observed panels and in the
  B5 tab's observed spectra; `benchmarks.md` and `status.md` lose "no part-2
  contribution".

---

## 3. Public interface (1.0, M)

A new page, `docs/api.md`, lists what is public and stable; everything else
is internal and may change in any release.

| Surface | Public | Internal |
|---|---|---|
| Command line | the subcommands `validate`, `build`, `reference`, `scan`, `budget`, `status`, `export-app`, `export-sections`, `export-pkl`, `export-xsec`, their options and defaults, exit codes | the layout of `build/app` (the tables `export-app` writes for the page: versioned with the page, not frozen) |
| Contribution format | `data.parquet` columns, `meta.yaml` keys, `response.parquet` | — |
| Build products | the frames in `build/data` and their columns (plotipus lists and outside scripts read them; a new column is minor, a renamed or removed one major) | the `earth3d` cache |
| Python | `snufish.engine`: `Inputs`, `Setup` and its fields, `check`, `parameters`, `oscillation`, `component_totals`, `component_spectra`, `combine`, `totals`, `flux_summary`, `quantity_value`, `statistical_sigma`, `budget`, `spectra`, `Table`, `TableProbabilities`, the constants `PARAMETERS`, `PERIODS`, `QUANTITY_NAMES`, `ES_MODELS`, `STATUSES`; `snufish.export`: `collect_inputs`, `ExactProbabilities`; `snufish.spec`: `load_spec`, `Spec`, `pmns`, `available_benchmarks`; `snufish.contribution`: `load_contribution`, `find_contributions`, `validate`, `write_contribution`, `load_response`; the reference entry points listed in `usage.md` | every name starting with `_`; `build`, `sections`, `pkl`, `scan` and `uncertainty` internals (their interface is the CLI); `crust`, `earth3d`, `plotipus_plugin`, `paths` |
| Calculator | the share-link keys of the page (`set`, `solar`, `site`, `earth`, `target`, `channel`, `xsec`, `preset`, `threshold`, … as in `web/app.js` `KEYS` and `RADIOS`), the preset names (`thumb`, `borexino`, `juno`, `sno`, `sno_salt`, `dune`, `hyperk`, `sk4`) and the result-template ids, so links people have shared keep working | the page's code and layout, `inputs.json` |

Preset *values* follow the physics rule of 1b: correcting a preset to a
newer published response is a minor change with release notes; renaming or
removing a preset is major.

Work:

- `__all__` in `engine`, `export`, `spec`, `contribution`, matching the table.
- `tests/test_public_api.py`: the subcommands and every option with its
  default (from the argparse parser, against a committed snapshot), the
  public names and their signatures (`inspect.signature`), the `Setup`
  fields and defaults, the frame columns of `build/data` against
  `usage.md`'s table.
- `web/test/engine.test.mjs`: the share-link keys, preset names and
  template ids against a snapshot (the constants move from `app.js` to a
  small exported module so the test can import them).
- Fix what the review turns up. Already found: `usage.md` lists
  `B1_Profiles` and `B1_Production` (the build writes `B2_Profiles`,
  `B2_Production`) and omits `B5_Observed` and `B5_ObservedChain`.

Rates and plots: none.

---

## 4. Optional items

### PyPI package (out)

SNUfish reads its inputs from the repository (`paths.repo_root`: specs,
reference data, contributions), the night needs the compiled NuFast-Earth
driver, and PyPI refuses packages whose metadata has a direct git
dependency (the `plots` extra pins plotipus by URL). A wheel would install
the code without the data it needs. The citable product of 1.0 is the
repository and its Zenodo archive. Way back, after 1.0: plotipus on PyPI, the
data as package data or a `snufish fetch` command, and the driver as an
optional extension.

### A third-party contribution (sntools in 1.0 if ready, not blocking; SNuDD out)

- **sntools** (water: ES and CC on ¹⁶O): a second full-chain tool in water
  (B5 part 1) and, if its ¹⁶O cross section is its own, the first
  alternative ¹⁶O model in B4. It is supernova-oriented and needs the solar
  flux given as a constant-in-time input. Being additive, it can also land in
  1.x; it does not hold the release.
- **SNuDD** (ES with atomic effects): out. Its corrections matter at recoils
  below ~10 keV, under every B5 threshold, and it targets xenon, which no
  B5 detector has.

### Citable write-up (JOSS: draft in 1.0, submitted after the tag)

A JOSS paper (`paper/paper.md`, `paper/paper.bib`, ~1000 words: the
problem, the benchmarks, what the tool comparison found, the calculator)
fits the project: open, documented, tested, with a version DOI. JOSS
reviews a tagged release, and review changes would come as 1.0.x. A
technote would add little beyond `docs/`. The draft goes in a PR before the
tag; submitting it is your call.

---

## Order of work

One PR each, in this order; the release PR only after all others are merged
and you say so.

1. This roadmap.
2. Compatibility: `docs/compatibility.md`, the validator's version rule,
   spec changelogs (versions not bumped yet).
3. B5 ⁸B tail, with the reruns and the new DUNE numbers (done: no quoted rate moves).
4. B5 named responses, the `flavour` column and ES in neutrino energy, JUNO
   (and SNO+ if sourced) (done: JUNO, `flavour`, ES in neutrino energy;
   SNO+ out, named responses deferred).
5. SNOwGLoBES part 2.
6. B4 thresholded ES.
7. B3 `prem_crust1` variants and the finer reference step; B5 night on
   `prem_crust1`. (Reruns: hours, nuSQuIDS the longest.)
8. B5 flux errors with the B23 correlations; the B3 low-energy bound.
9. Public interface: `docs/api.md`, `__all__`, the pinning tests.
10. sntools (optional; may slip to 1.x).
11. JOSS draft (optional).
12. Release 1.0.0: every spec to 1.0.0 and `frozen`, `status.md`,
    `benchmarks.md`, the page, release notes with every number that moved;
    by the steps of [release.md](release.md). Tagging mints a permanent DOI:
    I ask before tagging.

v0.4.0 (PR #35) is to be tagged first, so that 0.4.0 keeps a DOI with the
current rates before item 3 changes them.

Each PR keeps `status.md` and the page consistent with the data, and passes
CI (ruff, tests on Python 3.10 and 3.12, the tables job, validate-and-plot).
