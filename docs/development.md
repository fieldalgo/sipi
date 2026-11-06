# Development

SIPI uses externally installed galerkin and meshine packages. For coordinated development,
install their wheels built from the commit in `dependencies.json`, then install this project
with `python -m pip install --no-deps .`. The pinned commit is a development baseline,
not evidence that equivalent packages have been published to PyPI.

Unreleased development commits can share a package version. Record the exact
SIPI commit and wheel SHA-256, plus the dependency artifacts, with numerical
results; a version string alone cannot identify such a build.

Run `PYTHONPATH=src python -m pytest -q tests/sipi` for the source suite (set
`$env:PYTHONPATH="src"` first in PowerShell). Build a wheel and install it in a clean
environment, copy tests outside the checkout and run the same suite there. Include
scikit-rf 2.2.0 for independent network checks and scikit-fem 12.0.2 for
independent finite-element comparisons. Both are test-only dependencies in
`sipi[test]` and explicitly installed by CI. Installing ordinary galerkin wheels
does not install their reference-tool extras. Set `OPENPHYSICS_REQUIRE_CROSSCHECK=1`
to reject missing reference tools instead of skipping those checks.
`integration/test_geometry_adapters.py`
checks the versioned geometry contract with the matching simcase reader; run it explicitly.

`provenance.json` identifies every imported file and its original SHA-256. Numerical
implementation and fixtures are unchanged. This extraction does not publish the website,
create a Windows EXE, or establish new platform support. Source history remains available
at the recorded upstream commit; this repository starts with a traceable snapshot.

[한국어](development.ko.md)

## Exact installed-artifact validation

Run `python -m pytest -q tools/tests` for the validation tools. After installing
exact first-party wheels, run `python tools/check_installed.py --wheels WHEEL_DIRECTORY`.
The directory must contain exactly one wheel each for sipi, galerkin, meshine and
simcase. The last package is used only for geometry contract integration tests.
The runner uses a fresh process outside the checkout, clears PYTHONPATH, checks
import origins and compares installed payload bytes with each wheel. Identical
version numbers alone do not establish that the correct code was tested.
Installer-rewritten RECORD files are excluded; code, metadata, licenses and other
wheel payload files are checked. Extra installed Python modules are rejected.

`.validation/installed.json` records status, failing phase/error, artifact SHA-256,
checked file counts and runtime versions. Previous XML is removed before starting;
a failed launch/audit leaves a failed JSON report, not an old passing XML. A failed
numerical test keeps its fresh failing JUnit report. These checks verify artifact
identity, not the physical accuracy or upstream provenance of an arbitrary wheel;
the existing numerical/reference tests and pinned build remain required.
