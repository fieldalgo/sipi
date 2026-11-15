# Saved one-variable two-ground line design

[한국어](../../locales/ko/pages/packages/sipi/two_ground_line_goal_document.md)

`TwoGroundLineQuantityDesignDocument` stores
`sipi.two-ground-line-quantity-design/1`: a nested
[line-quantity study](two_ground_line_study.md), target, absolute tolerance and
maximum attempts. It binds a reproducible factory for the
[bounded direct goal](two_ground_line_goal.md), without serializing callables.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_line_study import TwoGroundLineQuantityStudyDocument
source = ImpedanceStudyDocument('offset_stripline',
    dict(width=.0006, plane_spacing=.002, trace_height=.0007, eps_r=4.,
         thickness=.00005, tan_delta=.003, box_width=.008),
    quantity='z0', frequency=2e9, materials={},
    sampling=dict(kind='sweep', count=2, variables=[
        dict(name='width', lower=.00055, upper=.00065)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
study = TwoGroundLineQuantityStudyDocument(source, quantity='impedance_real',
    conductors=dict(signal=metal),
    reference=dict(kind='surfaces', bottom=metal, top=dict(metal, conductivity=21e6), sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=64, ground_modes=128, interpolation_degree=12)
assert TwoGroundLineQuantityStudyDocument.loads(study.dumps()).dumps() == study.dumps()
assert len(study.samples()) == 2

from sipi.two_ground_line_goal_document import TwoGroundLineQuantityDesignDocument
design = TwoGroundLineQuantityDesignDocument(study, target=58., tolerance=.05,
                                            max_evaluations=40)
assert TwoGroundLineQuantityDesignDocument.loads(design.dumps()).dumps() == design.dumps()
```

Construction and normalization do not solve fields. The nested source must be a
sweep with count2 and one positive, nondegenerate interval. Count2 describes
the bounds; the source samples are not run before the goal. Study/3 or /4 retains
geometry/material bindings, fixed pitch and plane-spacing transformations.
The selected quantity fixes scalar/paired signal admission and target units:
ohms for real characteristic impedances, Np/m for attenuation. Target must be
positive except that zero attenuation is allowed; absolute tolerance is positive.

Preflight checks the nominal input, both endpoints and midpoint, including
volume-only, panel-only and joint refinement inputs. This does not prove the
interior feasible or a target achievable. Parsing refuses missing/extra,
duplicate and nonfinite fields. Stored values are detached snapshots.

`design.solve()` and `execute_saved(design.dumps(), max_evaluations=40)` use
the same direct algorithm. The host budget must cover the saved5..10000 attempt
budget before fields. Three evaluations remain reserved for refinements; every
failed attempt counts. Original absolute targets and all0.005 relative gates
remain unchanged. Selection and refinements retain exact frozen inputs, current
and dielectric-mesh records, history and quantities. No hidden pre-search study,
factory fallback or automatic retry is introduced.

A failed execution retains the direct goal error, typed partial line cause,
attempt count and completed fields. Interrupts propagate. Requests, records
and projects normalize, bind and reopen input/results without recomputation.
The existing CLI validation/run path uses the same registry. Browser rendering,
Worker qualification and Windows packaging remain separate tasks.

The registered saved58Ω case uses the direct case's exact offset geometry,
material/metal, bounds, frequency, panel/mesh settings and40-attempt budget.
Its selected and all three refined inputs/results are compared to the direct
case, in addition to source/installed receipt identity. Such agreement checks
serialization/execution consistency, not new independent physical accuracy.
Outer-domain adequacy, measured accuracy and production yield remain separate.
