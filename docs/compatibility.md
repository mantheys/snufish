# Compatibility

What a version number promises, for the benchmark specs, the contributions
made against them and the SNUfish package. The rule applies in full from
1.0.0 ([roadmap-1.0.md](roadmap-1.0.md)); until then, specs are drafts and
the validator accepts only what each spec lists (below).

## Spec versions

Every `benchmarks/<id>/spec.yaml` has a `version` (MAJOR.MINOR.PATCH) and
a `changelog` with one entry per version: `version`, `date`, `kind`
(`initial`, `patch`, `minor`, `major`) and `changes`. Any change to a spec
bumps its version and adds an entry.

| Change | Kind | Contributions made against the old version |
|---|---|---|
| Wording, comments, sources, descriptions; a correction that moves no value a contribution gives | patch | valid |
| A new optional variant, quantity, grid, detector, response or site; a relaxed check | minor | valid |
| A change of any value an existing variant fixes (a constant, a grid point, an oscillation parameter, a matter, solar or Earth model, a flux shape, a target count); a renamed or removed key, variant, quantity or grid; a new *required* variant, quantity or grid; a tightened check; a change of the columns or of the `meta.yaml` keys | major | no longer valid |

A new quantity is minor only where the spec does not require every quantity
(`all_quantities_required: false`, as in B4 and B5); in B2 and B3, which
require all, it is major.

**Registries.** The parameter sets of B1
(`reference/oscillation/parameter_sets.yaml`) and the solar models of B2
(`benchmarks/B2_sun/models.yaml`) are inputs that contributions are
computed with. An entry is never edited once released: a correction is a
new id, and the old one is marked legacy in `reference/status.yaml`. Adding
an entry is minor.

## Which contributions are valid

A contribution's `meta.yaml` keeps the `benchmark_version` it was computed
with; it is never restamped. `snufish validate` accepts it when the spec
accepts that version (`Spec.accepts`):

- the same version as the spec; or
- a version the spec lists in `compatible` (earlier versions whose
  contributions are still exact, for instance across the move to 1.0.0); or
- from 1.0.0 on, the same major version and no newer than the spec: minor
  and patch changes are additive, so a contribution made against 1.0.0 stays
  valid under 1.4.2.

Before 1.0.0, minor versions may break (semantic versioning's 0.x), so only
the first two apply. A contribution that a new major version no longer
accepts stays in the history and in the Zenodo archive of the release it was
made under; to appear in the plots again it is rerun against the new spec.
`compatible` may name only versions with no major change after them (the
tests check it).

## The package

From 1.0.0 the package follows semantic versioning on its public interface:
the `snufish` subcommands with their options and defaults, the contribution
format, the frames `snufish build` writes and the public Python API
(the list is written down with item 3 of the roadmap; everything else is
internal and may change in any release).

- A minor release may add subcommands, options, frame columns and API
  names; a major one may remove or rename them.
- Something to be removed is deprecated first, with a warning, for at least
  one minor release.
- A change of a default physics input (a new state-of-the-art cross section,
  solar model or parameter set as the engine's default) is a minor release.
  Its release notes list every quoted number that moves; each release's
  version DOI keeps the numbers made with it reproducible.

## Bumping a spec

1. Classify the change with the table above.
2. Bump `version` and add the `changelog` entry.
3. Minor or patch: nothing else; existing contributions stay valid. Major:
   rerun the contributions (or list in `compatible` the versions whose data
   are provably unchanged), and update the products, `benchmarks.md`,
   `status.md` and the page.
4. New contributions record the new version (`spec.version`, as every
   wrapper does).
