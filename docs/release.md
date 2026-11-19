# Releasing a citable version

Released: **v0.2.0** is tagged and archived on Zenodo, version DOI
[10.5281/zenodo.24045167](https://doi.org/10.5281/zenodo.24045167), concept
DOI (resolves to the latest version)
[10.5281/zenodo.24045166](https://doi.org/10.5281/zenodo.24045166). It is
the first release: 0.1.0 is the untagged development version; 0.2.0 adds the
DUNE table options (`night_fraction`, `nu_threshold`, `nc_ar40`, the SOLAR
night). The steps below are what it took; repeat 2 to 4 for the next one.

Prepared: **v0.3.0** (steps 2 done, 3 and 4 to do). Release notes below.

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

Submodules (Zenodo archives the repository without them): NuFast-Earth at
`327586d` (v1.2.0-3), PEANUTS at `1783f9f` (v1.7).

Cite the version DOI of 0.3.0 (Zenodo mints it at the release) or the concept
DOI 10.5281/zenodo.24045166.

## Files

| File | Holds | Status |
|---|---|---|
| `CITATION.cff` | citation metadata (GitHub's "Cite this repository") | 0.3.0: `version`, `date-released` 2026-11-19 (the tag date), concept DOI until step 4 |
| `.zenodo.json` | the metadata Zenodo's GitHub integration reads at each release (it takes precedence over `CITATION.cff`) | 0.3.0 (ORCID included) |
| `pyproject.toml`, `src/snufish/__init__.py` | `version`, `__version__` | 0.3.0 (plotipus pinned to its `v0.1.0` release) |
| `catalogue/tools/snufish-reference.yaml` | `reference` | unchanged (the concept DOI, cites every version) |

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
