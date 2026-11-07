# Separate reference-plane and ground-trace surface laws

[한국어](../../locales/ko/pages/packages/sipi/reference_surfaces.md) · [Signal faces](face_conductor.md)

`ReferenceSurfaceMetals` extends the Python face-loss API with separate bottom,
top, side-wall and named ground-trace metals. The older single `SurfaceMetal`
reference still combines all grounds and retains its output shape. Saved line/4
continues to accept that common reference only; this extension is a Python API.

```python
import numpy as np
from sipi import stripline
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import (TraceFaceMetals, ReferenceSurfaceMetals,
                                 surface_conductor_loss_by_face)

section = stripline(width=.5e-3, plane_spacing=1e-3, thickness=50e-6,
                   eps_r=4., box_width=4e-3)
smooth = SurfaceMetal(58e6)
reference = ReferenceSurfaceMetals(bottom=smooth,
    top=SurfaceMetal(58e6, roughness_rms=.5e-6), sides=None, conductors={})
result = surface_conductor_loss_by_face(section, [1e9, 4e9],
    conductors={'signal': TraceFaceMetals.uniform(smooth)}, reference=reference,
    ground_thickness=35e-6, edge_size=2.5e-6, far_size=.1e-3, grade=.05)
assert result.boundary_labels[-2:] == ('reference:bottom', 'reference:top')
np.testing.assert_allclose(result.factors.parts[4:].sum(axis=0),
                           result.factors.base.parts[-1], rtol=1e-12, atol=1e-12)
np.testing.assert_allclose(result.resistance_parts.sum(axis=1), result.R, rtol=1e-12)
```

All four constructor fields are explicit. A `bottom`, `top` or `sides` boundary
needs a `SurfaceMetal` exactly when the cross-section marks it as ground; an open
boundary requires `None`. Both side walls share the `sides` law. `conductors` maps
exactly every explicit ground-trace name to one law over its complete perimeter.
Signal assignments remain separate `TraceFaceMetals`. Unknown/missing names and
unused boundary assignments reject before meshing. The ground mapping is copied
and made read-only; changing the caller's mapping cannot change the assignment.
All ground groups remain the same PEC reference potential in the field model;
separate surface laws do not introduce independent return-conductor ports.

Signal skin-depth gates retain their existing minimum-dimension rule. Each active
plane/wall uses the minimum of `ground_thickness`, box width and box height;
each explicit ground trace uses its own minimum dimension. Every local skin depth
must be <= that dimension/5 before meshing. `ground_thickness` must remain positive
even for a section grounded only by traces, where it does not enter those trace
dimensions. These gates are necessary checks, not a model-accuracy guarantee.

One vacuum current solution is partitioned into four faces per signal followed by
the active references: bottom, top, sides, then ground traces in cross-section
order. Labels are `reference:bottom`, `reference:top`, `reference:sides` and
`reference:ground:<name>`. Every ground boundary edge must map to exactly one
nonempty group. Plane/wall endpoints use the section boundary tolerance; ground
trace endpoints use their geometry. Overlap or a missing group rejects.

For N signals and M reference groups, there are P=4N+M entries. Existing face-loss
arrays use P instead of 4N+1; `factors.reference_labels` records the M labels.
The common-reference API keeps M=1 and label `reference`. Summed reference Q and
integrated currents must agree with the original unsplit ground within 1e-12.
Original C0, external L and the 5% whole-conductor flux rejection are unchanged.
Resistance and internal L sum each local surface impedance times its Q matrix;
mutual terms and per-surface contributions are retained.

Tests independently assemble scikit-fem 12.0.2 fields for a pair with both planes,
side walls and two ground traces, then classify reference currents by midpoints.
The reference Q and integrated currents agree within 1e-10. Uniform laws reduce
to the existing common-reference result within 1e-12. Tests require PSD,
reciprocity, passive networks, every reference kind used alone, strict pre-mesh
rejection and preserved partition sums.

A wide centered stripline has Q approximately 1/(4w) on each signal horizontal
face and each reference plane. Different plane resistivities are checked against
this analytical power sum within 5%. A separate offset stripline requires both
mesh refinement and doubled-box resistance changes below 5%. These are explicit
fixture criteria, not universal bounds for arbitrary cross-sections.

This remains first-order PEC surface perturbation. Different laws do not imply a
physically realizable coating stack, finite-metal current redistribution or a
measured foil calibration. Ground-trace faces are not separated; each trace has
one law. Perform independent mesh and outer-domain convergence for the actual
geometry and frequencies. No new application pin or platform acceptance is implied.

```sh
python -m pytest -q tests/sipi/test_reference_surfaces.py tests/sipi/test_face_conductor.py tests/sipi/test_face_line.py
```
