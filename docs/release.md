# Releasing a citable version

Ready to tag: the metadata is filled in, but no tag exists and nothing is
archived yet. The first release is **v0.2.0** (0.1.0 is the untagged development version; 0.2.0
adds the DUNE table options: `night_fraction`, `nu_threshold`, `nc_ar40`,
the SOLAR night).

## Files

| File | Holds | To fill in before tagging |
|---|---|---|
| `CITATION.cff` | citation metadata (GitHub's "Cite this repository") | `date-released` if the tag is not made on 2026-11-07; the DOI after Zenodo mints it |
| `.zenodo.json` | the metadata Zenodo's GitHub integration reads at each release (it takes precedence over `CITATION.cff`) | done (ORCID included) |
| `pyproject.toml`, `src/snufish/__init__.py` | `version`, `__version__` | done (`0.2.0`; plotipus pinned to its `v0.1.0` release) |
| `catalogue/tools/snufish-reference.yaml` | `reference` | the concept DOI (cites every version) |

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
