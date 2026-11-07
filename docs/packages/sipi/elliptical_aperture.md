# Local elliptical-aperture capacitance matrices

`EllipticalAperture` computes the complex Maxwell capacitance per length for one
or two round PEC conductors inside an axis-aligned, grounded elliptical boundary.
The dielectric is homogeneous. It reuses meshine's polygon meshing and Galerkin's
electrostatic energy assembly. Both equal and unequal conductors are supported.

```python
from sipi import RoundConductor, EllipticalAperture, ApertureSectionDocument

section = EllipticalAperture(
    width=1.20e-3, height=0.80e-3,
    conductors=[
        RoundConductor("p", diameter=0.28e-3, x=-0.25e-3),
        RoundConductor("n", diameter=0.22e-3, x=0.25e-3, y=0.03e-3),
    ],
    eps_r=3.96, tan_delta=0.03,
)
document = ApertureSectionDocument(section, mesh={
    "size": 25e-6, "angular_divisions": 256,
})
restored = ApertureSectionDocument.loads(document.dumps())
print(restored.section.names)
print(restored.analyze())             # complex Maxwell matrix, F/m
print(section.mixed_capacitance(**restored.mesh_options))
```

All lengths are in metres. `width` and `height` are **full axis lengths**;
`diameter` is a conductor diameter. The ellipse centre is `(0, 0)` and each
conductor has explicit centre coordinates. Names are unique, nonempty, single
line strings; `ground` is reserved. One or two conductors are required.

The returned matrix follows input conductor order, including unequal self terms
and mutual coupling. A uniform scalar coefficient does not change the field:
the vacuum matrix is scaled by `eps_r*(1-j*tan_delta)`, using `exp(+j*omega*t)`.
Relative permittivity is positive; loss tangent is nonnegative. Booleans and
nonfinite numbers are rejected. Nonrepresentable dimensional element areas,
nonfinite C, or a non-positive-definite real C raise errors.

This is a local **C' in F/m**. It does not infer a total pad capacitance, plane
spacing, magnetic return, inductance, impedance, conductor loss or a 3D via
transition. An ellipse is defined geometrically, not by an implicit oval or
shared-antipad conversion. Do not transfer these validation errors to a physical
transition, a different geometry convention or a measured device.

## Differential and common coordinates

For two conductors, `mixed_capacitance()` returns the full matrix in the order
`(differential, common)`, defined by

- `Vd = V1 - V2`, `Vc = (V1 + V2)/2`;
- `Qd = (Q1 - Q2)/2`, `Qc = Q1 + Q2`;
- `T = [[0.5, 1], [-0.5, 1]]`, `C_mixed = T.T @ C @ T`.

The transformation preserves `V.conj().T @ Q`. For an exactly exchange-symmetric
pair, `Cdd = (C11-C12)/2` and `Ccc = 2*(C11+C12)`. These conventions differ from
the per-conductor odd/even capacitances. Asymmetric mixed cross terms are kept;
these are coordinates, not a claim that independent propagation modes exist.
No symmetry averaging is applied to the computed matrix.

## Geometry, mesh and saved inputs

`mesh(size=None, angular_divisions=128)` returns a `MeshedAperture` with the shared
mesh in metres, ordered signal node sets and ground nodes. Default `size` is the
larger full axis divided by 48. `size` controls field resolution; integer angular
divisions (at least 16) control **both** ellipse and circle polygonization.
Boundary segments remain straight when refined. Check both controls separately.
The outer ground is a physical boundary, not an artificial open-domain box.

Construction checks names, numbers, bounding-box clearance and conductor overlap.
`mesh_settings()` completes containment preflight: each entire inner disk must
fit in every inward half-plane of the inscribed outer polygon, with clearance
greater than `32*machine_epsilon` in units of the larger axis. This conservative
condition can reject a circle that fits the exact ellipse; increase angular
resolution. It also rejects circles whose centres fit but circumferences do not.
No field solve occurs before preflight. Near-contact, extreme aspect ratios and
very small conductors still require case-specific convergence evidence.

Holes are sorted by geometry for meshing, independently of names or output order.
Swapping the requested conductor order therefore permutes C without selecting a
different mesh. A separately remeshed reflection need not give exactly equal
self terms; tests distinguish that discretization error from algebraic symmetry.

`ApertureSectionDocument` snapshots `sipi.aperture-section/1`: metre units, full
axes, named conductor diameters/centres, dielectric and explicit mesh settings.
It rejects missing/unknown fields, duplicate JSON keys, invalid geometry and
unsupported schema or units, without embedding results. The existing
[`CircularAperture` and `sipi.circular-aperture/1`](circular_aperture.md) are
unchanged. Neither input is an impedance-study document.

## Validation

Independent constant-charge boundary panels use a logarithmic Green function,
analytic self-panel integration, 16-point Gauss quadrature for other panels,
an unknown potential offset and zero total boundary charge. Refining 128 to 256
panels per loop changes C by at most 0.0264% in the three recorded cases.

| Case | Fine FEM versus panel reference, relative matrix norm |
|---|---:|
| Eccentric circular aperture: axes 0.8/0.8 mm, diameter 0.28 mm, offset 0.2 mm | 0.0831% |
| Centred circular conductor: ellipse axes 0.73/0.53 mm, diameter 0.28 mm | 0.0587% |
| Equal pair: ellipse axes 1.2/0.8 mm, diameters 0.28 mm, centre pitch 0.5 mm | 0.1422% |

The pair's differential component differs by 0.1577%. The circular exact-reference
error is 0.0918%. Preregistered limits are 1% for matrix/differential comparison,
0.2% for panel refinement and the circular analytic limit, and 0.5% for separate
field/polygon refinement. These results are examples, not universal bounds.
Independent complex scikit-fem assembly on the same mesh is separately checked
to `1e-9`, with charge/power duality, input-order permutation, rigid mesh rotation,
binary geometric scaling, complex-material scaling and strict input replay.

[한국어](../../locales/ko/pages/packages/sipi/elliptical_aperture.md)
