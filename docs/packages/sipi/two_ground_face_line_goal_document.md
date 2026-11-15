# Saved one-variable design with physical-face metals

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_line_goal_document.md)

`TwoGroundFaceLineQuantityDesignDocument` stores
`sipi.two-ground-face-line-quantity-design/1`: a nested
[face quantity study](two_ground_face_line_study.md), target, absolute tolerance
and maximum attempts. It binds a reproducible factory for the
[direct face goal](two_ground_face_line_goal.md), without serializing callables.
The whole-boundary input, execution path and numerical criteria remain unchanged.

The following example prepares and normalizes input without field work:

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_face_line_study import TwoGroundFaceLineQuantityStudyDocument
source = ImpedanceStudyDocument('offset_stripline',
    dict(width=.0006, plane_spacing=.002, trace_height=.0007, eps_r=4.,
         thickness=.00005, tan_delta=.003, box_width=.008),
    quantity='z0', frequency=2e9, materials={},
    sampling=dict(kind='sweep', count=2, variables=[
        dict(name='width', lower=.00055, upper=.00065)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
study = TwoGroundFaceLineQuantityStudyDocument(source, quantity='impedance_real',
    conductors=dict(signal=dict(zip(('bottom','top','left','right'),
        [dict(metal,conductivity=sigma) for sigma in (58e6,35e6,21e6,45e6)]))),
    reference=dict(kind='surfaces', bottom=metal, top=dict(metal, conductivity=21e6), sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=128, ground_modes=128, interpolation_degree=16)
assert TwoGroundFaceLineQuantityStudyDocument.loads(study.dumps()).dumps() == study.dumps()
assert len(study.samples()) == 2

from sipi.two_ground_face_line_goal_document import TwoGroundFaceLineQuantityDesignDocument
design = TwoGroundFaceLineQuantityDesignDocument(study, target=58., tolerance=.05,
                                            max_evaluations=40)
assert TwoGroundFaceLineQuantityDesignDocument.loads(design.dumps()).dumps() == design.dumps()
```

The strict root keys are schema, study, target, tolerance and max_evaluations.
The nested face study must supply a sweep with count=2 and one positive,
nondegenerate interval. Count=2 defines the bounds, without running those
samples before searching. Study/3 or /4 retains geometry/material bindings,
fixed pitch and plane-spacing transformations. The quantity fixes scalar/paired
admission and units: ohms for real characteristic impedance, Np/m for attenuation.
Only attenuation admits a zero target; absolute tolerance must be positive.

Preflight checks nominal, both endpoints and midpoint, including their volume,
panel and joint refinement inputs. This does not prove interior feasibility or
target reachability. Parsing rejects missing/extra, duplicate and nonfinite
fields. Whole-boundary study objects are refused. Values are detached snapshots.

`design.solve()` and `execute_saved(design.dumps(), max_evaluations=40)` use the
same direct algorithm. The host budget must cover the saved 5..10000 attempt
budget before fields. Three evaluations remain reserved for refinements; every
failed attempt counts. Original absolute targets and all 0.005 relative gates
remain. Frozen inputs retain physical faces, coatings, roughness, reference
metals and dielectric bindings. No hidden preliminary study, fallback or retry
is introduced. Failures retain typed causes, history and available current/mesh
observations; interrupts propagate.

Requests, records and projects bind and reopen inputs/results without another
solve. The existing CLI validates and runs this schema, preserving input bytes
and writing result receipts. Browser UI, Worker parity and executable packaging
are separate qualifications.

The physical saved case uses the direct case's offset geometry at 2 GHz,
58 ohms ±0.05, width 0.55–0.65 mm, 128→256 panels and 40 attempts. Each actual
field result is checked against complex sqrt(Z/Y) and sqrt(ZY) at 1e-12; the
saved result is compared with the earlier direct result and exact installed
receipt. A separate CLI case uses the recorded selected width 0.000590625 m as
the lower bound, upper bound 0.00065 m and five attempts (two endpoints and three
refinements). This does not replace the complete saved-search test. Other checks
cover all four quantities, strict nesting, admission, materials, fixed pitch,
failed stages, budgets, interrupts and project restoration. These checks do not
establish measured accuracy, production yield or arbitrary outer-domain adequacy.
