# Principal-axis dispersive dielectrics

`sipi.dielectric.PrincipalAxisDielectric(axis1, axis2, angle_rad=0)` combines two
existing scalar material models on fixed orthogonal transverse axes:

`eps(f) = R(angle) diag(eps1(f), eps2(f)) R(angle)^T`.

Axis 1 is at `angle_rad` counterclockwise from the **mesh global x axis**; axis 2
is perpendicular. Angles are finite real radians, including negative values.
Each axis must be a `ConstantDielectric`, `DebyeDielectric`, `WidebandDielectric`
or `TabulatedDielectric`; nested principal-axis models are rejected. The rotation
is real and frequency independent. Both axes can have different dispersion and
loss, with the constituent models' validity and causality limits unchanged.

Scalar frequency produces shape `(2,2)`, a frequency vector produces `(F,2,2)`.
The real tensor is positive definite and the loss tensor `−Im(eps)` is positive
semidefinite in the `exp(+jωt)` convention. A positive imaginary off-diagonal
entry is compatible with passivity. These are relative, dimensionless transverse
coefficients. Longitudinal coupling, magnetic anisotropy and nonreciprocity are
outside the contract.

## Save and replay a line

```python
from sipi import CrossSectionDocument, microstrip
from sipi.dielectric import PrincipalAxisDielectric, DebyeDielectric, WidebandDielectric
from sipi.line_model import TransmissionLineDocument

section = microstrip(width=.4e-3, substrate_height=.5e-3,
                     thickness=.1e-3, eps_r=4,
                     air_height=.5e-3, box_width=2e-3)
material = PrincipalAxisDielectric(
    DebyeDielectric(eps_inf=2, strengths=[3], relaxation_hz=[1e8]),
    WidebandDielectric(eps_ref=4, tan_delta_ref=.02, reference_hz=1e9),
    angle_rad=.4,
)
document = TransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=10e-6, far_size=.25e-3, grade=.2)),
    [1e6, 1e8, 1e10], materials={'substrate': material},
    conductor={'kind': 'perfect'}, length=.01,
)
saved = document.dumps()
result = TransmissionLineDocument.loads(saved).analyze()
result.C, result.G, result.L, result.network.s
result.dielectric.layer_permittivity['substrate']  # read-only (3,2,2)
```

The perfect conductor selection explicitly sets R to zero. Surface-conductor
and finite-volume line models accept the same material records while preserving
their existing skin-depth, mesh and current-conservation checks. Their conductor
R and inductance calculations are unchanged. Dielectric C/G are evaluated from
the tensor field at each frequency on the same geometry mesh. The example mesh
is an input, not a convergence claim for arbitrary designs.

`dispersive_line` accepts principal-axis objects in its `materials` mapping.
Unspecified layers retain their scalar defaults; scalar and tensor regions can
coexist. Scalar coefficients become scalar times identity only within a tensor
solve. `DielectricSweep.layer_permittivity` preserves the original sampled form:
scalar `(F,)` or tensor `(F,2,2)`, copied and read-only. Vacuum C0 and the external
quasi-TEM inductance relation remain unchanged. A tilted material can break a
pair's exchange symmetry; it does not automatically support even/odd propagation.

## Versioned material contract

The scalar `sipi.dielectric/1` format is unchanged. Principal-axis records use
`sipi.dielectric/2`, `kind: "principal-axes"`, and exactly these parameter keys:

```python
from sipi.dielectric import dielectric_to_dict, dielectric_from_dict

record = dielectric_to_dict(material)
assert record['schema'] == 'sipi.dielectric/2'
assert set(record['parameters']) == {'axis1', 'axis2', 'angle_rad'}
assert record['parameters']['axis1']['schema'] == 'sipi.dielectric/1'
restored = dielectric_from_dict(record)
```

Both axis values are complete scalar `/1` records, including all constructor
fields. Unknown/missing keys, booleans/nonfinite angles, unsupported or nested
axis models are rejected. Table axes retain their positive-frequency bounds;
out-of-range samples fail before meshing. The existing transmission-line and
volume-line schemas embed the new **material** version. Existing assembly,
network transformation and circuit documents preserve and replay those inputs;
older readers reject the new nested material schema.

`Layer`, template `eps_r`, geometry JSON, impedance-study JSON and width-goal
documents still have scalar material inputs. Apply tensor overrides through
the frequency-line material mapping; `section.analyze()` alone uses the scalar
section defaults. Browser/portable interfaces have not been connected here.

## Validation

```sh
python -m pytest -q -s tests/sipi/test_principal_dielectric.py tests/sipi/test_tensor_electrostatics.py
```

- Rotation/eigenvalue invariants, axis swap plus π/2, isotropic reduction,
  strict schema replay and pre-mesh rejection are checked. Equal-axis models
  reproduce scalar C/G/L/R within relative `1e-12` and S within absolute `1e-10`.
- Aligned layered parallel plates agree with the independent complex series
  capacitance `eps0 W / sum(h/eps_yy(f))` within relative `1e-9`.
- For proportional Debye axes `eps=A*k(f)` in transformed elliptic coax,
  `C=2*pi*eps0*sqrt(det A)*k(f)/ln(b/a)`. Radial/angular refinement
  16/64 → 32/128 → 64/256 requires decreasing error, order ≥1.5 and final error
  below 0.1%. The outer electrode is a physical boundary.
- A mixed scalar/tensor coupled microstrip at 1 MHz/100 MHz/10 GHz is compared
  to independent scikit-fem 12.0.2 complex tensor assembly, maximum relative C
  difference `1e-9`. Separate 4→1 μm edge refinement and doubled box/air sizes
  each require maximum relative complex-C entry changes below 1%.
- Saved perfect/surface and volume lines, assembly, reference transformation
  and driven circuits retain their inputs and existing extraction contracts.

These checks establish numerical behavior for the documented problems. They do
not validate a measured laminate, a general frequency-varying eigenbasis, 3D
transitions, full-wave propagation or a new platform. Causal constituent models
alone do not certify time-domain causality of a sampled network.

[Scalar materials](dielectrics.md) · [Mesh tensor API](tensor_electrostatics.md) ·
[Saved line](line_model.md) · [Volume line](volume_line.md) ·
[한국어](../../locales/ko/pages/packages/sipi/principal_dielectrics.md)
