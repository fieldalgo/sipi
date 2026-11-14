# Separate ground-trace and bottom-plane surface metals

`panel_shape_conductor_loss_with_reference_metals` applies independent surface
laws to each whole signal perimeter, the bottom plane and each named grounded
trace. It reuses the [capacitance-shape current factors](panel_shape_conductor.md)
already stored before reference grouping. No field solver or default method
changes, and the original common-reference API/output remains unchanged.

`conductors` maps exactly every signal name to `SurfaceMetal` or
`LayeredSurfaceMetal`. `reference` must explicitly be `ReferenceSurfaceMetals`:
`bottom` has a metal, `top` and `sides` are None, and `conductors` maps exactly
each grounded trace name to one whole-perimeter metal. `TraceFaceMetals` is
rejected by this API. Bottom-ground/open-top/open-sides convex finite-thickness
geometry and all existing panel/shape-step limits remain required.

Skin-depth checks use each boundary's own material and remaining dimension.
The bottom uses explicit `ground_thickness`; ground traces use their own finite
cross-section dimensions. Coating thickness reduces the conservative remaining
core just as in existing surface laws. Every active metal must satisfy the
existing good-conductor and skin-depth <= remaining dimension / 5 checks before
fields. Existing roughness models and their stated conventions remain; a
coated metal cannot silently acquire a roughness correction. The planar local
coating law does not resolve coating corners or interior current diffusion.

For boundary b with shape energy matrix Qb and local complex surface impedance
Zsb, the calculation adds Re(Zsb) Qb to R and Im(Zsb) Qb / omega to internal L.
Changing a ground metal changes its loss weighting while retaining the same
PEC vacuum current field. This is the existing surface-impedance perturbation,
not a recomputed finite-conductivity field.

`ShapeReferenceConductorLoss` retains immutable frequency, R, internal L,
`skin_depth`, `roughness_factor`, `surface_impedance`, `metals`,
`boundary_labels` and `boundary_parts`. The order is signals in geometry order,
`reference:bottom`, then `reference:ground:<name>` in geometry order. The
original `factors` retains grouped reference currents, C0 and all current
samples/two-step evidence. `resistance_parts` gives each named contribution.
`network(C=..., G=..., length=..., z_ref=...)` uses existing RLGC conversion;
C/G must correspond to the same geometry and frequency vector.

This example prepares a guarded geometry with a different bottom metal and a
coated guard. Dimensions are metres and conductivity S/m. The commented call
runs actual fields. See the [saved reference-metal line](shape_reference_panel_line.md) to store the complete calculation.

```python
from sipi import CrossSection, Layer, Trace, MetalLayer
from sipi.boundary_conductor import SurfaceMetal, LayeredSurfaceMetal
from sipi.face_conductor import ReferenceSurfaceMetals
from sipi.shape_reference_conductor import panel_shape_conductor_loss_with_reference_metals

section = CrossSection([Layer('uniform', .01105, 4.2)], [
    Trace('a', -.0005, .0003, .001, 50e-6),
    Trace('guard', 0., .0002, .001, 50e-6, ground=True),
    Trace('b', .0005, .0004, .001, 60e-6),
], .02)
signals = {'a': SurfaceMetal(58e6), 'b': SurfaceMetal(35e6)}
reference = ReferenceSurfaceMetals(
    bottom=SurfaceMetal(45e6), top=None, sides=None,
    conductors={'guard': LayeredSurfaceMetal(58e6, coatings=(
        MetalLayer(.2e-6, 14e6, 3.), MetalLayer(1e-6, 40e6)))})
options = dict(conductors=signals, reference=reference, ground_thickness=35e-6,
               panels_per_edge=64, ground_modes=1024, interpolation_degree=16,
               step_fraction=.001)
# result = panel_shape_conductor_loss_with_reference_metals(
#     section, [1e9, 4e9, 16e9], **options)  # Starts the current extraction.
```

Validation checks independent planar metal transfer, each boundary sum, passive four-port equations, exact reference regrouping and selected finite panel observations. The current extraction remains a finite-domain approximation. These checks do not establish outer-domain sufficiency, small mutual-entry or absolute accuracy, measured foil behavior, or arbitrary geometry support.
