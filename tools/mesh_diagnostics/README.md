# Isolated mesh candidate diagnostics

This unshipped developer study compares original meshine with a four-call
scalar-length candidate. It leaves `dependencies.json` unchanged.
`manifest.json` records the exact shared commit, package/test file hashes,
reviewable patch, candidate source hash, inputs and runtime reference.
Wrong commits, changed bytes and existing output directories are rejected.
Only verified files are copied; the upstream checkout is not edited.

The candidate uses `math.hypot` for scalar 2D lengths in `_treated_apices`
and `_lattice_point`. A previously observed one-ULP difference in
`numpy.linalg.norm` changed a small-angle lattice point and later refinement.
The candidate does not round points or change numerical criteria. This is
separate from the rectangular PCB conductor refinement failures.

## Run

Use a checkout of the exact manifest commit and prepare fresh copies:

```sh
python tools/mesh_diagnostics/run.py prepare UPSTREAM_CHECKOUT ORIGINAL_COPY original
python tools/mesh_diagnostics/run.py prepare UPSTREAM_CHECKOUT CANDIDATE_COPY candidate
```

Build meshine from `COPY/packages/meshine`. During its build, set
`OPENPHYSICS_DOCS_REF` to the manifest commit and `GIT_CEILING_DIRECTORIES`
to the absolute copy directory, so documentation links use the upstream
package path. Preserve Apache-2.0 LICENSE/NOTICE. Build the other shared
wheels from the unchanged upstream checkout and SIPI from its independent
checkout. Install each variant in a separate environment, audit exact wheel
payloads with `tools/verify_install.py`, and clear `PYTHONPATH`. A package
version alone does not identify a candidate build.

Run the six unchanged 2D test files listed in the manifest from the copied
`tests/meshine` directory, then run the probe with the corresponding installed
environment. Set BLAS/OpenMP threads to one and use fresh output paths:

```sh
python tools/mesh_diagnostics/run.py probe original ORIGINAL_REPORT
python tools/mesh_diagnostics/run.py probe candidate CANDIDATE_REPORT
```

The `Mesh candidate diagnostics` workflow automates these checks for separate
original/candidate jobs on Linux, macOS and Windows. It records exact SIPI
commit/tree, shared commit, source/wheel hashes and library versions. It uses
NumPy 2.5.4, SciPy 1.18.1 and Shapely 2.2.0, installs existing wheel
dependencies and publishes no package, executable or website.
Run tool regression with `python -m pytest -q tools/tests`.

Install `threadpoolctl==3.6.0` for these developer tools. Its BSD-3-Clause
license requires retaining its copyright, conditions and disclaimer on
redistribution and forbids endorsement by the copyright holder. The reviewed
package has no bundled native libraries; its license remains in the installed
wheel. It is a diagnostic/CI dependency, not a SIPI runtime or EXE dependency.
`environment.json` records NumPy runtime CPU features and the active BLAS
libraries, versions, architecture selection and thread counts. Observation
does not set CPU selection, floating-point modes or thread limits.

## Interpret the evidence

Nine original saved-study inputs with two width samples each and the original
paired-conductor coarse/fine meshes give 20 solves. Each completed case is
saved before the next. Errors retain completed names, active input and partial
trace. JSON/NPZ creation is exclusive, so reruns cannot overwrite failures.
Observer hooks restore after success or failure. Use a fresh, single-process
probe; the observer is not thread-safe and must not run inside an application.

`reference.json` retains 18 native impedance observations with their exact
source revisions and environment. Every impedance must meet the existing
relative runtime limit **1e-9**. This is reproducibility, not independent
physical accuracy. All 20 solves are recorded before comparison; failures
write `comparison.json`, `failure.json` and return a failing exit code.
Do not regenerate references or change geometry to make this comparison pass.

Each case records actual Domain.build points/segments/regions, first Delaunay
points/simplices, later call hashes/shapes, triangle-data hashes, treated-apex
units, final mesh identity and C/C0/C_loss/L. The two conductor NPZ snapshots
contain actual vacuum surface-current inputs; load with
`numpy.load(path, allow_pickle=False)`. Matrix entries and conductor factors
are observations, not replacements for original numerical/convergence gates.

The first triangle-data call also retains its points, triangle indices, four
output arrays and Delaunay round index. Replaying `_triangle_data` on these
exact arrays separates arithmetic differences from different triangulations;
the observer does not alter the arrays returned to refinement.
The next two Delaunay calls and second triangle-data call retain bounded
`snapshot` arrays as well. Their hashes remain in the original rows. Use
`delaunay_snapshot(record, index)` or `triangle_snapshot(record, index)` from
`compare.py` to validate and read them; missing old snapshots return `None`,
never an empty successful comparison.

Compare two downloaded probe directories without rerunning field solves:

```sh
python tools/mesh_diagnostics/compare.py LEFT_PROBE RIGHT_PROBE NEW_REPORT.json
```

The comparison verifies stored array hashes, distinguishes triangle ordering
from connectivity, and evaluates changed internal edges with exact rational
orientation/incircle predicates on the recorded binary64 coordinates. A zero
incircle determinant identifies four exactly cocircular vertices; it does not
validate the whole triangulation or establish a final error bound. Changed
coordinates are reported rather than treated as matching node indices. When
both traces include the first triangle-data arrays, output differences are
measured only if their complete input arrays match. Older traces explicitly
report that these arrays are unavailable. Reports are created exclusively.

At `21624a9`, diagnostic run `43549799850` passed all 265 original mesh tests
in each of six jobs. Windows original/candidate and Linux candidate passed
the 18 impedance comparisons. Linux original failed one; macOS original and
candidate each failed all 18 at the retained 1e-9 limit. In the candidate
Linux/macOS traces, all 20 initial point sets matched. Six initial
triangulations differed in connectivity; all 32 changed internal edges across
both sides had exact zero incircle determinants. The remaining 14 cases had
matching initial connectivity, with subsequent divergence still unresolved.
This observation does not accept the candidate or explain all later changes.

Replacing only the initial conductor triangulation with the recorded macOS
connectivity, then continuing on Linux, reproduced the original Linux final
mesh and conductor values exactly at both mesh sizes. Thus the initial
diagonal choice alone does not explain the final platform difference. Replaying
all 20 macOS first triangle-data inputs on Linux reproduced circumcenters,
radii and centroids exactly; angles differed by at most 4.44e-16 radians, with
identical raw 28-degree classifications. Later refinement remains unresolved.

A controlled CPU-dispatch experiment with NumPy 2.5.4 and OpenBLAS
0.3.34.106.0 reproduced the separate scalar-length discrepancy. On the same
Linux installation, SkylakeX and Haswell paths produced 98.87655849123043 and
98.87641768741268 ohms for the retained asymmetric unbacked sample. The
isolated candidate produced 98.87655849123043 and 98.87655849123048 ohms.
This is a controlled observation, not evidence of which CPU path earlier CI
jobs used, and does not resolve the macOS conductor gate.

Compare the same case and stage. Different node hashes alone do not establish
physical error; identical impedance does not prove identical meshes. This
study does not validate 3D refinement, arbitrary geometry, material data,
conductor loss or executable distribution. The original macOS 5% conductor
gate and parked browser failure remain separate. Passing diagnostics does
not authorize a product pin change or accept the UI candidate.

[한국어](README.ko.md)

## Exact cocircular tie experiment

`ties.canonical_ties(points, triangles)` is an unshipped diagnostic for an
already valid, unconstrained triangulation. It returns ordered CCW triangles
and a flip count. Coordinates remain unchanged. Vertices are ranked by their
coordinate pairs; an interior diagonal is replaced by the smaller ranked
alternative only when the four binary64 points are **exactly** cocircular and
the quadrilateral is convex. Fraction predicates use no proximity threshold.
Every flip decreases the ranked edge multiset, preventing a flip cycle. The
helper does not validate the entire domain, preserve interior constraints or
repair non-Delaunay input. It is not called by the product mesher and changes
neither the existing `legacy` nor `stable` candidate-order contract.

The tests cover 288 rectangle order/scale/translation combinations, 60 fans of
12 integer-coordinate points on an exact radius-five circle, an adjacent
binary64 value that must not be treated as a tie, idempotence, boundary/area
preservation and rejected malformed records. This establishes those contracts,
not general triangulation accuracy or platform convergence.

For the retained `0a7395d` Linux/macOS candidate traces, 58 of the 60 first-three
stage pairs have the same point set. Fourteen of those pairs have different
connectivity before normalization; all 58 have identical ordered triangles
after the experiment. The other two pairs have different coordinates and are
excluded from this same-input comparison.

Full-mesh experiments remain separate failures. Replacing axis-aligned right
triangle circumcenters alone gives a conductor coarse/fine factor change of
0.050451984547489746 and fails 17 of the 18 original runtime comparisons.
Applying only this exact-tie/order intervention to the installed scalar-length
candidate on Linux gives 19,598/75,121 coarse/fine nodes and a conductor factor
change of 0.05765770656716615. Both exceed the unchanged 0.05 conductor gate.
The second experiment takes about 123 seconds for both meshes on that host;
it is not a portable performance guarantee. Neither experiment is a product
fix or grounds for replacing original failure records, fixtures or criteria.
