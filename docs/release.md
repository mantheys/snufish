# Releasing a citable version

Next: **v0.5.0** (notes below), tagged from `main` with CI green; its version
DOI goes in with step 4.
Released: **v0.4.0** is tagged (2026-11-20) and archived on Zenodo.
**v0.3.0** is tagged (2026-11-20), version DOI
[10.5281/zenodo.24383275](https://doi.org/10.5281/zenodo.24383275).
**v0.2.0** has version DOI
[10.5281/zenodo.24045167](https://doi.org/10.5281/zenodo.24045167). The
concept DOI (resolves to the latest version) is
[10.5281/zenodo.24045166](https://doi.org/10.5281/zenodo.24045166). 0.1.0 is
the untagged development version; 0.2.0 adds the DUNE table options
(`night_fraction`, `nu_threshold`, `nc_ar40`, the SOLAR night). The steps
below are what it took; repeat 2 to 4 for the next one.

## v0.5.0 release notes

SNUfish 0.5.0 adds the inputs of the DUNE solar Phase I paper's day-night
uncertainty and new benchmark parts. No rate changes:
`scripts/dune_phase1_rates.py` (B16-GS98 8B + hep, per kt-yr) gives the same
CC, ES and NC rates as 0.3.0 and 0.4.0.

- DUNE Phase I (#42 and on `main`): `scripts/dune_phase1_daynight.py`, the
  spectrum-weighted CC and ES day-night asymmetries in argon, and
  `scripts/dune_phase1_adn_budget.py`, the theoretical uncertainty of the CC
  asymmetry at SURF (range over the current Earth models, 0.6 %; spread for
  the NuFIT 6.1 uncertainties around the analysis point, 2.3 %).
- B5 0.5.0 to 0.7.0 (#38 to #40): the 8B spectrum above 15.2 MeV from
  Bahcall et al. 1996; JUNO's detector and response, ES matrices in neutrino
  energy per flavour; SNOwGLoBES part 2 through its own response.
- B4 0.2.0 (#41): ES above the detectors' recoil thresholds.
- Compatibility rule (#37): spec changelogs, `Spec.accepts`,
  docs/compatibility.md; roadmap to 1.0.0 (#36).
- CI: test coverage reported to Codecov.

Submodules: NuFast-Earth at `327586d` (v1.2.0-3), PEANUTS at `1783f9f` (v1.7).

Cite the version DOI of 0.5.0 once minted, or the concept DOI
10.5281/zenodo.24045166.

## v0.4.0 release notes

SNUfish 0.4.0 adds a second full-chain rate tool in argon and a consistency
pass of the web page. No rate changes: the engine is that of 0.3.0, and
`scripts/dune_phase1_rates.py` (B16-GS98 8B + hep, per kt-yr above
E_ν = 5 MeV, annual) gives CC 2416, ES 1081 and NC 105.7 as before.

- B5: MARLEY's full chain in argon (#34), `contributions/marley/scripts/run_b5.py`:
  MARLEY 2 integrates its own cross sections (CC: HF-CRPA continuum + the
  Bhattacharya 2009 bound levels; ES: tree level) over the oscillated B2
  spectra of every solar model, for CC and ES at E_ν > 0 and > 5 MeV. It
  agrees with SNUfish's folding of MARLEY's B4 tables to 0.03 %. MARLEY's B4
  contribution now has ES too (CC unchanged). B5 plots and the B5 tab show
  every full-chain tool, a symbol per tool.
- B4 (#32): the 8B + hep NC rate on 40Ar is a reference observable of the
  impact chart, with the figure reading of the continuum (−43 %/+66 %), the
  measured strength (B(M1) ±14 %, ~1 %) and SNOwGLoBES's legacy table (−73 %).
  The Home finding on cross sections shows ES, CC and NC against each
  channel's default.
- Web (#33): the impact charts have one panel per detection channel, each
  with the legend of its own sources; every plot has its full frame at any
  screen scaling; B1 sets have one colour each; B5's observed spectra are
  split into ES and CC plots; numbers in the text checked against the data.

Cite the version DOI of 0.4.0 once minted, or the concept DOI
10.5281/zenodo.24045166.

## v0.3.0 release notes

SNUfish 0.3.0 adds the exports that make the theory inputs of the DUNE
low-energy reconstruction paper and the DUNE solar Phase I paper, and
replaces the SNOwGLoBES cross sections on argon that had no published source
(ν̄e CC and NC). CC and ES rates are those of 0.2.0; the NC rate changes with
the new NC model: `scripts/dune_phase1_rates.py` (B16-GS98 8B + hep) gives CC
2420 and ES 1080 per kt-yr above E_ν = 5 MeV as before, and NC 105.7 (was
28.8 with SNOwGLoBES's table, still available as `--nc-model snowglobes`).

- `snufish export-pkl` (#24): the solar neutrino spectrum (per component, at
  the detector, by period and site) as a plotipus pickle.
- `snufish export-xsec` (#25, #27): neutrino-argon cross sections from 0.5 to
  100 MeV as a plotipus pickle, with the settings of DUNE's official MARLEY
  production (MARLEY v1.2.1, `ve40ArCC_Bhattacharya2009` in the allowed
  approximation, `ES.react` at tree level). ν̄e CC on 40Ar is the HF+CRPA
  calculation of Van Dessel, Jachowicz & Nikolakopoulos, PRC 100, 055503
  (2019) (`reference/xsec/vandessel2019_nuebar_ar40.yaml`, free g_A = 1.27;
  `--nuebar_model vandessel2019_quenched` gives a legacy g_A = 1.00 variant,
  SNUfish's estimate), no longer SNOwGLoBES's undocumented table.
- NC inelastic on 40Ar (#29), the new default of the engine, the calculator,
  `export-xsec` (`--nc_model`) and the DUNE scripts: the measured spin-flip
  1+ levels of Tornow et al., PRC 112, 054320 (2025) (9.3 to 10.3 MeV,
  ΣB(M1) = 1.31(18) μN², allowed approximation with MARLEY 2's form factors)
  plus the HF+CRPA continuum of Van Dessel et al. 2019 (fig. 8), the
  combination MARLEY's authors propose (arXiv:2604.26801). Each part and
  SNOwGLoBES's table (legacy) stay selectable. The rate is uncertain: 93 % of
  it comes from the continuum's onset at E_ν = 10 to 12 MeV, read from a
  figure (61 to 156 per kt-yr within half a plotting step), and the continuum
  may overlap the measured levels above 9.9 MeV (docs/status-of-inputs.md).
- PEANUTS v1.7 (#26): B2 and B3 rerun, bit-for-bit unchanged.
- Web page (#21 to #23): Zenodo DOI badge and citation, the eighth Home
  finding (one or two inputs limit each prediction), B5 tab in physics order,
  observed-rates table scrolls on mobile.
- B4 tab (#30): NC on 40Ar card: the default model, its parts and
  SNOwGLoBES's table, the band of the figure reading, where the 8B + hep NC
  rate comes from (E_ν cut), and the rates of each variant.

Submodules (Zenodo archives the repository without them): NuFast-Earth at
`327586d` (v1.2.0-3), PEANUTS at `1783f9f` (v1.7).

Cite the version DOI of 0.3.0,
[10.5281/zenodo.24383275](https://doi.org/10.5281/zenodo.24383275), or the
concept DOI 10.5281/zenodo.24045166.

## Files

| File | Holds | Status |
|---|---|---|
| `CITATION.cff` | citation metadata (GitHub's "Cite this repository") | 0.5.0: `version`, `date-released` 2026-11-26 (set to the tag date if it differs); `doi` the concept DOI until step 4 puts in the v0.5.0 version DOI |
| `.zenodo.json` | the metadata Zenodo's GitHub integration reads at each release (it takes precedence over `CITATION.cff`) | 0.5.0 (ORCID included) |
| `pyproject.toml`, `src/snufish/__init__.py` | `version`, `__version__` | 0.5.0 (plotipus pinned to its `v0.1.0` release) |
| `catalogue/tools/snufish-reference.yaml` | `reference` | the concept DOI (cites every version); the comment lists the version DOIs |

## Steps

0. Done: plotipus `v0.1.0` is released (version DOI
   [10.5281/zenodo.24044062](https://doi.org/10.5281/zenodo.24044062),
   concept DOI 10.5281/zenodo.24044061) and `pyproject.toml` pins
   `plotipus @ git+https://github.com/mantheys/plotipus.git@v0.1.0`.
1. Link the repository in Zenodo (GitHub integration, switch it on for
   `mantheys/snufish`). From then on every GitHub release is archived.
2. Fill in the table above; bump `version` in `pyproject.toml` and
   `CITATION.cff`; commit on `main` with CI green.
3. Tag and release: `git tag -a v0.2.0 -m "SNUfish 0.2.0"`, push the tag,
   create a GitHub release from it. Zenodo archives the tag and mints a
   version DOI and (the first time) a concept DOI.
4. Put the DOI in `CITATION.cff`, `catalogue/tools/snufish-reference.yaml`
   and the README; commit (this is after the archived version, so the
   archive itself carries no DOI: that is normal).
5. Cite the **version DOI** in the paper and the thesis (the exact code that
   made the numbers), and the commit of the inputs (contributions record
   their own).

## What a reader needs from the archive

- the engine and the reference solvers (`src/snufish`), the inputs
  (`reference/`, `benchmarks/`, `contributions/`) and the scripts that
  imported them (`scripts/`, `contributions/*/scripts`);
- the NuFast-Earth submodule at its pinned commit (Zenodo archives the
  repository without submodules: name the commit, 327586d, in the release
  notes);
- the commands that made each quoted number (for the DUNE tables, the
  script in [dune-solar-tables.md](dune-solar-tables.md)).
