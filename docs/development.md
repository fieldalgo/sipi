# Development

See [product and calculation boundaries](architecture.md) for responsibility
ownership and the proposed order of extracting a headless line library.
The existing package/API remains unchanged.

See [isolated mesh candidate diagnostics](../tools/mesh_diagnostics/README.md)
for exact-source original/candidate builds, installed payload checks and
cross-platform refinement traces. The product dependency pin and original
numerical criteria remain unchanged.

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

`provenance.json` identifies every file in the original extraction snapshot and its
upstream SHA-256. That snapshot preserved the numerical implementation and fixtures;
subsequent commits extend the independent engine. Use the exact commit and wheel
hash to identify later builds, without rewriting the original provenance record.
The extraction did not publish the website, create a Windows EXE or establish new
platform support. Original source history remains at the recorded upstream commit.

[한국어](development.ko.md)

## Exact installed-artifact validation

Install `threadpoolctl==3.6.0` for the unshipped numerical-runtime observer,
then run `python -m pytest -q tools/tests` for the validation tools. After installing
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

The current coordinated baseline uses galerkin and meshine 0.0.2 development
wheels. The declared range also retains the earlier 0.1 development line;
neither range nor version proves that an unreleased API is present. Build from
the exact dependency commit and retain wheel hashes. The boundary-panel API
is a shared galerkin capability; changing this pin alone does not select it
for existing SIPI calculations.

Give large parametrized test inputs short explicit `ids`. Pytest puts the node
ID in `PYTEST_CURRENT_TEST`; Windows limits an environment-variable value to
32767 characters. Keep the actual large input and its rejection criterion intact.

## Continuous validation

The validation workflow runs source and installed-artifact regression in separate
Linux, macOS and Windows jobs, with three partitions per suite. Each job retains
a six-hour limit. Whole test modules are assigned by a stable SHA-256 of their
relative path, keeping module fixtures together. All cases are collected before
selection; a partition does not relax numerical criteria or mark omitted cases
as skipped. It runs for ready pull
requests, main pushes and pushes to the current independent-repository development
branch, so pre-merge validation can run without opening a pull request. Every job
retains the pinned independent references, wheel/sdist build, validation-tool checks
and failure reports. The installed suite includes geometry-contract checks. These
checks do not publish packages, executables or websites.

Validation uploads explicitly allow the hidden `.validation` directory while
restricting artifact paths to `.validation/*.xml`, `.validation/installed.json`
and `.validation/*-shard.json`. Each platform/suite/partition has its own artifact.
Without that option, the upload action excludes
the generated reports even when the tests wrote them successfully. Source
checkouts, wheels and other hidden files are not artifact inputs.

Development branch pushes retain the running validation and keep the newest
pending run. This permits incremental commits to be backed up without
cancelling their in-flight platform evidence. Pull-request updates still
cancel obsolete runs; main retains its full queue. A completed older commit
does not establish validation of a newer branch head.

`tools/pytest_shard.py` is an opt-in validation plugin, not a runtime dependency.
The ordinary local pytest and installed-check commands remain unpartitioned.
For an individual source partition, append `-p tools.pytest_shard
--sipi-shard-count=3 --sipi-shard-index=0
--sipi-shard-report=.validation/source-shard.json` to the source command above;
use indices 0, 1 and 2 in separate runs with fresh report paths. For the installed
runner, use `--shard-count=3 --shard-index=0`; it copies the plugin outside the
checkout and still audits all four wheels and clears PYTHONPATH.

The manifest retains every original node ID, its collection hash, the selected
IDs, completed IDs and exit status. Existing manifests are refused, and missing
or partial execution cannot establish a passing suite. `tools/check_shards.py`
requires all indices, identical original collections, exact disjoint coverage
and successful completion of every selected case. Its explicit `--collect-only`
mode verifies discovery only and reports `executed: false`.
The workflow's final coverage job checks all six platform/suite groups and the
shared source/installed product collection. A failed or interrupted partition
fails that check even when its other partitions pass. Check names include the
partition index; required-check configuration must be reviewed before integration.
This scheduling change does not fix existing numerical failures, certify a new
platform or guarantee that future test growth fits the time limit.

The paired surface-conductor and Cannonball refinement tests record
`conductor_refinement` JSON in their JUnit testcase properties before checking
convergence. The record includes the geometry, resolved coarse/fine meshes,
frequency samples, R/internal-L/C0 matrices, separate boundary loss factors,
current integrals and numerical-library versions. It serializes existing results
without extra field solves. Retain failed XML when comparing platforms: a small
flux mismatch does not by itself bound resistance error. The original mesh
fixtures, 5% resistance-change gate and current-return checks remain unchanged.

Browser saved-study checks write `study-N.json` before numerical parity assertions.
Each record preserves the exact input, actual downloaded result and native
reference, including failed rows. Preserve a failing run in its own directory;
reruns use a new directory. These records diagnose differences without changing
the parity gate or accepting a failed runtime.

The separate `Numerical platform checks` workflow runs a focused installed-wheel
suite on Linux, macOS and Windows when its selected development-branch paths
change. It audits imported payloads against four first-party wheels, records all
built wheel hashes, exact commits/tree and numerical-library versions, then runs
reactive-state limits/original invariants and original conductor convergence
checks. Both groups run even if the first group fails; failures still fail the job.
This focused suite supplements full regression and does not establish release
or executable support.

Set `SIPI_NUMERICAL_MESH_OUTPUT` to a fresh output directory to retain the actual
coarse/fine vacuum meshes used by `tests/sipi/test_crosscheck_conductor_p2.py`.
This opt-in test instrumentation saves nodes, triangles, ordered signal names,
signal node sets and ground nodes in compressed NPZ files, without another mesh
generation. Load with `numpy.load(path, allow_pickle=False)`. For replay, construct
`galerkin.Mesh(nodes, triangles, {})` and pass the saved signal/ground sets to
`sipi.conductor.surface_current_factors`; these snapshots do not contain a
dielectric model. Existing files are never overwritten. JUnit properties contain
the file SHA-256 and the computed boundary quantities. CI uploads the two groups'
original XML, environment JSON and mesh snapshots even when a test fails.

At `8694e70`, the focused installed run passed the same 220 reactive-state
cases on all three platforms. The seven conductor/reference cases passed on
Linux and Windows; macOS retained three original PCB refinement failures.
See the [conductor observations](packages/sipi/conductor.md) for the actual-mesh
replay and its limits. These results describe this selected suite and exact
commit, not the full regression status of later commits.

## Explicit two-ground development capability

The shared revision in `dependencies.json` supplies the generic two-ground
Laplace boundary capability. SIPI owns the metal laws, dielectric extraction,
[saved line](packages/sipi/two_ground_panel_line.md),
[paired goal](packages/sipi/two_ground_pair_goal_document.md) and
[manufacturing study](packages/sipi/two_ground_pair_study.md).
The current development revision may exist only on a local coordinated branch;
build its package wheels explicitly. Do not assume public CI can fetch it before
the shared branch is available. No existing calculation silently selects this
method. Source/installed tests establish only their stated cases and platform.
