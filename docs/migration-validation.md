# Extraction validation

Baseline: fieldalgo/openphysics b8f7c0427b75362ed5e8298bc81682e7076abe4e.
The numerical source, tests and executable examples (60 files) retain their original
SHA-256 values in provenance.json. The original full commit history remains upstream;
this repository starts from an attributed snapshot, not a rewritten history export.

On Linux / CPython 3.12.14, the extracted SIPI wheel and separate galerkin/meshine
wheels passed 598 regression/installed-consumer tests (377.73 s). The simcase geometry
contract passed 18 tests. A separate run outside the checkout passed 25 tests comprising
the seven installed-wheel consumers and those same 18 geometry tests; these counts overlap.
The wheel payload rebuilt from the sdist is byte-identical to the direct wheel payload.

First-party packages were newly built and installed from the pinned snapshot. Third-party
packages were reused from an existing environment because network access was unavailable;
a fresh online dependency resolution was not verified. NumPy 2.5.4, SciPy 1.18.1,
Shapely 2.2.0 and scikit-rf 2.2.0 were used. macOS/Windows and the proposed remote CI
workflow have not been run. A Windows EXE and web consumer cutover are not part of this result.

[한국어](migration-validation.ko.md)
