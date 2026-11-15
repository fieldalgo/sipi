# FEM line goals with explicit corner resolution

`seek_corner_fem_shape_line_quantity` performs the existing bounded, one-variable
FEM quantity search using a factory that returns an explicit
[corner FEM line](corner_fem_line.md). The factory must provide one positive
frequency, zero length and one scalar or two ordered paired signals. Frequency
and signal identity remain fixed throughout the search.

```python
from sipi.templates import stripline
from sipi import (CrossSectionDocument, FEMShapeTransmissionLineDocument,
                  CornerFEMShapeTransmissionLineDocument,
                  seek_corner_fem_shape_line_quantity)

metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness=dict(kind='smooth'))

def factory(width):
    cross = CrossSectionDocument(stripline(width=width, plane_spacing=.002,
        eps_r=4., thickness=.00005, box_width=.008),
        mesh=dict(edge_size=5e-6, far_size=.0002, grade=.1))
    line = FEMShapeTransmissionLineDocument(cross, [2e9], materials={},
        conductors=dict(signal=metal), reference=metal,
        ground_thickness=35e-6, length=0.)
    return CornerFEMShapeTransmissionLineDocument(line, corner_size=2.5e-6)

assert factory(.0004).corner_size == 2.5e-6
options = dict(quantity='impedance_real', tolerance=.2, max_evaluations=12)
# result = seek_corner_fem_shape_line_quantity(
#     factory, [.00039, .00041], 70.35, **options)
```

The quantity retains its original definition: scalar `impedance_real` or
`attenuation`, or paired `differential_forward_impedance_real` (Ic=0 launch) and
`common_forward_impedance_real` (Id=0 launch). The paired values use the full
complex forward characteristic matrix; they are not independent eigenmodes.

Both endpoints must evaluate. The original endpoint acceptance and bracketed
bisection rules remain. Reserve one line attempt for refinement: freeze the
selected geometry/material/metal input and halve resolved edge, far, grade
and corner controls, retaining min_angle. The factory is not recalled for
refinement. Both requested and refined values must satisfy the absolute target
tolerance, and their relative change must not exceed the original 0.005 gate.
When both values are zero, the relative change is zero.

Every factory/validation/extraction/diagnostic attempt counts, including
failures. A line attempt contains multiple internal field solves; the evaluation
budget is not a time or memory guarantee. Original current-derivative, extension,
flux, skin-depth and positive-energy checks remain mandatory. Failures use
`FEMShapeLineQuantityGoalError`, retaining the wrapper input, completed history
and any complete or partial current observations. Interruptions propagate.

The result is a `CornerFEMShapeLineQuantityDesign` with selected/refined corner
input snapshots and both current records. Preserve its full input and exact
numerical artifacts. The direct callable is not serialized; existing saved
FEM design schemas keep their original contract.

Validation includes independent characteristic quantities and actual scalar
70.35-ohm/paired 92.8-ohm targets, equal/smaller corner controls, frozen refinement,
original-case parity and typed failures. These finite checks do not certify
weak mutual loss, outer-domain sufficiency, arbitrary factories, continuity,
uniqueness, global optimality, empirical accuracy or new platforms.

[한국어](../../locales/ko/pages/packages/sipi/corner_fem_goal.md)
