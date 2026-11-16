# Two-ground face-resolved conductor loss

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_conductor.md)

`two_ground_conductor_loss_by_face` applies existing local surface-metal laws
to the four straight faces of each trace, with separate bottom and top foils.
The generic current solve comes from the pinned external `galerkin` package;
metal, roughness and network laws remain in SIPI. The
[whole-surface API](two_ground_conductor.md) remains available separately.

```python
from sipi import CrossSection, Layer, Trace
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import TraceFaceMetals, ReferenceSurfaceMetals
from sipi.roughness import CausalHuray
from sipi.two_ground_face_conductor import two_ground_conductor_loss_by_face

smooth = SurfaceMetal(58e6)
rough = SurfaceMetal(58e6, roughness=CausalHuray((0.2e-6,), (2.0,)))
section = CrossSection(
    [Layer("substrate", 0.002, 4.0)],
    [Trace("signal", x=0.0, width=0.0006, y=0.0007,
           thickness=0.00005, top_width=0.00055)],
    width=0.008, top="ground",
)
loss = two_ground_conductor_loss_by_face(
    section, [1e9, 3e9, 10e9],
    conductors={"signal": TraceFaceMetals(rough, smooth, smooth, smooth)},
    reference=ReferenceSurfaceMetals(smooth, rough, None, {}),
    ground_thickness=35e-6, panels_per_edge=64, interpolation_degree=16,
)
```

## Contract

Coordinates use metres and frequency uses hertz. Both horizontal reference
planes must be grounded and the sides open. All 1–16 traces, including grounded
traces, must be finite rectangular or tapered `Trace` objects. Generic polygons
remain available through the whole-surface API; they have no implicit
bottom/top/left/right assignment in this face API. The shared admission and
2048-panel budget remain in force.

`conductors` maps exactly the signal names to `TraceFaceMetals`. The four laws
are bottom, top, left and right in global section coordinates; tapered side
faces follow their sloping edges. `ReferenceSurfaceMetals` requires both foil
laws, no side law and exactly the grounded trace names. A grounded trace's
`SurfaceMetal` is expanded uniformly to its four faces; `TraceFaceMetals`
keeps its distinct laws. `ground_thickness` is the common conservative
thickness used for both foil skin-depth checks.

All original frequency, coating, remaining-core, skin-depth and roughness
admission checks run before the field solve. Skin depth must remain at most
one fifth of the minimum remaining conductor dimension. A missing shared edge
capability raises `RuntimeError`; another solver is not substituted.

## Results and physical scope

The result uses the existing `FaceConductorLoss` interface, retaining the
frequency-dependent resistance, internal inductance, surface impedances,
roughness factors and skin depths. `loss.factors` is a
`TwoGroundFaceCurrentFactors`; `loss.factors.base` retains the original
whole-surface `TwoGroundCurrentFactors` and its diagnostics. Face order is:

1. Four faces for each signal, in signal order.
2. Bottom and top reference planes.
3. Four faces for each grounded trace, in ground-trace order.

Arrays are snapshots. The face factors and their base are immutable. Signed
currents are retained separately from energy Grams. Grounded traces have zero
potential in the original full capacitance system; they are not floating
conductors eliminated with a Schur complement. Physical endpoints and conductor
ownership must match each face uniquely. Each trace's four contributions must
reproduce its original boundary at entrywise relative `1e-10`, with no diagonal
floor; signed sums use absolute `1e-10`. Finite values, reciprocity and scaled
positive semidefiniteness are also required.

One shared solve supplies both the original whole factors and the edge
factors. The vacuum current distribution is independent of dielectric metadata.
It is the homogeneous magnetic-exterior, first-order surface-perturbation
model. Layered metals retain their local planar coating law; coating corners,
finite-metal diffusion and measured-foil calibration are not resolved.
Changing one face law changes only that face's weighted contribution. Uniform
laws recover the existing whole-surface loss within the original numerical
partition checks. The existing `network` method still requires independently
supplied physical capacitance and conductance, with matching geometry and names.

## Validation and limits

Refine panels, interpolation degree, ground modes and finite outer dimensions
for the requested face quantity. Internal consistency is not an accuracy bound.
In the registered tapered two-signal section with a grounded guard, degree14
passed the shared matrix check but failed the stricter `1e-10` face-entry
vertical-reflection comparison (about `2e-10`). Degree16 was separately checked
at 16, 32 and 64 panels per edge; the original failure was retained. The API
defaults were not silently changed, and this explicit degree16 example does not
qualify other inputs automatically.

Tests cover uniform-law equivalence, independent smooth-surface power weights,
coating and roughness localization, fixed-potential ground reduction, physical
transformations, passive networks and pre-solve refusals. Independent panel,
mesh and finite-outer face studies remain necessary for physical qualification;
a whole-boundary agreement cannot substitute for them. This direct Python API
does not change existing saved JSON, execution defaults or browser forms.

## Selected independent face and loss checks

Registered offset single, asymmetric pair and close pair rectangular sections
retain 64/128/256 panels, two independent P2 volume-energy meshes, two interior
extensions and 8/16/32 mm finite outer comparisons. Per-face independent
agreement uses relative 2% with the independent entry as denominator and no
floor; capacitance uses 0.05%. Final panel/mesh changes and both finite-outer
changes use 1% per entry. These selected rectangles do not qualify arbitrary
tapered sections automatically.

Independent smooth-metal loss checks use 1, 3 and 10 GHz. The first signal's
bottom/top/left/right conductivities are 58/35/21/45 MS/m, the second uses the
reverse sequence, and both foils use 45 MS/m, all with relative permeability
one. Independent square-root surface impedances weight the stored P2 face and
combined-ground energies. Each resistance and internal-inductance entry uses
the same 2% independent and 1% refinement checks. Reference replay does not
rerun the independent solver and is not measured-material calibration. Existing
whole-surface criteria and the original insufficient-resolution observations
remain unchanged.

[Face-specific saved two-ground line](two_ground_face_panel_line.md)

A separate [all-active corner-power method](two_ground_corner_conductor.md) retains integrable corner densities for one or two signals; both APIs keep their existing defaults, and the corner method excludes grounded traces.
