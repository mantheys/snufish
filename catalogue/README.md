# Tool catalogue

One YAML file per tool in `tools/`, named by the tool id used in
`contributions/<tool>/`. Fields left `null` are not yet verified; fill
them from the tool's own repository or paper, never from memory.

```yaml
id:            short id (lower case, dashes)
name:          display name
description:   one or two sentences
language:      main implementation language(s)
license:       SPDX id
repository:    URL
documentation: URL or null
reference:     arXiv id or DOI of the paper to cite
maintainers:   [names]
benchmarks:    benchmark ids the tool can contribute to
status:        draft | verified (checked against the tool's own sources)
```
