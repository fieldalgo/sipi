# Independent FEM shape-energy reference observations

The three- and four-signal refined examples retain their successful independent
quadratic-potential (P2) observations in
`tests/sipi/reference_values/scikit_fem/three_signal_fem_shape.json` and
`four_signal_fem_shape.json`. Both records use `openphysics.reference-values/1`.
The reader is copied unchanged from the shared repository's
`625d9f74ca253538f172a42272c869b66d144eed` implementation, under Apache-2.0.
No reference library code or binaries are included in these records.

The product's P1 current, both interior extensions and all capacitance finite
differences still run for every case. Only the expensive independent P2 run is
replaced by its preserved observations. The original whole-boundary comparison
limit 0.01, C0 comparison limit 0.001, and reference self-check limit 1e-10 remain
unchanged. The five smaller plate/coax/closed-pair live reference cases remain.
Earlier coarse three-signal C0 and coarse/half-size four-signal PSD failures are
not removed, reclassified or used as accepted fixtures.

Before creating the records, a separate compare-only run reproduced every P2
array and self-check value exactly from the successful observations. The
three-signal reference took 16.54 seconds and the four-signal reference 157.15
seconds in that Linux run; these are observations, not runtime guarantees.
The four-signal comparison exceeds the live-reference cost limit. Historical
reference cost is stored separately from the current test's execution. A test
using a stored record explicitly reports that the reference tool did not run.

The P1/P2 potential orders differ. The P2 field is assembled and solved by
scikit-fem 12.0.2 (BSD-3-Clause), with independent charge/energy and quadrature
checks. Prescribed velocities and mesh inputs come from the product contract;
this is not an independent test of velocity construction. Geometry and mesh
recipes are explicit, while stored mesh hashes identify the historical arrays.
A different platform can remesh differently. The retained comparison criteria
do not establish absolute accuracy, weak mutual-term accuracy, outer convergence
or empirical validation.

Records contain input geometry, ordered boundary interpretation, exact tool and
numerical-library versions, provenance, costs, values and content hashes.
Installation locks and archives not retained with the original environment are
marked unknown with reasons. `provenance_status` is `reconstructed`; it must not
be described as complete distribution reproducibility. Values are finite, small,
read-only after loading, and covered by the recorded tool. The consumer rejects
corrupt values, inputs, hashes, duplicate keys, nonfinite values and missing
unknown-field explanations.

Manual replay uses the existing pinned shared dependencies and the stated test
versions. From the repository checkout, with its source available on PYTHONPATH:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python tests/sipi/reference_values/scikit_fem/compare_multisignal.py --signals 3
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python tests/sipi/reference_values/scikit_fem/compare_multisignal.py --signals 4
```

On Windows, set these environment variables using the current shell before
running the same Python script. The replay is manual and can require substantial
memory/time. Its default and only mode compares every P2 output byte for byte;
it exits nonzero on differences and never rewrites a baseline. A different
platform/runtime may legitimately produce differences, which require review.
This replay does not rerun product capacitance finite differences. The normal
product tests still perform those checks separately. The original private
comparison driver and the portable replay script have distinct recorded hashes.
No new Windows/macOS or release support is established by these Linux records.

[한국어](../../locales/ko/pages/packages/sipi/fem_shape_references.md)
