# Metal loss with FEM geometry-energy currents

`fem_shape_conductor_loss_by_boundary` applies existing `SurfaceMetal` or
`LayeredSurfaceMetal` laws to the explicitly checked
[FEM geometry-energy currents](fem_shape_conductor.md). Each signal has one
material. The bottom/top planes and any finite grounded traces all share the
one explicit reference material; individual foil faces are not separated.
Existing loss APIs and saved-line defaults are unchanged.

```python
from sipi import fem_shape_conductor_loss_by_boundary
from sipi.templates import coupled_stripline
from sipi.boundary_conductor import SurfaceMetal

section = coupled_stripline(width=.0004, gap=.0003, plane_spacing=.002,
                            thickness=.00005, eps_r=4., box_width=.008)
metals = {'positive': SurfaceMetal(58e6), 'negative': SurfaceMetal(35e6)}

def calculate():
    return fem_shape_conductor_loss_by_boundary(
        section, [2e9, 5e9], conductors=metals,
        reference=SurfaceMetal(58e6), ground_thickness=35e-6,
        edge_size=2.5e-6, far_size=.0001, grade=.05)
```

Call `calculate()` to run the fields. Material/core/skin-depth checks precede
meshing. At most four signals are admitted. One mesh supplies the vacuum current
basis and all its checked geometric perturbations. The original gradient flux
error must still be at most 5%; this inherited guard is separate from the new
energy derivative checks and is not a resistance error bound.

For each boundary, the returned R contribution is `Re(Zs) * Q`; internal L is
`Im(Zs) * Q / omega`. R has units ohm/m and L has units H/m. The returned
`BoundaryConductorLoss.factors` is a `FEMShapeCurrentFactors` object containing the
original gradient evidence, both extensions, both derivative steps and every
completed capacitance sample. The loss result's `boundary_labels` follows the signals and one
reference group. `resistance_parts` retains each boundary's contribution.

Coatings occupy the inside of the finished boundary. The existing conservative
remaining-core and local planar surface-law limits remain in effect. Coating
corners, DC and full metal diffusion are not solved by this adapter. Existing
roughness models retain their own assumptions; no roughness calibration or
conversion between measurement conventions is inferred.

Use `result.network(C=..., G=..., length=..., z_ref=...)` with matched-geometry,
matched-frequency dielectric C/G. External inductance uses the same vacuum C0;
internal inductance is added separately. This adapter does not calculate the
requested dielectric C/G itself. Never combine matrices from different signal
orders or physical geometries.

A current extraction failure retains its original typed exception and partial
field observations; interrupts propagate. A flux or material failure is not
silently recovered with another current method. Check mesh refinement, outer
domain and independent references separately, including small mutual entries.
The tests exercise actual closed-pair meshes, independent layered-metal transfer
and a four-port matrix-exponential network. An accepted selected case does not
establish arbitrary-geometry or measured accuracy, or support for a different
OS, browser Worker or executable artifact.

[한국어](../../locales/ko/pages/packages/sipi/fem_shape_loss.md)
