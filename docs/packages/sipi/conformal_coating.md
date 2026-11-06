# Normal-thickness coating on surface traces

[Coplanar normal-thickness films](conformal_coplanar.md) cover finite grounds with or without a backing plane.

`conformal_coated_microstrip` and `coupled_conformal_coated_microstrip` add a
dielectric film to a grounded substrate and one or two surface traces. The film
has constant thickness normal to each straight face; adjacent offset faces meet
at miters. This is an idealized cross-section, not a measured deposition profile.

```python
from sipi import coupled_conformal_coated_microstrip, CrossSectionDocument

section = coupled_conformal_coated_microstrip(
    width=.5e-3, gap=.3e-3, substrate_height=.5e-3, eps_r=4,
    thickness=35e-6, top_width=.4e-3, tan_delta=.01,
    coating_thickness=20e-6, coating_eps_r=3.5, coating_tan_delta=.02,
    air_height=4e-3, box_width=8e-3)
document = CrossSectionDocument(section,
    mesh=dict(edge_size=4e-6, far_size=.25e-3, grade=.2))
restored = CrossSectionDocument.loads(document.dumps())
line = restored.analyze()
assert line.C.shape == (2, 2)
```

All lengths are metres. `coating_thickness=d` is positive and measured normal
to the substrate plane, trace top and sloping sides. It differs from the
existing planar `coating_height`, which includes copper height. Trace thickness
may be zero; `top_width` may equal or be smaller than `width`. Overhangs are
rejected. Pair `gap` is the bottom-edge signal spacing. The bottom plane is
grounded; top and side boundaries are open truncations of the exterior.

The substrate extends to height h, the plane film to h+d, and the highest film
point to h+t+d. `air_height` is the clearance above that highest point; its
default is 10h+t. Default box widths follow the corresponding bare template.
Explicit outer dimensions are recommended for convergence studies. A lateral
film outside the box is rejected rather than clipped. Heights that cannot be
represented separately in floating point are also rejected.

The generated template also requires every positive film, air, layer and metal
feature to exceed `1e-12 * max(box_width, total_height)`, matching the section's
placement scale. Zero copper thickness remains an explicit supported limit.
This rejects unresolved air slits before automatic meshing. Union seams lose
only exactly collinear vertices (`simplify(0)`); a positive gap is never snapped
closed. Resolvable thin features can still require expensive meshes.

For t>0 and side slope s=(width-top_width)/(2t), the raised film envelope is
the trace trapezoid shifted upward by d and widened at both sides by
δ=d/(sqrt(1+s²)+s). Its union with the plane film gives one simple region named
`coating`. Overlapping pair films become the same dielectric; no enclosed air
pocket is introduced. Metal has priority over the dielectric region during
meshing. For nonoverlapping envelopes, physical film area is Wd+Σ2δt, where W is
the box width. At t=0 the construction reduces to the existing flat film.

## Saving, materials, tolerances and goals

The substrate and air remain layers; coating is a local dielectric region.
[Cross-section JSON v3](polygon_sections.md) preserves its polygon exactly.
Existing transmission-line and volume-line documents accept the section, and
`materials={'coating': model}` can select a scalar or principal-axis material.
Save the complete line input to retain that override.

Both template names work in [saved studies](study.md) and [saved goals](design.md).
Sample `coating_thickness` with other geometry dimensions; correlated normal
sampling retains failures. The paired template supports fixed signal pitch in
studies and uses `z_diff`; the single template uses `z0`. Fixed-frequency
[material studies and goals](material_impedance.md) retain their existing real
quasi-static impedance definition and symmetry restrictions. They do not target
the complex characteristic matrix. No JSON schema field or older template
meaning changes; readers predating these names reject them.

## Validation and limits

The 41 new Linux tests use Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1,
Shapely 2.2.0 and test-only scikit-fem 12.0.2. Acceptance criteria were set
before implementation. They check independent film area/normal-distance
identities, reflection, meeting films, zero-thickness and air-equivalent limits
(0.5%), JSON replay, correlated geometry sampling, material overrides, volume
extraction and invalid geometry. Same-mesh independent complex P1 assembly
agrees within 1e-9 relative (observed maximum below 5e-15).

For the example geometry and its single-line counterpart, mesh refinement from
edge 4 to 1 µm, far .25 to .125 mm and grade .2 to .1 changes complex C by
0.256% / 0.689% (single/pair). Separately doubling the fine-mesh air and box
dimensions changes it by 0.196% / 0.647%. Each is below the preregistered 1%
gate; these are separate numerical checks, not a measured accuracy guarantee.

Saved rectangular-trace width goals at 60 Ω single / 100 Ω differential give
widths .69375 / .553125 mm. Requested/refined residuals are
(.2424, .3332) Ω and (−.3764, −.1519) Ω, each within the 1 Ω target tolerance.
The tests also verify dielectric-increase monotonicity and positive loss.

Rounded corners, menisci, overhanging traces, trapped air and process-dependent
film thickness are unsupported. Independently refine thin films, metal corners
and the exterior for each new geometry. No new runtime dependency or binary is
bundled; the existing Shapely and independent-test license notices still apply.
This validation does not establish Windows executable behavior or 3D accuracy.

[한국어](../../locales/ko/pages/packages/sipi/conformal_coating.md)
