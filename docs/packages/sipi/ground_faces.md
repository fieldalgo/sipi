# Surface laws on individual ground-trace faces

[한국어](../../locales/ko/pages/packages/sipi/ground_faces.md)

The Python [reference-surface API](reference_surfaces.md) accepts either a
`SurfaceMetal` for a complete ground-trace perimeter or `TraceFaceMetals` for
its bottom, top, left and right faces. Both forms may appear in the same mapping.
Four-face assignments require a finite rectangular or tapered `Trace`.
Whole-perimeter `PolygonTrace` grounds remain supported; arbitrary polygons and
zero-thickness grounds cannot receive a four-face assignment.

```python
import numpy as np
from sipi import coplanar_stripline
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import (TraceFaceMetals, ReferenceSurfaceMetals,
                                 surface_conductor_loss_by_face)

section = coplanar_stripline(width=.5e-3, gap=.2e-3, ground_width=.5e-3,
    plane_spacing=1e-3, trace_height=.4e-3, thickness=50e-6, eps_r=4., box_width=4e-3)
copper = SurfaceMetal(58e6)
left_ground = TraceFaceMetals(bottom=copper,
    top=SurfaceMetal(58e6, roughness_rms=.5e-6), left=copper, right=copper)
reference = ReferenceSurfaceMetals(bottom=copper, top=copper, sides=None,
    conductors={'ground_left': left_ground, 'ground_right': copper})
result = surface_conductor_loss_by_face(section, [1e9, 4e9],
    conductors={'signal': TraceFaceMetals.uniform(copper)}, reference=reference,
    ground_thickness=35e-6, edge_size=2.5e-6, far_size=.1e-3, grade=.05)
assert 'reference:ground:ground_left:top' in result.boundary_labels
assert result.boundary_labels[-1] == 'reference:ground:ground_right'
np.testing.assert_allclose(result.factors.parts[4:].sum(axis=0),
                           result.factors.base.parts[-1], rtol=1e-12, atol=1e-12)
np.testing.assert_allclose(result.resistance_parts.sum(axis=1), result.R, rtol=1e-12)
```

Face names refer to global cross-section coordinates. Left/right follow sloping
faces of tapered traces. All four existing `SurfaceMetal` laws must be supplied;
`TraceFaceMetals.uniform(metal)` supplies the same law to each. Conductivity,
relative permeability and the existing explicit roughness models retain their
definitions. No roughness-statistic conversion, bulk coating or measured foil
equivalence is inferred.

## Assignment and current conservation

Boundary planes and walls keep their existing single laws. `conductors` still
maps exactly every grounded trace name; open boundaries require `None` and
active reference boundaries require a metal. Mappings are copied and read-only.
All reference conductors remain at the same PEC potential: these assignments
do not create additional ports or model a floating return conductor.

Each face's skin depth must be at most its **own trace's minimum dimension/5**
before meshing. This uses trace thickness and the minimum face width; one thin
trace or low-conductivity face cannot borrow another conductor's dimensions.
Positive frequency and the existing good-conductor limits remain required.
`ground_thickness` retains its existing positive-input and plane/wall meanings.

Reference groups are ordered bottom, top, sides, then ground traces in section
order. A whole-trace law keeps `reference:ground:<name>`; a four-face assignment
expands it into `reference:ground:<name>:bottom`, `:top`, `:left`, `:right`.
Existing common-reference and whole-trace output labels/shapes are unchanged.
Expanded labels must be unique. For example, a four-face ground named `g` and a
whole ground named `g:bottom` would collide; that assignment rejects **before
meshing**. Colons are not otherwise globally forbidden in existing trace names.

There is one shared vacuum extraction, with one unit-voltage solution per signal,
regardless of the number of face laws. Both endpoints of every ground edge must
match exactly one nonempty surface group. Ground faces retain the original
whole-trace and combined-ground current-product sums. C0, external L and the
existing 5% whole-conductor flux rejection remain unchanged. The flux gate is a
current-gradient diagnostic, not a 5% resistance-accuracy guarantee.

For N signals and M reference groups, P=4N+M entries retain the existing
[face-loss result shapes](face_conductor.md). Each Q is an N×N integral of Ki Kj
in 1/m. Resistance is `sum(Re(Zs)*Q)` and internal inductance is
`sum(Im(Zs)*Q)/(2*pi*f)`; `resistance_parts` preserves every local contribution.
Mutual terms, labels, skin depths and complex surface impedances remain available.

## Validation and limits

`tests/sipi/test_ground_faces.py` independently solves scikit-fem P1 vacuum fields
and classifies tapered ground-face currents by edge midpoints. Q matrices and
integrated currents must agree within 1e-10. On an identical mesh, assigning the
same law to all four faces reduces R/internal L and ground-trace sums to the
whole-perimeter model within 1e-12. Tests also check mixed assignments, immutable
snapshots, pre-mesh rejections, reciprocity, positive semidefinite contributions
and passive networks.

A wide central signal between two wide finite ground foils, with equal metal-face
gaps, approaches Q=1/(4W) on each signal horizontal and ground-facing face, with
integrated current -1/2 on each ground-facing face. If signal faces have surface
resistance Rs and the two facing grounds have 2Rs and 3Rs, total resistance
approaches 7Rs/(4W). Tests require face Q and weighted R within 5%, with a separate
5% mesh-change gate. A tapered-ground pair separately requires R changes below
5% for mesh refinement and box doubling. Non-facing/side currents at finite foil
ends are retained; the parallel-plate formula is only a limit comparison.

For the tapered-ground fixture, the initial 5 to 2.5 micrometre edge refinement
changed R by 6.78% and failed that gate. Halving edge/far/grade controls again
to 1.25 micrometres/50 micrometres/0.025 gives 4.63% mesh and 0.68% doubled-box
changes. The geometry, metals and 5% thresholds were retained. A passing flux
diagnostic alone would not have established this resistance convergence.

This remains first-order PEC surface perturbation: local surface laws do not
solve metal-interior diffusion, coating stacks, three-dimensional ground
connections or measured manufacturing behavior. Check mesh and outer-domain
convergence for the actual geometry and frequencies.

This unit extends the Python API. Existing saved transmission-line/5 documents
still accept one whole-perimeter metal per ground trace and reject four-face
ground records; their meaning is unchanged. Application and Windows candidates
are not advanced by this API extension.
