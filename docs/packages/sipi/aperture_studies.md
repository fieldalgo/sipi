# Local capacitance studies and bounded design

`ApertureStudyDocument` and `ApertureDesignDocument` reuse the saved
[`ApertureSectionDocument`](elliptical_aperture.md) geometry, mesh and homogeneous
dielectric. They select a **real capacitance per length in F/m**. They do not
infer impedance, total pad capacitance, 3D transition behavior or manufacturing
yield. The existing impedance-study and design schemas remain unchanged.

```python
from sipi import (RoundConductor, EllipticalAperture, ApertureSectionDocument,
                  ApertureStudyDocument, ApertureDesignDocument)

section = ApertureSectionDocument(EllipticalAperture(
    width=0.8e-3, height=0.8e-3,
    conductors=[RoundConductor("signal", diameter=0.28e-3)], eps_r=3.96,
), mesh={"size": 20e-6, "angular_divisions": 128})
study = ApertureStudyDocument(section, sampling={
    "kind": "sweep", "count": 3,
    "variables": [{"name": "eps_r", "lower": 3.0, "upper": 5.0}],
})
result = ApertureStudyDocument.loads(study.dumps()).analyze()
print(result.failed, dict(result.summary))

goal = ApertureDesignDocument(section, variable="conductor_0_diameter",
    bounds=[0.20e-3, 0.35e-3], target=200e-12, tolerance=0.5e-12)
design = ApertureDesignDocument.loads(goal.dumps()).solve()
print(design.parameter, design.residual, design.refined_residual)
```

## Variables and quantities

Variables are `width`, `height`, `eps_r`, `tan_delta` and
`conductor_0_diameter`, `conductor_0_x`, `conductor_0_y` (also index 1 for a
pair). Indices follow saved conductor order, independent of conductor names.
Lengths are metres; offsets may be negative. Real C is independent of loss
tangent in this uniform-material electrostatic model; a loss-tangent sweep does
not predict a real-C distribution or loss target.

For the real Maxwell matrix C, quantities are:

| Name | Definition |
|---|---|
| `c11` (default) | C11 |
| `c22` | C22 |
| `mutual` | −C12 |
| `differential` | (C11+C22−2C12)/4 |
| `common` | C11+C22+2C12 |

One-conductor inputs support only `c11`. Differential/common values use the
power-dual voltage/charge convention of the section document, retaining unequal
self terms. They are not per-conductor odd/even capacitances or propagation modes.

## Saved sampling and failures

Strict `sipi.aperture-study/1` contains `schema`, `section`, `quantity` and
`sampling`. The shared [sampling contract](study.md) supports sweep, corners,
seeded uniform and correlated normal distributions, with 1–8 variables and
2–10000 samples. Sweep uses one variable; corners use all 2^n endpoints.
Normal uses the same PCG64 generator and symmetric covariance square root as
impedance studies, including positive-semidefinite singular correlations.
Unknown/missing fields, duplicate keys, booleans in numeric fields, nonfinite
values and unsupported versions are rejected. Saved inputs contain no results.

Bounded input corners are checked before calculation. This does **not** prove
that all intermediate geometries are valid: a conductor can cross another one
between valid endpoint positions. Every actual row is checked. Invalid normal
or interior samples retain their parameters, error type and message; they are
neither discarded nor resampled. `document` is absent if input construction
failed. Results and parameter snapshots are read-only through their public API.

`analyze(max_evaluations=128)` checks its budget before any field solve. Each row
remeshes with the saved nominal size and angular settings. No per-row convergence
certificate is implied. Only an entirely successful study has a summary:
minimum, maximum, mean, sample standard deviation (n−1 denominator), and linearly
interpolated 5th/95th percentiles, all in F/m. Corners and sweeps are not random
manufacturing populations. Failed studies have `summary=None`.

## Bounded goal and verification

Strict `sipi.aperture-design/1` stores `section`, `variable`, ordered `bounds`,
`quantity`, `target_f_per_m`, `tolerance_f_per_m` and `max_evaluations`, plus
`schema`. The target and absolute tolerance are positive; the budget is 3–10000.
Bisection requires bracketed endpoint values unless an endpoint meets the
tolerance. It assumes a continuous feasible interval; geometric feasibility
between endpoints and uniqueness are not guaranteed. Failures stop the search.

One evaluation is reserved for final refinement: halve the saved field size and
double angular divisions. **Both** requested and refined residuals must meet the
same target tolerance. `CapacitanceGoalError` retains completed history and the
failed parameter when available, including refinement misses. Success returns
the requested-mesh document, both capacitances, both residuals, history and saved
input JSON. Refinement agreement is not a universal physical accuracy bound.

## Validation

Analytic circular capacitance verifies the dielectric sweep and an independent
200 pF/m diameter solution: requested/refined residuals below 0.5 pF/m and diameter
within 0.5% of the analytic value. A paired ellipse targets differential C of
130 pF/m with both residuals below 1 pF/m. Tests also cover negative-offset goals,
explicit voltage/charge energy for all pair quantities, independent statistical
moments/covariance/distribution checks, preserved invalid samples and a real
coarse-mesh case that fails the final refinement. Existing impedance-study JSON
and deterministic samples are preserved byte for byte in migration checks.

[한국어](../../locales/ko/pages/packages/sipi/aperture_studies.md)
