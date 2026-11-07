# Broadside pair with three dielectric layers

[한국어](../../locales/ko/pages/packages/sipi/layered_broadside.md)

`layered_broadside_stripline` places two equal-width rectangular conductors
between grounded outer planes. The lower, inter-conductor and upper dielectric
layers have independent relative permittivity and loss tangent. A signed lateral
offset and different outer clearances are allowed. This is a longitudinally
uniform quasi-static cross-section, not a via, pad or layer transition model.

```python
from sipi import layered_broadside_stripline, CrossSectionDocument

parameters = dict(width=.35e-3, gap=.15e-3, lower_height=.25e-3,
    upper_height=.45e-3, lower_eps_r=3., gap_eps_r=4., upper_eps_r=5.,
    thickness=35e-6, offset=.12e-3, lower_tan_delta=.01,
    gap_tan_delta=.02, upper_tan_delta=.03, box_width=6e-3)
mesh = dict(edge_size=8e-6, far_size=.25e-3, grade=.3)
section = layered_broadside_stripline(**parameters)
document = CrossSectionDocument(section, mesh=mesh)
restored = CrossSectionDocument.loads(document.dumps())
assert restored.dumps() == document.dumps()
line = restored.analyze()
assert line.z_diff_forward > 0
```

Lengths are metres. `width`, `thickness`, `gap`, `lower_height` and `upper_height`
are strictly positive. The two metal thicknesses and widths are equal; taper is
not part of this template. Heights here are **outer metal-face clearances**,
excluding copper, and `gap` is the inner metal-face separation:

| From bottom to top | Vertical span | Material name |
|---|---|---|
| Bottom ground to lower trace bottom | `lower_height` | `lower` |
| Lower positive metal | `thickness` | hole in lower layer |
| Lower metal top to upper metal bottom | `gap` | `gap` |
| Upper negative metal | `thickness` | hole in upper layer |
| Upper metal top to top ground | `upper_height` | `upper` |

Total plane spacing is `lower_height + upper_height + gap + 2*thickness`.
The three layer thicknesses are `lower_height+thickness`, `gap` and
`upper_height+thickness`. Dielectric interfaces meet the inner metal faces.
The positive trace has x=-offset/2 and negative trace x=+offset/2. `offset` is
finite and signed; zero aligns the two traces. No material averaging occurs.
The finite side walls are insulated; increase `box_width` and check convergence.
If omitted, width is `max(12*total_height, 4*(width+abs(offset)))`. This default
and the automatic mesh are starting points, not a convergence certificate.

## Impedance, loss and symmetry

The full C, C0, L and dielectric-loss matrices retain asymmetry. Saved study and
design inputs require `quantity="z_diff_forward"`: lossless forward Vdiff/Idiff
with zero common current, obtained from the positive-definite characteristic
matrix. It does not assume independent common/differential eigenmodes.
The scalar excludes resistance and dielectric loss, as other real impedance
diagnostics do; use existing frequency-dependent line/network APIs for those.
Calling `even_odd()` on an asymmetric result still fails its existing symmetry
check. Symmetric outer clearances/materials reduce to the usual symmetric pair;
equal materials everywhere reduce to the homogeneous broadside template.

All three named layers can use the existing scalar or principal-axis material
overrides and material-variable bindings. Layer loss tangents describe existing
complex electrostatics, not empirical validation of a material data sheet.

## Saved studies, yield and goals

```python
from sipi.study import ImpedanceStudyDocument
from sipi.yield_assessment import ImpedanceYieldDocument
from sipi.execution import execute_saved, normalize_saved

study = ImpedanceStudyDocument("layered_broadside_stripline", parameters,
    quantity="z_diff_forward", mesh=mesh,
    sampling=dict(kind="uniform", count=2, seed=17,
        variables=[dict(name="offset", lower=-.1e-3, upper=.1e-3)]))
saved = normalize_saved(study.dumps())
report = execute_saved(ImpedanceYieldDocument(study, minimum=40., maximum=60.).dumps(),
                       max_evaluations=2)
assert len(report["result"]["rows"]) == 2
```

This is a small interface example, not a sample size sufficient for yield
certification. Study/1–4, [yield assessment](yield.md), [fixed candidate
selection](yield_design.md) and existing saved impedance goals reuse the same
template. Uniform/normal offset may cross zero; normal samples with invalid
dimensions/materials remain failed rows. Positive bounded width/gap/material
goals use `z_diff_forward` and keep the existing refined-mesh acceptance gate.
Signed search bounds are not added to the existing positive-bound goal API.
Horizontal `fixed_pitch_m` and the two-layer `fixed_plane_spacing_m` constraint
are rejected for this three-layer vertical geometry. Specify candidate
dimensions explicitly rather than silently deriving a different thickness.

The geometry uses existing cross-section/1 JSON; there is no new schema version.
Study inputs preserve the template name, all dimensions/material coefficients,
resolved mesh, sampling settings and each row's errors. Material-bound studies
also retain the actual per-row material snapshot. General three-dimensional
transitions, unequal trace widths/thicknesses and taper are outside this template.

## Validation scope

The representative offset/asymmetric case above is compared to independent
scikit-fem P1 complex and vacuum electrostatics on identical meshes, with C,
C_loss and C0 normalized differences below `1e-10`. Separate coarse/fine mesh
checks require C and forward impedance changes below 1.5%; doubling the lateral
box requires below 0.5%. These are explicit case gates, not all-input error bounds.
Tests also require positive/passive reciprocal matrices, reflected geometry
and material interchange, homogeneous broadside reduction, exact uniform
permittivity scaling on the same mesh, and a wide parallel-plate differential
limit within 5% with mesh refinement. JSON, random/material studies, unresolved
rows and a saved width goal with its independent refinement check are exercised.
No measured fabrication accuracy or new application/platform acceptance follows.
