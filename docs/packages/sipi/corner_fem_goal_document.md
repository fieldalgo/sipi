# Saved FEM line goals with explicit corner resolution

`CornerFEMShapeLineQuantityDesignDocument` retains exactly `schema`, `design`
and `corner_size` under `sipi.corner-fem-shape-line-quantity-design/1`.
The nested [FEM goal](fem_shape_goal_document.md) retains one positive-bounded
sweep variable with count=2, quantity, target, tolerance and evaluation budget.
The separate corner target is in metres, finite, positive and no larger than
the nominal resolved edge size. Normalization performs no field solves.

```python
from sipi.study import ImpedanceStudyDocument
from sipi import (FEMShapeLineQuantityStudyDocument,
                  FEMShapeLineQuantityDesignDocument,
                  CornerFEMShapeLineQuantityDesignDocument)
from sipi.execution import normalize_saved

source = ImpedanceStudyDocument('stripline',
    dict(width=.0004, plane_spacing=.002, eps_r=4.,
         thickness=.00005, box_width=.008),
    quantity='z0', frequency=2e9, materials={},
    mesh=dict(edge_size=5e-6, far_size=.0002, grade=.1),
    sampling=dict(kind='sweep', count=2,
        variables=[dict(name='width', lower=.00039, upper=.00041)]))
metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness=dict(kind='smooth'))
study = FEMShapeLineQuantityStudyDocument(source,
    conductors=dict(signal=metal), reference=metal,
    ground_thickness=35e-6, quantity='impedance_real')
design = FEMShapeLineQuantityDesignDocument(study,
    target=70.35, tolerance=.2, max_evaluations=12)
saved = CornerFEMShapeLineQuantityDesignDocument(design, corner_size=2.5e-6)
assert normalize_saved(saved.dumps()) == saved.dumps()
# result = saved.solve()
```

The factory reevaluates the original geometry or dielectric numeric-leaf
transformation at each parameter. Fixed pitch/height and boundary metals retain
their original meanings. Source study samples are not analyzed first. Each
factory input is an explicit corner FEM line at zero length and one frequency.

The [direct corner goal](corner_fem_goal.md) reserves a refinement attempt,
freezes the selected physical input and halves edge, far, grade and corner
controls. The original absolute target gate and 0.005 relative mesh-change
gate both apply. Scalar real impedance/attenuation and paired real differential
or common forward impedance retain their original launch conventions. A bounded
search is neither global optimization nor a general accuracy certificate.

The common executor checks the nested goal budget before any solve. Requests,
records and projects retain selected/refined inputs, search history and partial
current evidence on typed failures. Reopening a record performs no solve;
changing the corner control invalidates the current-result link while preserving
historical records. The host budget counts line attempts, each of which contains
multiple internal field solves. Diagnostic requests on a goal are rejected.

Validation checks strict parsing, material and fixed-pitch factories, preflight
budgets, original saved contracts, and actual scalar/paired saved goals against
the direct corner API. Source and installed artifacts are compared separately.
This connection does not certify all geometries, weak mutual loss convergence,
new platforms or a packaged application. Existing schemas still reject an
implicit corner key.

[한국어](../../locales/ko/pages/packages/sipi/corner_fem_goal_document.md)
