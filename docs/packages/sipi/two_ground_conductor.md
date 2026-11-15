# Explicit two-ground surface currents

[한국어](../../locales/ko/pages/packages/sipi/two_ground_conductor.md)

This explicit consumer uses the public
`galerkin.laplace_two_ground.solve_two_ground_rectangle` capability supplied by
the exact shared development revision in `dependencies.json`. The API raises
RuntimeError if that capability is absent, without a fallback. Existing extraction
defaults are unchanged. Build the shared packages from the pinned revision;
a repeated version number does not identify a compatible wheel.

```python
from sipi import CrossSection, Layer, Trace
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import ReferenceSurfaceMetals
from sipi.two_ground_conductor import two_ground_conductor_loss

section = CrossSection([Layer("uniform", .002, 4.)],
    [Trace("signal", 0., .0007, .0006, .00005)], .008, top="ground")
loss = two_ground_conductor_loss(section, [2e9, 5e9],
    conductors={"signal": SurfaceMetal(58e6)},
    reference=ReferenceSurfaceMetals(
        bottom=SurfaceMetal(58e6), top=SurfaceMetal(21e6),
        sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=64)
assert loss.boundary_labels == ("signal:signal", "reference:bottom", "reference:top")
```

`two_ground_current_factors` accepts a CrossSection with grounded bottom and top,
open sides and finite convex signal/grounded trace boundaries. Side conditions
mean zero normal flux in the finite electric dual, not an infinite radiation
boundary. Coordinates, widths, heights and thicknesses are metres. Surface order
is signals in input order, bottom plane, top plane, then grounded traces in input
order. Grounded traces have zero potential; they are never treated as floating.
Their vacuum capacitance is selected by the principal signal block, with the
complete boundary-current basis transformed before grouping. Signed currents
sum to zero; per-surface matrices remain available even though `parts` retains
the common grouped-reference convention.

The current solve is the homogeneous nonmagnetic vacuum dual. Layer permittivity
and dielectric-region metadata do not enter it. Combine its external inductance
and conductor loss only with dielectric C/G extracted for exactly the same
geometry and boundary conditions. This does not solve a spatially magnetic
exterior. Local conductor permeability belongs to the existing metal surface law.

`two_ground_conductor_loss` requires a SurfaceMetal per signal and an explicit
ReferenceSurfaceMetals with bottom/top laws, no side law and exactly the grounded
trace names. Each law applies to a whole perimeter or foil. Signal-face laws and
grounded-trace face laws are not supported by this entry point. Both planes use
the explicit `ground_thickness` for the existing minimum-dimension restriction.
Separate foil conductivities/permeabilities and existing local roughness or
layered coatings are supported by composition, not a new diffusion equation.
Every material and remaining-core skin-depth gate is checked before a field
solve. The original requirement is skin depth at most one fifth of the minimum
remaining conductor dimension. The layered law preserves its existing
no-roughness-combination restriction.

For surface k, `R = sum(real(Zs[k])*Q[k])` and
`L_internal = sum(imag(Zs[k])*Q[k]/omega)`. The result retains frequency, metal
order, signed currents, separate Q, skin depths, roughness factors and surface
impedances in immutable arrays. Its network method adds external and internal L
and uses the existing RLGC network implementation. Network reciprocity and
passivity do not establish absolute conductor-loss accuracy.

Explicit panel count, ground modes and interpolation degree are forwarded to the
shared capability. The API retains the 2048-panel resource limit and 1e-10
current/ground-voltage checks. The shared matrix, ground refinement and condition
gates still apply. Four previously registered geometries and finite wider boxes
are compared to their stored independent P4 references; the 16/32mm box
references are coarse P4, not newly refined references. The asymmetric pair
requires explicit degree14, with its prior degree12 failure preserved. Additional
grounded-trace and distinct-foil checks establish algebraic transformations and
surface-law identities only; they do not imply new mesh or outer convergence.
The study scope remains finite, with no measurement, all-geometry accuracy,
new platform, browser or EXE qualification.

For explicit bottom/top/left/right trace laws, use the separate
[face-resolved API](two_ground_face_conductor.md).
