# FEM quantity samples with explicit corner resolution

`CornerFEMShapeLineQuantityStudyDocument` saves exactly `schema`, `study` and
`corner_size` under `sipi.corner-fem-shape-line-quantity-study/1`. The nested
[original FEM study](fem_shape_study.md) retains its source geometry/material
sampling, quantity, metals and positive frequency. The corner target in metres
must be finite, positive and no greater than the nominal resolved edge size.
Normalization performs no field solves.

```python
from sipi.study import ImpedanceStudyDocument
from sipi import (FEMShapeLineQuantityStudyDocument,
                  CornerFEMShapeLineQuantityStudyDocument)
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
saved = CornerFEMShapeLineQuantityStudyDocument(study, corner_size=2.5e-6)
assert normalize_saved(saved.dumps()) == saved.dumps()
# result = saved.analyze(max_evaluations=2)
```

Every attempted sample creates an explicit [corner FEM line](corner_fem_line.md)
with the same corner target, zero length and 50-ohm port reference. Geometry and
material values are reevaluated per row. No one mesh is reused across different
geometry samples. The original current, skin-depth and diagnostic checks still
apply. The target is validated again for each row's input.

Supported quantities retain their original meanings: scalar real impedance
and attenuation, or paired real differential/common forward impedance for the
stated Ic=0/Id=0 launch. These paired quantities are not independent propagation
modes. The host budget counts line attempts; each line contains multiple internal
field solves. All requested rows are counted before fields begin.

Samples retain order, duplicates, input snapshots, material evaluations and
complete or partial current evidence. A failed row does not prevent later rows
from being attempted. Descriptive summaries require every row to succeed;
there is no clipping, resampling, weighting or production-yield interpretation.
The common saved executor, request, record and project retain this contract.
Reopening records does not solve again; changing the corner control invalidates
the current result link while preserving historical records.

Validation compares original cases and actual equal-corner fields, explicit
smaller-corner scalar/paired samples, independent characteristic quantities,
material attenuation and saved failures. These finite observations do not
certify every sample's mesh/outer convergence, weak mutual loss accuracy,
continuous parameter ranges or new platforms. Existing study schemas continue
to reject a corner key inside their source mesh.

[한국어](../../locales/ko/pages/packages/sipi/corner_fem_study.md)
