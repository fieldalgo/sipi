# Sampled-band line-length boundary

[한국어](../../locales/ko/pages/packages/sipi/length_design.md) · [Band limits](band.md)

[Version 2](extracted_length.md) also accepts saved field sources, extracting once before length search.

`LineLengthDesignDocument` varies only length in a supplied uniform RLGC model.
It finds a feasible/infeasible boundary for several sampled insertion, reflection
or crosstalk constraints together. It does **not** claim a global maximum length:
mismatched lines may have disconnected feasible intervals or nonmonotonic responses.

```python
import numpy as np
from sipi.length_design import LineLengthDesignDocument

network = dict(kind='rlgc', frequency_hz=[0, 1e8, 2e8],
    R=[[15]], L=[[2.5e-7]], G=[[.006]], C=[[1e-10]],
    length_m=0, reference_ohms=50, names=['s'])
plan = LineLengthDesignDocument(network, bounds=[0, 2], tolerance=1e-7,
    limits=[dict(name='insertion', input_port='near:s', output_port='far:s',
                 frequency_hz=[0, 2e8], minimum=.8, maximum=None)])
result = LineLengthDesignDocument.loads(plan.dumps()).solve()
assert result.feasible.passed and not result.infeasible.passed
assert result.infeasible_length_m-result.feasible_length_m <= 1e-7
assert abs(result.feasible_length_m-(-np.log(.8)/.3)) <= 1e-7+1e-10
```

The strict `sipi.line-length-design/1` object contains exactly `schema`, `network`,
`limits`, `basis`, `bounds_m`, `tolerance_m`, `max_evaluations`. The source must be
an explicit `rlgc` object with **length_m=0**. This baseline is only for validating
the given per-unit-length coefficients; the two design bounds supply trial lengths.
Existing real symmetric/passive RLGC requirements remain. Coefficients may vary
at the explicitly supplied frequencies, but are not interpolated or fitted.
Geometry-backed RLGC can be supplied explicitly after a separately validated field
extraction; this document does not re-extract or refine its field mesh.

Bounds are finite, nonnegative and strictly increasing; tolerance is a positive
length in metres. `basis` and the 1–64 constraints follow [band limits](band.md),
including exact sampled endpoints, named input/output ports and optional explicit
mixed-mode conversion. The lower length must meet **all** constraints and the
upper must violate at least one. Both endpoints are evaluated even when one will
reject the bracket. If both pass, the API rejects rather than searching past the
user's upper bound. If lower fails, it does not skip to an arbitrary feasible island.

Bisection retains the feasible lower and infeasible upper side. It stops when
upper-lower <= tolerance_m. The returned feasible side satisfies the sampled
constraints; the infeasible side documents a nearby violation. This locates one
boundary in the bracket, not a proof of the unique or largest feasible length.
It supplies no bound on response between frequency samples and no uncertainty,
yield, manufacturing margin, causality or material-validity certification.

The explicit evaluation budget (2–10000) includes both endpoints and every
midpoint; there is no uncounted final evaluation. Initial source normalization
may perform the existing zero-length network algebra. A small initial bracket can
succeed with just two evaluations. Budget exhaustion, inability to represent a new
midpoint or a numerical evaluation failure raises `LengthGoalError`; no partial
candidate is reported as an accepted design. Completed history is retained, and
numerical failures additionally preserve `failed_length_m` and `cause_type`.
Interrupts are not converted into completed results.

The result retains both length bounds, both full band assessments, evaluation
history and canonical input JSON. `to_dict()` exports finite quantities with scope
`sampled-band-bracket-boundary`. Shared execution exports the same result, or
`status='failed'` with retained error/history, and checks its caller's budget before
the search. Existing app engine pins remain independent of this new contract.

Tests use frequency-dependent matched distortionless RLGC, where the active
insertion constraint has analytical boundary -log(minimum)/alpha. They check the
specified 1e-7 m bracket, exponential magnitudes within relative 1e-10, and both
endpoint networks against independent scikit-rf 2.2.0 within absolute 1e-10.
They also cover joint bands, mixed-mode references, budgets, invalid brackets,
exact replay and preserved numerical failures. This adds no field solver; mesh,
outer boundary and model accuracy remain the source extraction's responsibility.

```sh
python -m pytest -q tests/sipi/test_length_design.py tests/sipi/test_band.py tests/sipi/test_execution.py::test_registry_all_versions_normalize_without_field_solve
```
