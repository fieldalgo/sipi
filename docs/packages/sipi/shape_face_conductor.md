# Surface laws on straight-face shape currents

`panel_shape_conductor_loss_by_face` applies separate local surface laws to
[straight-face shape-current energies](panel_shape_faces.md). It supports one
to four finite rectangular or tapered `Trace` conductors over bottom ground
with open top/sides. Signal metals must map each name to `TraceFaceMetals` in
bottom/top/left/right order; left/right are sloping faces when tapered.

`reference` must explicitly be `ReferenceSurfaceMetals`: a bottom-plane law,
`None` for open top/sides, and exactly one assignment per grounded trace.
A grounded trace accepts either a whole-perimeter `SurfaceMetal` or four
`TraceFaceMetals`. Whole assignment sums the four face energies; it does not
replace them with the separately differentiated whole-boundary matrix.
The original entrywise 1e-4 face-to-whole agreement gate remains active.

Existing `SurfaceMetal` bulk/explicit roughness and `LayeredSurfaceMetal`
planar coatings are reused. Every boundary's conductivity, permeability,
frequency, skin depth and remaining core are checked before fields. A thin
plane and a thick grounded trace use their own dimensions. Coatings and
roughness cannot be combined. No empirical roughness parameters are inferred.
Geometry is the finished PEC boundary; coatings occupy its inside and use a
local high-frequency perturbation, not a resolved coating-corner or finite
metal-interior solution. Existing good-conductor and skin-depth gates remain.

`ShapeFaceConductorLoss` retains immutable frequency, R [ohm/m], internal L
[H/m], skin depth, roughness factors, surface impedance [ohm/square], metal
assignments, `boundary_labels` and `boundary_parts` [1/m]. Boundary order is
four faces per signal in signal order, bottom plane, then each grounded trace
in geometry order as either one whole group or four faces. This differs from
the raw geometry-interleaved face order; named structural mapping preserves
assignments even when ground traces occur between signals.

For each boundary b, R = sum(Re(Zs_b)*Q_b) and internal L =
sum(Im(Zs_b)*Q_b/omega). `resistance_parts` exposes each contribution.
`factors` retains all face samples and its original `base` whole-current
samples, C0 and external L. Energy is not signed face current: conservation
is the original grouped diagnostic in `factors.base.current_integrals`.
No rescaling or PSD projection is performed. Original whole or face errors,
partial samples and interrupts propagate unchanged. Resource controls and
maximum 85 shared solves are those of the face-energy API.

The following creates inputs without running fields; uncommenting the call
starts the calculation. Units are metres and hertz.

```python
from sipi import CrossSection, Layer, Trace, MetalLayer
from sipi import panel_shape_conductor_loss_by_face
from sipi.face_conductor import TraceFaceMetals, ReferenceSurfaceMetals
from sipi.boundary_conductor import SurfaceMetal, LayeredSurfaceMetal

section = CrossSection([Layer('uniform', .01105, 4.)], [
    Trace('a', -.0005, .0003, .001, 50e-6, top_width=.00022),
    Trace('guard', 0., .0002, .001, 50e-6, ground=True, top_width=.00012),
    Trace('b', .0005, .0004, .001, 60e-6, top_width=.00055),
], .02)
copper = SurfaceMetal(58e6)
coated = LayeredSurfaceMetal(58e6, coatings=(MetalLayer(.2e-6, 14e6, 3.),))
conductors = {'a': TraceFaceMetals(copper, coated, copper, copper),
              'b': TraceFaceMetals.uniform(copper)}
reference = ReferenceSurfaceMetals(copper, None, None,
    {'guard': TraceFaceMetals.uniform(SurfaceMetal(40e6))})
options = dict(conductors=conductors, reference=reference, ground_thickness=35e-6,
               panels_per_edge=32, ground_modes=4096,
               interpolation_degree=16, step_fraction=.001)
# result = panel_shape_conductor_loss_by_face(section, [1e9, 4e9], **options)
# print(result.boundary_labels, result.R, result.L_internal)
```

`result.network(C=..., G=..., length=..., z_ref=...)` uses retained external L
plus internal L with the supplied dielectric C/G. The caller must supply C/G
for the same geometry, signal order and frequencies. This direct API does
not compute dielectric fields or add a new saved JSON schema.

Validation includes separate face-law transfer matrices, local positive
power, uniform-face agreement with original whole-current loss, actual
tapered guarded-line panel refinement and signal permutation, independent
four-port transfer and passivity, preflight rejection and retained errors.
Source and isolated installed checks are distinct from platform qualification.
Finite-domain convergence observations and previous independent current
references do not establish absolute or small mutual-entry accuracy for
arbitrary geometry. Refine the intended geometry and outer box separately.
Browser/EXE bindings, saved face-loss input and new platform qualification
are outside this direct API unit.

[Save a face-metal line](shape_face_panel_line.md).
