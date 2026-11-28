# Development

See [product and calculation boundaries](architecture.md) for responsibility
ownership and the proposed order of extracting a headless line library.
The existing package/API remains unchanged.

See [isolated mesh candidate diagnostics](../tools/mesh_diagnostics/README.md)
for exact-source original/candidate builds, installed payload checks and
cross-platform refinement traces. That diagnostic keeps its historical source manifest and runtime references;
its preparation command does not select the current product dependency.
Original numerical criteria remain unchanged.

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

SIPI reaches the shared boundary-panel solvers only through the public
`galerkin.panel_electrostatics` module. Its arguments are SI: `box_size` is the
rectangle's (width, height) in m, and conductors are selected with
`ground_indices`, `signal_indices` or `signal_index`. `CrossSection` lengths
are already in m, so SIPI passes the same numbers without conversion, and the
results are the internal solvers' result objects, bit for bit. Saved
shape-panel requests keep their `width` and `height` keys.

Give large parametrized test inputs short explicit `ids`. Pytest puts the node
ID in `PYTEST_CURRENT_TEST`; Windows limits an environment-variable value to
32767 characters. Keep the actual large input and its rejection criterion intact.

## Continuous validation

The validation workflow runs source and installed-artifact regression in separate
Linux, macOS and Windows jobs, with twenty-four partitions per suite. Each job retains
a six-hour limit. Each platform has its own table,
`tools/shards/durations-<linux|darwin|win32>.json` (seconds per unit from the JUnit XML
of complete CI runs on that platform), because the same tests take different times on
each runner. A unit is a whole test module, keeping module fixtures together, except
in the modules the table lists under `split`, whose cases are separate units; only
modules whose expensive cases share no module fixture are split (today the two
harmonic corner-face panel-line modules, six independent 5–14 minute line solves
each). The guard corner-conductor module stays one unit: its module fixture is one 32-panel
field solve, and its refinement test solves the same 32-panel field again and a 48-panel one
(about 1, 1 and 2.5 fixture times, nearly all of the module), so any split recomputes the
fixture and adds time without shortening the unit that holds the refinement test. Recorded units go largest first to the partition with the least recorded time;
a unit missing from the table keeps the stable SHA-256 of its module path (of its node
ID in a split module).
All cases are collected before
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
--sipi-shard-count=24 --sipi-shard-index=0
--sipi-shard-report=.validation/source-shard.json` to the source command above;
use indices 0 to 23 in separate runs with fresh report paths. The running platform's
table is used unless `--sipi-shard-durations=<linux|darwin|win32>` names another. For the
installed runner, use `--shard-count=24 --shard-index=0`; it copies the plugin and the
durations tables outside the checkout and still audits all four wheels and clears
PYTHONPATH.

Refresh the tables when modules are added or their times change much: download the
`validation-<os>-<suite>-<i>` artifacts of one complete run
(`gh api repos/fieldalgo/sipi/actions/runs/<id>/artifacts`), write the node IDs collected
now with `PYTHONPATH=src python -m pytest -q --collect-only tests/sipi > collected.txt`,
then from the repository root, for each platform (`ubuntu-latest` and `linux`,
`macos-15` and `darwin`, `windows-latest` and `win32`), run
`python tools/pytest_shard.py --table <table> --update <os>-source-*/source.xml
--update <os>-installed-*/installed.xml --split <the split modules> --collected
collected.txt --source "<run, commit, date, files>"`. Each `--update` is one complete suite
run; a unit's time is the mean over the runs that have it. Cases no longer collected are
left out. Each table records its source and command.
`tools/tests/test_shard_durations.py` checks the format, the deterministic plan, the
balance bound and that no unit exceeds 1.1 times a twenty-fourth of its table.

The manifest (`sipi.pytest-partition/3`) retains every original node ID, its
collection hash, the name and the SHA-256 of the canonical durations table it used, the
selected IDs, completed IDs and exit status. Existing manifests are refused, and missing
or partial execution cannot establish a passing suite. `tools/check_shards.py`
requires all indices, identical original collections, one table named by every
partition (with `--durations-table`, the expected one) and equal to the checkout's,
selections equal to the plan computed from it, exact disjoint coverage
and successful completion of every selected case. The plans of different platforms
differ, but the evidence of each platform and suite must still cover every collected
case exactly once. Its explicit `--collect-only`
mode verifies discovery only and reports `executed: false`.
The workflow's final coverage job checks all six platform/suite groups, each against
its platform's table, and the shared source/installed product collection. A failed or interrupted partition
fails that check even when its other partitions pass. Check names include the
partition index; required-check configuration must be reviewed before integration.
This scheduling change does not fix existing numerical failures, certify a new
platform or guarantee that future test growth fits the time limit.
With three partitions, the largest partition held 4.7 hours of recorded
test time on Linux, and runner speed varied enough that Linux and Windows
jobs exceeded six hours and were cancelled. With eight, the same module
times give at most 2.1 hours per partition. Validate run 45965021952 recorded
854 minutes of Linux source test time in eight hash-assigned partitions of 84 to
148 minutes, and jobs of 72 to 210 minutes across the three platforms. The same
module times balanced over sixteen partitions give 53 minutes each; runner speed
still varies, and a module absent from the table is not balanced, so later growth
must be checked again.

Validate run 46099046636 then took 108 minutes: sixteen parts planned from that Linux table
gave jobs with median/maximum 50/85, 47/104 and 63/108 minutes on Linux, macOS and Windows,
because macOS and Windows times differ from Linux and two panel-line modules of 34 to 84
minutes could not be split. With each platform's own table from that run, the split
modules and the studies moved to the dispatch-only job, the largest recorded part is
45/48/57 minutes with sixteen parts and 30/34/38 minutes with twenty-four (twenty: 36/39/45;
twenty-eight: 25/34/32). Twenty-four is used: the macOS floor is one conductor module of
33.6 minutes whose module fixture is shared, so more parts no longer help there, and the
same test varied up to about 1.5 times between runs. The wall time of a run with
twenty-four parts, and whether all 144 jobs (48 on macOS) start together, are not yet
measured.

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

### Finite-resolution studies (dispatch only)

The corner-face finite-resolution studies solve six complete lines each (base, finer
dielectric mesh, finer panels, both, and two wider outer boxes) and took 6 to 60 minutes per
case on one runner. They are defined only with `SIPI_RESOLUTION_STUDIES=1` and run in the
dispatch-only `resolution-studies` job of the validation workflow (`gh workflow run
validate.yml --ref <branch> -f resolution_studies=true`) on Linux, macOS and Windows. In the
regular partitions each study's base line is solved and must reproduce the values recorded
with the study in `tests/sipi/reference_data/resolution_studies/finite-resolution-studies.json`
within a matrix-relative 1e-9. The mesher may triangulate exact cocircular ties differently by
platform (macOS in the recorded runs), so the record keeps one variant per dielectric mesh
(SHA-256 of nodes and triangles). A mesh equal to a variant must match it within 1e-9; a
mesh matching no variant, such as a new runner image's triangulation, is compared with the
closest variant within a matrix-relative 1e-4, above the largest recorded difference between
the two meshes (2.2e-5) and a hundred times below the 1% study criterion. The JUnit property
`resolution_study_reproduction` records which path was taken. The accuracy and
convergence checks therefore stay in the regular suite as reproduction of the studied
resolution, and the study criteria themselves are unchanged.

| Module | Study test (cases) | Linux CI time | Criterion, checked when the study job runs | Regular partitions |
| --- | --- | --- | --- | --- |
| `test_two_ground_harmonic_three_active_corner_face_resolution` | `test_actual_layered_three_signal_finite_comparisons` [0] | 40.0 min | Six lines, four current solves; every comparison: each R, L_internal, L_external, C, G, C0 entry within 1% of the larger magnitude at every frequency | Base line reproduces the record (1e-9) |
| `test_two_ground_harmonic_guard_corner_face_resolution` | `test_actual_layered_two_signals_and_guard_finite_comparisons` [0] | 39.3 min | Same | Same |
| `test_two_ground_linear_corner_face_resolution` | `test_actual_layered_one_and_two_signal_finite_comparisons` [0], [1] | 5.8, 22.1 min | Same | Same, for both cases |

`tests/sipi/test_resolution_study_record.py` checks, without field solves, that the record
holds an accepted outcome for every case on all three platforms, that every recorded copy is
assigned to a mesh variant, and that the study tests exist only with the gate. After the
study job, regenerate the record from its JUnit XML (or that of a Validate run with the gate)
with `PYTHONPATH=src python
tests/sipi/reference_data/resolution_studies/generate_finite_resolution_studies.py --junit
<platform>/<suite>=<xml> ... --source "<run>"`; the generator also solves each base line
locally and requires it to match the variant of its own mesh.

The durations table leaves out the four study cases (`--collected` with the node IDs collected
now): 747 instead of 854 recorded minutes, 46.7 minutes per partition. The new reproduction
tests have no CI time yet; locally they took 9 minutes together on one thread.

Five further heavy tests compared several resolutions or ran a study through another path.
Each was read and decided as below. Times are minutes in Validate run 46099046636 (main
`b2cbb002`), source/installed, on Linux, macOS and Windows.

| Test | What it checks | Time (min) | Decision | Regular suite now |
| --- | --- | --- | --- | --- |
| `test_two_ground_linear_corner_face_line_study.py::test_actual_scalar_sweep_refinement_and_complex_closed_forms` | The actual three-sample sweep at 32 panels per edge; for each sample R, L and C0 again at 64 and 128 panels, consecutive levels within rtol 1%; closed-form characteristic impedance and propagation constant at every level (rtol 1e-12); the row value equals Z0 | 20/35, 22/21, 45/35 | Split. The 64/128-panel refinement is a resolution study: the unchanged test runs only with `SIPI_RESOLUTION_STUDIES=1` | `test_actual_scalar_sweep_closed_forms_and_recorded_base`: the same sweep, closed forms and value check at 32 panels, and reproduction of each sample's R, L, C0 and Z0 recorded with the study (`linear-line-study-base.json`; 86 s locally) |
| `test_two_ground_harmonic_three_active_corner_face_resolution_document.py::test_actual_saved_finite_resolution_receipt` | The recorded three-active study's six lines (same inputs, same 1% criteria) run through `SavedExecutionRequest`; requires a complete, accepted receipt | 39/29, 33/32, 59/51 | Study, run a second time: dispatch-only. The saved path's complete, failed, disagreeing, interrupted, CLI and record behaviour is already checked field-free in the same module | `test_saved_document_runs_the_recorded_study` (field-free): the saved base line is the recorded study's base input, the outer lines, refined panel and budget are the study's; the resolution module reproduces that base line |
| `test_two_ground_harmonic_guard_corner_face_resolution_document.py::test_actual_saved_finite_resolution_receipt` | The same for the guard study | 25/25, 34/37, 46/30 | Same | Same |
| `test_two_ground_harmonic_guard_corner_conductor.py::test_real_physical_faces_and_whole_currents_refine_without_floor[0]` | Physical-face and whole current factors (C0, face and whole parts) at 32 and 48 panels per edge within 1%, and the module's own 32-panel path equal to the shared solve | 9/15, 12/12, 23/18 | Kept: the only check of these modules' current path with real fields (the other tests reuse the shared solve through a stub), and nothing recorded to reproduce | Unchanged. Time review: the 32-panel call repeats the module fixture's solve, but that repetition is the exact shared-solve check; the 48-panel level is the criterion. No reduction without changing what is checked |
| `test_two_ground_harmonic_three_active_corner_conductor.py::test_real_physical_faces_and_whole_currents_refine_without_floor[0]` | The same for three active conductors | 7/10, 30/21, 12/23 | Kept, as above | Unchanged, as above |

The line-study record keeps, per sample, the base level once per dielectric mesh: Linux and
Windows share one mesh, macOS another (R, L and C0 come from the boundary panels and agree
within 1.4e-14 across all six copies). The reproduction takes the same exact (1e-9) and
closest-variant (1e-4) paths as the corner-face studies and writes
`resolution_study_reproduction`. Regenerate it after a study run with `PYTHONPATH=src python
tests/sipi/reference_data/resolution_studies/generate_linear_line_study_base.py --junit
<platform>/<suite>=<xml> ... --source "<run>"`, which also solves the base sweep locally and
requires it to match the variant of its own mesh. The `resolution-studies` job also runs the
two saved-document receipts and the line-study refinement.

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

## Scalar mesh lengths and dependency identity

The development baseline in `dependencies.json` uses scalar `math.hypot`
lengths in four small-angle lattice operations. This avoids a BLAS
CPU-dispatch reduction difference at those operations. It preserves existing
coordinates, candidate-order contracts, mesh settings and numerical gates.
The two-ground capability remains an external galerkin API; SIPI remains an
independent consumer of individual shared package wheels.

This change does not guarantee identical meshes on every platform, resolve
cocircular triangulation or establish convergence of the original macOS
conductor cases. Revalidate the exact dependency artifacts for each consumer;
selected CPU-path or browser comparisons do not replace full regression or
physical references. Build all shared wheels from the recorded commit and
retain their hashes, including when their version strings have not changed.
The local development commit is not evidence of a published package or an
available remote build. No mesh fixture, runtime reference or numerical
acceptance threshold is regenerated by this dependency update.

## Short-panel arithmetic in the pinned dependency

The coordinated baseline retains accepted unequal-panel logarithmic integrals
exactly. Entries failing the original 32/64-point quadrature check are evaluated
again using local coordinates and must meet the same `1e-12` criterion. This
avoids losing tiny target motion at a large coordinate origin. Existing solver
controls, interpolation orders, panel grading and saved document contracts stay
unchanged. The independent shared checks cover one short/long geometric pair
in both source orders, with 60/80-digit reference integration and geometric
invariants. This arithmetic correction does not qualify new physical models,
arbitrary section accuracy or additional platforms.

## Wall-scaled panel boxes in the pinned dependency

The pinned shared revision no longer refuses a panel conductor cluster nearer
the side/top walls than its extent. Such clusters, in both the bottom-ground
and two-ground solvers, interpolate the wall and plane images on boxes no
wider than each conductor's distance to them, with the same 1e-10 check;
more than 256 boxes is refused before a field solve. Clusters admitted before
give bit-identical results. Panel diagnostics add `smooth_interpolation_boxes`
only when boxes were used. On the near-wall execution line of the tests,
panel C0 differed from an independent P2 volume solution by 4.4e-4 on its
saved 731-node mesh and by 5.8e-5 on the 3076-node default mesh.

## Two-ground interpolation boxes in the pinned dependency

The pinned shared revision repeats a failed one-box interpolation check of the
two-ground panel solver once on plane-scaled boxes, with the same settings and
1e-10 limit. Inputs that passed before give bit-identical results; coupled,
layered and broadside striplines that were refused now solve. SIPI two-ground
current diagnostics add `smooth_interpolation_boxes` and
`single_box_matrix_error` only when that repeat was used, so earlier outputs
keep their keys.

## Units and naming in the pinned dependency

The pinned shared revision merges OpenPhysics main with the units and naming
batch steps L2 and L3 under the existing shared development branch, keeping
every earlier shared commit and SIPI's previous pin as ancestors. SIPI imports
the assembly and solve kernels (`assemble_stiffness`, `assemble_mass`,
`assemble_load`, `solve_dirichlet`, the 3D stiffness and edge matrices) from
`galerkin.kernels`. The IR-drop solve uses the SI argument names and passes
each sink as an inward current density, the exact negation of the previous
outward value. The galerkin capacitance cross-check passes
`relative_permittivity`. Public SIPI calculation names, inputs and results are unchanged; only the
geometry adapter `to_geometry_v1` writes the format 0.3 parts the pinned simcase
reads ([overview](packages/sipi/overview.md)).

With the previous and the new pinned wheels, the 16 example scripts printed
byte-identical output and the test collection kept the same node IDs. The
stored scikit-fem comparison script keeps its recorded hash and runs against
its recorded product commit. This dependency update does not qualify a new
physical model, platform or published package.
