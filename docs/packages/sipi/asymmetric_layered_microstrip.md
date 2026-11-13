# Unequal surface pair above two substrate layers

[한국어](../../locales/ko/pages/packages/sipi/asymmetric_layered_microstrip.md)

`asymmetric_coupled_layered_microstrip` places two independently sized copper
traces above a lower and upper substrate. Both substrate heights exclude copper;
the signal bottoms meet their summed height. Positive is left, negative is right.
The full bottom-width span is centred, and `gap` separates the bottom edges.
Each signal has its own bottom width, thickness and optional centred top width.
The bottom plane is grounded; the top and sides are open. Air height includes
copper and must exceed the larger thickness. The automatic air height is ten
substrate heights plus that thickness; automatic box width is the larger of
20 substrate heights and four complete signal spans.

```python
from sipi import asymmetric_coupled_layered_microstrip, CrossSectionDocument

section = asymmetric_coupled_layered_microstrip(
    left_width=.4e-3, right_width=.7e-3, gap=.3e-3,
    left_thickness=25e-6, right_thickness=45e-6,
    left_top_width=.32e-3, right_top_width=.55e-3,
    lower_height=.3e-3, upper_height=.7e-3,
    lower_eps_r=3., upper_eps_r=5.,
    lower_tan_delta=.01, upper_tan_delta=.03,
    box_width=.02, air_height=.01,
)
document = CrossSectionDocument(section,
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
line = document.analyze()
print(line.C, line.L, line.z_diff_forward)
```

`z_diff_forward` is the real lossless forward-current launch diagnostic at
`Icommon=0`. Unequal conductors do not imply independent even/odd eigenmodes.
The geometry does not infer conductor resistance, roughness, frequency-dependent
materials or 3D transitions. Constant loss tangent contributes to the extracted
complex electrostatic capacitance; the launch diagnostic excludes that loss.
Save geometry with `CrossSectionDocument`. Template/study/design registration
and a dedicated editable form are separate integration steps.

Validation separately checks the explicit geometry, independent scikit-fem
12.0.2 complex and vacuum energy with height-based material assignment, matrix
reciprocity/positivity, vacuum identity, equal-pair geometry and a uniform-substrate
limit. Numerical gates are registered before measurement: normalized independent
matrix difference at most 1e-10, mesh changes in C and the launch diagnostic at
most 1%, separate box and air doubling changes at most 0.5%, and a homogeneous
substrate comparison at most 0.5%. These apply to the documented representative
geometry, not arbitrary boards or measured accuracy. A direct left-width target
also requires both original and refined meshes within the requested tolerance.

Run `PYTHONPATH=src OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q tests/sipi/test_asymmetric_layered_microstrip.py`
with the qualified reference environment. Keep failed trials alongside the
accepted artifact; passing a chosen recipe does not establish universal convergence.
