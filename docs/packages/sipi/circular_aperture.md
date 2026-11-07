# Local circular-aperture capacitance

`CircularAperture` solves the homogeneous two-dimensional electrostatic problem
between a round PEC conductor and a circular grounded boundary. The conductor
may be displaced from the aperture centre. It uses the shared Galerkin P1 solver
and annulus topology; no additional solver or runtime dependency is introduced.

```python
from sipi import CircularAperture, ApertureDocument

section = CircularAperture(
    conductor_diameter=0.28e-3,
    aperture_diameter=0.80e-3,
    offset_x=0.10e-3, offset_y=-0.07e-3,
    eps_r=3.96, tan_delta=0.03,
)
document = ApertureDocument(section, mesh={
    "radial_divisions": 64, "angular_divisions": 256,
})
saved = document.dumps()
restored = ApertureDocument.loads(saved)
capacitance = restored.analyze()       # complex F/m, C - j*C_loss
print(capacitance.real, -capacitance.imag)
refined = section.capacitance(radial_divisions=128, angular_divisions=512)
print(abs(refined / capacitance - 1))
```

Both size inputs are **diameters in metres**, not radii or finished-hole sizes.
The grounded circle is centred at `(0, 0)`. `offset_x` and `offset_y` locate the
inner conductor centre. With inner radius `a`, outer radius `b` and offset
magnitude `e`, require `a + e < b`. Inputs must be finite real numbers; booleans
are rejected. Relative permittivity is positive and loss tangent is nonnegative.
The homogeneous material is `eps_r * (1 - j*tan_delta)` for `exp(+j*omega*t)`.
Its harmonic field is independent of the uniform scalar material coefficient;
the implementation solves in vacuum and scales C afterwards. Nonrepresentable
dimensional cell areas or a nonfinite/nonpositive real capacitance raise errors.

The output is a local capacitance **per length**. It is not the total capacitance
of a finite pad or barrel, nor an inductance, impedance or 3D via-transition
model. There is no inferred plane spacing, magnetic return, frequency dispersion,
roughness, conductor loss or end fringing. This model does not expose a via
impedance by combining local C with an assumed inductance. Multiplication by a
height would introduce a separate uniform-extrusion approximation.

## Mesh and saved input

`mesh()` returns a Galerkin mesh in metres with `inner` and `outer` boundary node
sets. `radial_divisions` defaults to 32 (integer at least 2), and
`angular_divisions` to 128 (integer at least 16). Both controls need refinement;
the defaults are not an accuracy certificate. The outer boundary is physical,
so changing its diameter changes the problem rather than testing open-domain
truncation.

Curves are inscribed polygons. Before allocation, the whole inner disk must fit
inside the outer polygon's incircle: in units of outer diameter,
`0.5*cos(pi/angular_divisions) - a/D - e/D > 32*machine_epsilon`.
This conservative guard can reject a circle geometry with a positive clearance;
increase angular resolution. Collapsed or inverted mapped cells are rejected.
Near-contact, very small conductors and extreme scales need further convergence
checks even if this geometry guard passes.

`ApertureDocument` stores `sipi.circular-aperture/1`, `length_unit: "m"`, the four
geometry values, dielectric properties, and explicit resolved mesh divisions.
It snapshots inputs and returns copies. Unknown/missing fields, unsupported
units/schema, duplicate JSON keys and nonfinite values are rejected. Results
are not embedded. Existing cross-section/study/design schemas and their template
registry are unchanged; this separate capacitance input is not accepted by an
impedance study or target-impedance document.

## Independent checks and limits

The eccentric-circle closed form is

`C' = 2*pi*epsilon0*eps_r / acosh((b*b + a*a - e*e)/(2*a*b))`.

For `e=0`, its denominator is `log(b/a)`. Tests use `a=0.14 mm`, `b=0.40 mm`
and `e/(b-a)=0, 0.5, 0.8`, refining both discretizations. The acceptance limit is
0.2% for the fine-mesh exact-reference error and for each separate final radial
and angular step. The observed fine errors at `(128, 512)` are approximately
0.00199%, 0.00273% and 0.00575%, respectively. These cases are not a universal
error bound for all possible geometries.

Independent scikit-fem 12.0.2 complex P1 assembly on the same polygonized mesh
checks C to relative `1e-9`; this checks assembly, not geometry convergence.
Additional checks cover uniform scaling, rigid rotation, mesh-symmetry rotations
and reflection, homogeneous complex-material scaling, invalid input, polygon
clearance and saved-input replay. No measured or three-dimensional transition
accuracy is claimed.

[한국어](../../locales/ko/pages/packages/sipi/circular_aperture.md)
