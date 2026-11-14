# Geometry and dielectric studies with fixed metal coatings

Explicit `sipi.line-quantity-study/4` uses transmission-line/7 for every sample.
It accepts the same scalar real impedance/attenuation and paired forward
differential/common real impedance quantities as study/3, with the additional
ability to retain [layered surface metals](layered_metal.md).

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.line_yield import LineQuantityYieldDocument
from sipi.execution import normalize_saved

source = ImpedanceStudyDocument('stripline',
    dict(width=.5e-3, plane_spacing=1e-3, thickness=50e-6, eps_r=4., box_width=4e-3),
    quantity='z0', frequency=1e9, materials={},
    sampling=dict(kind='uniform', count=4, seed=123,
        variables=[dict(name='width', lower=.45e-3, upper=.55e-3)]))
metal = dict(kind='layered', conductivity=58e6, relative_permeability=1.,
    coatings=[dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.)])
study = LineQuantityStudyDocument(source, quantity='impedance_real',
    conductor=dict(kind='surface-boundaries', conductors={'signal': metal},
                   reference=metal, ground_thickness=35e-6),
    schema='sipi.line-quantity-study/4')
assessment = LineQuantityYieldDocument(study, minimum=40., maximum=60.,
    confidence=.95, schema='sipi.line-quantity-yield/3')
assert normalize_saved(assessment.dumps()) == assessment.dumps()
```

The source varies geometry and dielectric parameters. **Metal coating thickness,
conductivity and permeability remain fixed across samples.** There is no inferred
metal distribution or simultaneous coating fit. Each row retains its original
sample vector, generated geometry/material inputs, explicit line/7 input when
construction succeeds, result or failed phase/error. A sample whose available
core violates the skin-depth condition remains a failed input row. Subsequent
rows are still attempted; failures are not clipped, resampled or dropped, and
an incomplete study has no partial numerical summary.

Explicit yield/3 admits study/4. It requires iid uniform or normal samples;
correlation between variables within a normal row is allowed. Unresolved rows
remain in the denominator and in the existing Clopper–Pearson envelope. This
interval addresses sampling under the stated distribution, not production yield
or uncertainty in field discretization, material fitting or the model itself.
The per-run budget is checked before any field solve.

Versions study/1..3 continue generating line/6. Yield/1 still admits study/1..2,
and yield/2 still admits study/1..3. Existing yield-design candidate selection
versions also retain their earlier study contracts; reading a new study does
not silently extend an old consumer. Saved quantity goals retain their earlier conductor format in versions 1..3;
[explicit goal/4](layered_goal.md) connects fixed coatings.

Validation replays sampled RLGC through direct line/7 calls. Scalar quantities
are compared with an independent 2x2 matrix exponential; paired forward launches
use the growing eigenspace of a 4x4 transfer, retaining actual mesh asymmetry.
Tests also retain correlated vectors, real core failures, independent finite
binomial interval bounds and unchanged legacy values. These composition checks
do not replace the local coating model's field/mesh/outer validity checks.

[한국어](../../locales/ko/pages/packages/sipi/layered_study.md)

[Explicit yield-design/4](layered_selection.md) compares a fixed set of coated candidates with simultaneous yield bounds.
