# All-active corner currents and conductor loss

[한국어](../../locales/ko/pages/packages/sipi/two_ground_corner_conductor.md)

The explicit functions in `sipi.two_ground_corner_conductor` connect the
shared corner-power field to SIPI's existing surface-metal laws:

- `two_ground_corner_current_factors`: whole boundaries and separate foils;
- `two_ground_corner_face_current_factors`: bottom/top/left/right trace faces;
- `two_ground_corner_conductor_loss`: one local metal law per whole boundary;
- `two_ground_corner_conductor_loss_by_face`: separate local trace-face laws.

```python
from sipi import CrossSection, Layer, Trace
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import TraceFaceMetals, ReferenceSurfaceMetals
from sipi.two_ground_corner_conductor import two_ground_corner_conductor_loss_by_face

section = CrossSection(
    [Layer("uniform", 0.002, 4.0)],
    [Trace("signal", x=0.00015, y=0.0008, width=0.0006, thickness=0.00007)],
    width=0.008, top="ground",
)
metal = SurfaceMetal(58e6)
loss = two_ground_corner_conductor_loss_by_face(
    section, [1e9, 3e9, 10e9],
    conductors={"signal": TraceFaceMetals.uniform(metal)},
    reference=ReferenceSurfaceMetals(metal, metal, None, {}),
    ground_thickness=35e-6, panels_per_edge=128, ground_modes=256,
)
```

## Scope and controls

Require one or two finite rectangular/tapered `Trace` objects, all signals,
with grounded bottom/top and open sides. Grounded traces, generic polygons
in the face assignment, and three or more signals are explicitly refused.
This leaves the existing [whole](two_ground_conductor.md) and
[face](two_ground_face_conductor.md) methods and their defaults unchanged.
A missing pinned shared capability raises `RuntimeError`, without fallback.

Dimensions are metres and frequencies hertz. `panels_per_edge` is an even
cubic subdivision count `16..512`; corner patches leave `n-6` actual panels
per edge, at most 4048 for two four-sided traces at 512. Default subdivisions
are 128. `interpolation_degree` is fixed at 24, checked against 20.
`ground_modes` is the **actual fine** Fourier count, even `64..4096`, default
256, compared with half the count and quadrature 16/32. This is different
from the original method's coarse-count convention.

The shared solver integrates the corner density and squared-current Gram,
checks its internal residuals/refinement at `1e-10` and condition below `1e10`,
and returns one immutable whole/edge result. SIPI preserves its all-active
basis directly, without a numerical `solve(C,C)` transform. Trace faces are
matched to physical endpoints and ordered bottom/top/left/right, followed
by bottom/top foils. Each face partition must reproduce the whole factors
at entrywise `1e-10`, including signed cross terms with no diagonal floor.
The base diagnostics identify `two-ground-corner-power-all-active`.

`TwoGroundCurrentFactors`, `TwoGroundFaceCurrentFactors`,
`TwoGroundConductorLoss` and `FaceConductorLoss` retain their existing result
contracts. Whole laws use `SurfaceMetal`; face laws use `TraceFaceMetals`.
`ReferenceSurfaceMetals` must contain both foils, no side law and an empty
grounded-trace mapping. Existing coating, roughness, remaining-core and
skin-depth restrictions run before the field solve. A skin depth larger
than one fifth of the remaining minimum conductor dimension is refused.

The factors describe vacuum currents in a homogeneous magnetic exterior;
dielectric metadata does not enter that current solve. `C0` is vacuum
capacitance. Physical dielectric `C/G` must be computed for matching geometry
and names before calling `loss.network(C=..., G=..., length=...)`. The local
surface-perturbation model does not resolve finite-metal diffusion, coating
corners or measured-foil calibration. No new saved JSON format or UI route
is selected by these functions.

## Evidence and limitations

Stored independent scikit-fem 12.0.2 (BSD-3-Clause, not shipped) P3
volume-energy references cover an offset rectangle and an unequal tapered
pair, each with two qualified meshes and two interior velocity extensions.
Tests compare vacuum capacitance at `0.05%`, face factors and weighted loss
at `2%`, whole factors at `1%`, and apply the analytical surface-impedance
formula at 1/3/10 GHz. The shared engine separately checks panel `256→512`,
finite outer widths `8→16→32 mm`, and reflection, without a denominator floor.
The original failed pair reference mesh remains failed; the later finer
mesh pair supplies the qualified comparison. Replay does not rerun P3.

Surface laws are checked against their direct formula, selected-face changes,
whole/face equivalence, passivity, and the existing reciprocal network model.
These selected numerical cases do not establish arbitrary geometry, physical
measurement, roughness calibration, other-platform or browser qualification.
Refine panels and outer bounds for each requested quantity. A three-active
reference and a fixed-ground reduction did not meet their separate gates;
those scopes are excluded rather than inferred from these passing cases.

## Saved corner-power line

The separate [corner-power face line](two_ground_corner_face_panel_line.md) stores this explicit current method, matched dielectric fields and network results.
