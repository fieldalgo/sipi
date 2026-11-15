# Saved impedance goals with explicit corner resolution

`CornerImpedanceDesignDocument` saves a bounded impedance design together with
its separate corner target. The strict `sipi.corner-impedance-design/1` JSON
contains exactly `schema`, `design` and `corner_size`. The nested design retains
its original version 1–4 contract, units, geometry or material variable,
quantity, tolerances and evaluation budget. The corner target is in metres;
it must be finite, positive and no larger than the resolved edge size.

```python
from sipi import ImpedanceDesignDocument, CornerImpedanceDesignDocument
from sipi.execution import normalize_saved

design = ImpedanceDesignDocument(
    'stripline', dict(width=.0006, plane_spacing=.002, eps_r=4.,
                     thickness=.0004, box_width=.008),
    variable='width', bounds=[.00055, .00065], target=44.3,
    tolerance=.1, search_tolerance=.025, max_evaluations=12,
    mesh=dict(edge_size=1e-5, far_size=.0002, grade=.15))
saved = CornerImpedanceDesignDocument(design, corner_size=2.5e-6)
assert normalize_saved(saved.dumps()) == saved.dumps()
# result = saved.solve()
```

Loading and normalizing validate inputs without a field solve. Accessors return
detached snapshots. Solving calls [the explicit corner goal](corner_goal.md):
it retains the selected input and halves edge, far, grade and corner controls
for the mandatory refinement check. Both requested and refined residuals must
meet their original tolerances. This is a bounded one-variable search.

The common saved executor, request, execution record and project accept this
schema. The host evaluation budget is checked before solving. A complete result
contains the selected corner-section document and refinement history. Failed
searches retain their typed history; a mesh-limit failure also retains the
failed input, stage, attempt count and original cause. Reopening a record does
not rerun a field. Editing the corner target invalidates the current result
while retaining historical records. Supply actual artifact hashes when saving
a run; an input document alone does not identify the numerical build.

Existing design and cross-section schemas continue to reject a corner key in
their mesh dictionaries. Use this explicit wrapper for a reproducible corner
goal. Actual width/material searches reproduce the direct API results exactly;
transport tests reuse those measured results explicitly. These checks do not
establish every geometry's convergence, outer-domain independence, conductor
loss accuracy or new platform support.

[한국어](../../locales/ko/pages/packages/sipi/corner_goal_document.md)
