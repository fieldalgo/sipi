# Transverse anisotropic electrostatics

`capacitance_matrix(mesh, eps_r, signals, ground)` accepts relative permittivity as
a scalar, one scalar per triangle `(T,)`, a constant transverse matrix `(2,2)`, or
one matrix per triangle `(T,2,2)`. Tensor axes are the mesh's **global x/y axes**.
The existing galerkin P1 tensor stiffness performs the solve; no separate field
solver is introduced.

A tensor is reciprocal and complex symmetric, with positive-definite real part
and positive-semidefinite `−Im(eps_r)` for the `exp(+jωt)` convention. Symmetry is
checked at relative `1e-12`; only that accepted roundoff is averaged. Loss-matrix
eigenvalues allow relative `1e-12` roundoff about semidefiniteness. Entries must
be finite numerical values, not booleans. An off-diagonal imaginary entry may
be positive in a passive tensor: passivity is a **matrix** condition, not a test
of every entry's sign. Nonreciprocal, indefinite and active tensors are rejected.
The result is complex Maxwell capacitance `C−j C_loss` in F/m.

`line_parameters` accepts a **real** tensor and scalar or per-triangle `tan_delta`.
One local tangent multiplies the entire local tensor. A matrix of separate axis
tangents is not accepted, and a complex tensor is not silently combined with a
second loss model. Use `capacitance_matrix` for general complex tensors with
independent loss axes. Existing scalar/per-triangle behavior is retained.

```python
import numpy as np
from sipi import coupled_microstrip, line_parameters

section = coupled_microstrip(
    width=.5e-3, gap=.3e-3, substrate_height=.5e-3,
    eps_r=4, tan_delta=.01, thickness=35e-6,
    air_height=4e-3, box_width=8e-3,
)
meshed = section.mesh(edge_size=4e-6, far_size=.25e-3, grade=.2)
materials = {
    'substrate': np.array([[3.5, .7], [.7, 4.5]]),
    'air': np.eye(2),
}
eps = np.array([materials[meshed.mesh.region_names[i]]
                for i in meshed.mesh.regions])
parameters = line_parameters(
    meshed.mesh, eps, meshed.signals, meshed.ground,
    tan_delta=meshed.tan_delta,
)
parameters.C, parameters.C0, parameters.L, parameters.G(1e9)
```

This explicitly supplies coefficients to the mesh API. `section.analyze()` still
uses the original scalar layer materials. `Layer`, template `eps_r`, geometry
JSON and frequency-dependent material documents do **not** yet accept tensors.
Save the supplied tensor field and exact mesh/build identity separately; no new
saved tensor schema is implied by this API. Returned `LineParameters` retains
the usual vacuum `C0` and nonmagnetic quasi-TEM `L=μ0 ε0 C0⁻¹` approximation.
Do not infer exact even/odd modes for an asymmetric material/geometry pair.
Tensor entries involving longitudinal z, nonreciprocity, magnetic anisotropy
and full-wave propagation are outside this two-dimensional contract.

## Independent checks

Identity tensors reproduce scalar/per-triangle C, C0, L and C_loss within relative
`1e-12`. For aligned layered parallel plates, the independent complex solution
`C=ε0 W/(h1/eps_yy1+h2/eps_yy2)` and vacuum inductance agree within `1e-9`.

An exact coordinate transform provides a rotated elliptic coax reference.
For positive real A and `x=A^(1/2) ξ`, circular radii a,b in ξ become physical
ellipses, and tensor `A(1−j tanδ)` gives
`C=2π ε0 sqrt(det A)(1−j tanδ)/ln(b/a)`. Radial/angular refinement
16/64 → 32/128 → 64/256 must decrease error with order at least 1.5 and final
relative error <=0.1%. Rigid coordinate/material rotations and uniform geometry
scaling preserve capacitance within `1e-12`. The coax outer ground is a physical
boundary; it is not an artificial open-domain convergence test.

A coupled microstrip with heterogeneous complex tensors is compared with
scikit-fem 12.0.2's independent anisotropic complex P1 energy on the same mesh,
at maximum relative C difference `1e-9`. Separate 4→1 μm edge refinement and
doubling the box/air dimensions each require maximum relative complex-C entry
changes <=1%. Same-mesh comparison alone is not convergence evidence. Tests also
check reciprocity, positive capacitance/loss matrices, input copies, invalid
shapes, symmetry, positivity, passivity and incompatible loss representations.

These checks establish the documented numerical problems, not measured laminate,
frequency-dependent tensor dispersion, 3D transition or new-platform accuracy.

[Overview](overview.md) · [Dielectric dispersion](dielectrics.md) ·
[한국어](../../locales/ko/pages/packages/sipi/tensor_electrostatics.md)
