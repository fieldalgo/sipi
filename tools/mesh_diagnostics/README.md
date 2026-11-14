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

Compare the same case and stage. Different node hashes alone do not establish
physical error; identical impedance does not prove identical meshes. This
study does not validate 3D refinement, arbitrary geometry, material data,
conductor loss or executable distribution. The original macOS 5% conductor
gate and parked browser failure remain separate. Passing diagnostics does
not authorize a product pin change or accept the UI candidate.

[한국어](README.ko.md)
