# Saved checked FEM-current goals

`FEMShapeLineQuantityDesignDocument` saves a reproducible one-variable factory
for the [bounded FEM goal](fem_shape_goal.md). Its strict five keys are `schema`,
`study`, `target`, `tolerance` and `max_evaluations`; the schema is
`sipi.fem-shape-line-quantity-design/1`. The nested
`FEMShapeLineQuantityStudyDocument` supplies the quantity, geometry, fixed positive
frequency, dielectric models, fixed boundary metals and mesh controls.

```python
from sipi.study import ImpedanceStudyDocument
from sipi import FEMShapeLineQuantityStudyDocument, FEMShapeLineQuantityDesignDocument

source = ImpedanceStudyDocument(
    'stripline', dict(width=.0004, plane_spacing=.002, eps_r=4.,
                     thickness=.00005, box_width=.008),
    quantity='z0', frequency=2e9, materials={},
    mesh=dict(edge_size=5e-6, far_size=.0002, grade=.1),
    sampling=dict(kind='sweep', count=2,
                  variables=[dict(name='width', lower=.00039, upper=.00041)]))
metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness=dict(kind='smooth'))
study = FEMShapeLineQuantityStudyDocument(
    source, conductors={'signal': metal}, reference=metal,
    ground_thickness=35e-6, quantity='impedance_real')
goal = FEMShapeLineQuantityDesignDocument(study, target=70.35,
                                        tolerance=.2, max_evaluations=12)
assert FEMShapeLineQuantityDesignDocument.loads(goal.dumps()).dumps() == goal.dumps()
# design = goal.solve()
```

Require a sweep with count=2 and exactly one positive-bounded variable. These
bounds define the search, rather than two preliminary field calculations. No
source study is analyzed before the goal. Existing fixed-pitch/stack-height and
dielectric numeric-leaf transformations build each candidate. Metals remain
fixed; zero-length lines at a 50-ohm reference retain the source's scalar or
explicit differential/common launch interpretation. Normalization is field-free.

The target and tolerance have the selected quantity's units: ohm for Re Zc,
Re Zdd and Re Zcc, or Np/m for attenuation. A zero target is admitted only for
attenuation; all tolerances are positive. The attempt budget is an integer from
3 through 10000, including one reserved frozen-input mesh refinement. It counts
attempts rather than internal capacitance/velocity solves. A common execution
budget smaller than the saved budget rejects the request before solving.

The selected and refined result must both meet the same absolute target
tolerance, and the FEM relative mesh-change limit remains 0.005. Existing
current derivative, original gradient flux and metal admission gates are
unchanged. Bisection, its lack of uniqueness/global guarantees, and the separate
outer-domain/physical validity requirements are exactly those of the direct API.

Common saved execution returns the complete design, including both current
records. A typed goal failure produces `status: failed`, a null result and the
complete error dictionary: attempts, successful history, failed parameter/input,
stage, and any complete or partial current evidence. Execution records /1 and /2
and projects retain these receipts without rerunning calculations. Cancellation
propagates. This wrapper does not turn failures into partial accepted designs.

Validation uses actual scalar and differential saved width goals matched to the
direct API, independent characteristic square roots, field-free material/pitch
mapping and exact complete/failed record/project round trips. Transport-only tests
explicitly reuse already computed designs. It does not add physical inverse
validation for other quantities, new platform support, runtime guarantees or
empirical accuracy. Existing schemas and defaults remain unchanged.

[한국어](../../locales/ko/pages/packages/sipi/fem_shape_goal_document.md)
