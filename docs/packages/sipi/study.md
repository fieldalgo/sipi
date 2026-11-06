# Impedance tolerance studies

**English** | [한국어](https://github.com/fieldalgo/sipi/blob/main/docs/locales/ko/pages/packages/sipi/study.md)

[Overview](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/overview.md) · [Impedance design](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/design.md)

`sipi.study.ImpedanceStudyDocument` samples named template parameters and evaluates
single-line or symmetric differential impedance. It supports explicit sweeps,
corners, independent uniform sampling and correlated normal sampling. Every
sample and failure remains in the result; failed rows are never resampled or
removed to produce a more favourable summary.

```python
from sipi.study import ImpedanceStudyDocument

plan = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.4e-3, gap=.3e-3, substrate_height=.5e-3, eps_r=4,
         thickness=0, air_height=1e-3, box_width=4e-3),
    sampling=dict(kind='sweep', count=3,
                  variables=[dict(name='width', lower=.35e-3, upper=.45e-3)]),
    quantity='z_diff', fixed_pitch_m=.7e-3,
    mesh=dict(edge_size=.1e-3, far_size=.4e-3, grade=.3))
restored = ImpedanceStudyDocument.loads(plan.dumps())
result = restored.analyze()
# Each row preserves width, derived gap, saved cross-section, Zdiff or its error.
```

## Saved plan and sampling contract

The strict `sipi.impedance-study/1` object has exactly `schema`, `template`,
`parameters`, `sampling`, `quantity`, `mesh`, `fixed_pitch_m`. Use `from_dict`,
`loads`, `to_dict`, `dumps` to validate, copy and save it. Unknown/missing fields,
duplicate JSON keys, NaN/Infinity, boolean numbers and invalid geometry are rejected.
Version `sipi.impedance-study/2` has the same fields plus required
`fixed_plane_spacing_m` (null or a positive length). Existing constructors without
that constraint still emit v1, and v1 rejects the new field. A loaded v2 document
retains v2 even when its constraint is null. Unknown versions are rejected.
The sixteen templates are `microstrip`, `stripline`, `coupled_microstrip`,
`grounded_coplanar`, `coated_microstrip`, `offset_stripline`, `coupled_stripline`,
`broadside_stripline`, `coupled_grounded_coplanar`, `layered_stripline`,
`coupled_layered_stripline`, `coupled_coated_microstrip`,
`coated_grounded_coplanar`, `coupled_coated_grounded_coplanar`,
`unbacked_coplanar` and `coupled_unbacked_coplanar`. Parameters follow their SI contracts;
all template defaults and the nominal resolved mesh settings are saved. A saved
`None` for an automatic template dimension retains its existing template rule,
which can change the generated box size when another dimension changes. Supply
explicit air/box dimensions when those must remain fixed.

`quantity` is `z_diff` for `coupled_microstrip`, `coupled_stripline`,
`broadside_stripline`, `coupled_grounded_coplanar`, `coupled_layered_stripline`,
`coupled_coated_microstrip`, `coupled_coated_grounded_coplanar` and
`coupled_unbacked_coplanar`, otherwise `z0`.
This extends the supported template names
without changing schema fields or existing plan semantics. Older readers reject
the newly supported names; save the SIPI version alongside the input. Sampling uses
1–8 distinct template parameter names, in the listed order:

| `sampling.kind` | Required fields beyond `kind` | Variable fields |
|---|---|---|
| `sweep` | `variables`, `count` | `name`, `lower`, `upper`; exactly one variable |
| `corners` | `variables` | `name`, `lower`, `upper`; all 2^D corners |
| `uniform` | `variables`, `count`, `seed` | `name`, `lower`, `upper`; independent uniforms |
| `normal` | `variables`, `count`, `seed`, `correlation` | `name`, `mean`, `std`; std > 0 |

Bounds are finite and strictly increasing; all bounded-domain corner geometries
are validated before meshing. Count is an integer 2–10000; seed is an integer
0–2^32-1. Random sampling uses NumPy `Generator(PCG64(seed))`. Normal samples are
**unbounded**, with no clipping, rejection sampling or truncation. A mean or
sample that produces an invalid physical input remains an error during analysis.

The normal correlation matrix is D×D, finite, symmetric, unit diagonal and positive
semidefinite. Symmetry, unit-diagonal, entry-range and negative-eigenvalue roundoff
allow 1e-12 absolute tolerance; asymmetric roundoff is averaged. Accepted negative
eigenvalues in [-1e-12,0] are set to zero only for the symmetric square root.
Larger negative eigenvalues are rejected. Perfect correlation/anticorrelation is
supported. Samples are `mean + (standard_normal @ sqrt(correlation).T) * std`.
Requested correlations describe the distribution, not the exact finite sample's
empirical correlation. Record the engine and NumPy versions with results; a seed
alone is not a cross-version bitwise guarantee.

`samples()` returns a copied read-only `(count, D)` array of independent variable
values in listed order. `sample_parameters()` returns fresh full template argument
maps, including derived parameters. No FEM solve runs in either method.

## Fixed pitch

`fixed_pitch_m` is `None`, or a positive centre-to-centre pitch for
`coupled_microstrip`, `coupled_stripline`, `coupled_grounded_coplanar`,
`coupled_layered_stripline`, `coupled_coated_microstrip`,
`coupled_coated_grounded_coplanar` or `coupled_unbacked_coplanar`.
Fixed pitch requires `width` among the independent variables
and forbids independent `gap` sampling. Nominal width+gap must equal pitch within
relative 1e-12. Every row derives `gap = pitch - width`, keeping both trace centres
fixed. The gap follows the bottom widths used by the existing tapered template.
Bounded corners with nonpositive gap are rejected at construction. Normal samples
that cross zero gap are retained as invalid rows. This is a deterministic geometric
constraint, not an additional statistical correlation parameter.

For `coupled_grounded_coplanar` and its coated/unbacked variants, this fixes the **signal** centres only. The
outer grounds move with the signal edges to preserve each row's `ground_gap`;
they are not fixed in position. See [coplanar dimensions](coupled_coplanar.md).

In `broadside_stripline`, `gap` is the vertical metal-to-metal separation and
`offset` is the signed horizontal displacement. Sample either directly;
`fixed_pitch_m` is rejected for this template. Its positive conductor thickness
and all ground-clearance requirements remain enforced by the template.

The [layered stripline templates](layered_stripline.md) keep lower/upper dielectric
properties and heights separate. Sampling one permittivity does not change the
other. `upper_height` includes the metal thickness; bounded corners must retain
positive clearance above the copper. Invalid normal samples remain failed rows.

## Fixed total plane spacing (v2)

`fixed_plane_spacing_m` supports `layered_stripline` and
`coupled_layered_stripline`. Sample exactly one of `lower_height` and
`upper_height`; the other is derived as total spacing minus the sampled height.
The nominal heights must sum to the specified spacing within relative 1e-12.
Sampling both heights, neither height, or using this constraint on another
template is rejected. A null value disables the constraint.

```python
plan = ImpedanceStudyDocument('layered_stripline',
    dict(width=.5e-3, lower_height=.4e-3, upper_height=.6e-3,
         lower_eps_r=2, upper_eps_r=6, thickness=.035e-3),
    quantity='z0', fixed_plane_spacing_m=1e-3,
    sampling=dict(kind='sweep', count=3,
                  variables=[dict(name='lower_height', lower=.3e-3, upper=.7e-3)]))
saved = plan.dumps()  # sipi.impedance-study/2
```

The upper height includes copper, so it must remain greater than `thickness`.
Every bounded corner is validated after deriving the other height. Invalid
normal samples, including negative derived heights, remain failed rows with both
the sampled and derived values. This is a deterministic geometric constraint,
not an extra independent variable in the correlation matrix. It can combine
with fixed horizontal pitch when width is also sampled in a layered pair.
`samples()` returns independent variables only; `sample_parameters()` and result
rows retain the full derived geometry.

## Evaluation, failures and summaries

`analyze(max_evaluations=128)` checks an explicit integer budget 2–10000 before any
solve. A larger sample plan raises `ValueError`; it is never silently shortened.
Every row then builds its own geometry mesh using the saved nominal settings.
`ImpedanceStudy` holds `input_json`, `quantity`, immutable `rows`, `failed`, and
`summary`. Each `StudyRow` holds index, a read-only parameter map, saved
`CrossSectionDocument` when construction succeeded, impedance in ohms or `None`,
and `error_type`/`error`. Solver errors retain the valid input document; invalid
geometry has no document. Interrupts are not converted into successful rows.

Any failed row makes `summary=None`. Otherwise the read-only summary holds sample
minimum, maximum, mean, sample standard deviation (`ddof=1`) and 5th/95th percentiles
(NumPy linear interpolation). Sweep/corner statistics are descriptive samples,
not probability distributions. Sample extrema/quantiles are **not guaranteed
manufacturing limits**, yield predictions or continuous-domain worst cases.

There is no automatic mesh-refinement check per row. Converge mesh/domain settings
for each relevant geometry before using small impedance differences. Samples do
not add conductor loss, frequency networks, nonlinear materials or full-wave
physics to the underlying quasistatic cross-section model. Results do not contain
a new persistent-result schema; the JSON contract saves inputs. UI/CLI linkage is
separate from this Python API.

## Validation

```sh
OPENBLAS_NUM_THREADS=1 PYTHONPATH=src python -m pytest -q tests/sipi/test_study.py tests/sipi/test_stripline_studies.py
python examples/sipi/tolerance_study.py
```

Fixed criteria: exact sweep/corner endpoints and ordering; uniform bounds; seed
and JSON reproduction; fixed pitch relative 1e-12; perfect anticorrelation
normalized absolute difference 1e-12. For 10000 correlated normal draws, each
standardized sample mean must be within 6/sqrt(N) of zero and the maximum
absolute difference between normalized sample covariance and target correlation
must be <=0.08. Independently generated `scipy.stats.multivariate_normal` draws
meet the same analytical moment criteria; both sets have normal-CDF KS statistic
<0.03 in each marginal. These statistical checks do not validate material physics.

Actual two-point single-line and differential FEM studies match direct saved-input
analysis within relative 1e-10. This is composition/reproduction evidence, not an
independent accuracy claim. Tests also cover invalid normal geometries without
resampling, retained solver failures, execution budgets, malformed JSON and
invalid covariance/shape/seed inputs. Existing cross-section analytical references
and convergence limits still apply. [Executable example](https://github.com/fieldalgo/sipi/blob/main/examples/sipi/tolerance_study.py).

All three added stripline templates replay all four sampling modes through JSON.
For unchanged geometry in a homogeneous dielectric, changing relative permittivity
from 1 to 4 halves impedance; actual FEM studies must satisfy this analytical
scaling law within relative 1e-9. This checks material scaling and study composition,
not absolute geometry accuracy or mesh convergence.
