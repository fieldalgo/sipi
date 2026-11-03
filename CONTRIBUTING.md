# Contributing

SIPI uses the Apache-2.0 license; preserve LICENSE, NOTICE and upstream attribution.
Keep each change in a self-contained commit, including validation evidence and limits.
Independently validated changes may be grouped into a batch PR. Work on topic branches;
show changes before PR submission when requested. Use Draft, review, Ready, all required
checks, Rebase and merge, then verify post-merge CI. Never force-push shared history.
Do related checks locally and full regression in CI. Preserve numerical tolerances,
independent analytical/reference comparisons and convergence studies. An unrun check
is not a pass. Keep public code/examples English and usage/validation docs English/Korean.
Check exact dependency versions, licenses and bundled native notices before distribution.

SIPI releases independently of galerkin and meshine. Record supported dependency versions
and tested artifact hashes. Do not automatically publish from branches or tags. Validate
installed wheels outside the source checkout on supported platforms before release.
See [development](docs/development.md) and [third-party software](docs/third-party.md).
