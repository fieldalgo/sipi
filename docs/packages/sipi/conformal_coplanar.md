# Normal-thickness films on coplanar traces

Four templates extend the [mitered normal-thickness film](conformal_coating.md)
to finite coplanar grounds. Every signal and ground trace receives the film;
only signals may taper. There is no central ground between paired signals.

| Template | Signals | Backing plane |
|---|---:|---|
| `conformal_coated_grounded_coplanar` | 1 | Ground |
| `coupled_conformal_coated_grounded_coplanar` | 2 | Ground |
| `conformal_coated_unbacked_coplanar` | 1 | None |
| `coupled_conformal_coated_unbacked_coplanar` | 2 | None |

```python
from sipi import coupled_conformal_coated_unbacked_coplanar, CrossSectionDocument

section = coupled_conformal_coated_unbacked_coplanar(
    width=.5e-3, gap=.3e-3, ground_gap=.2e-3, ground_width=1e-3,
    substrate_height=.5e-3, eps_r=4, tan_delta=.01,
    thickness=35e-6, top_width=.4e-3,
    coating_thickness=20e-6, coating_eps_r=3.5, coating_tan_delta=.02,
    air_height=6e-3, lower_air_height=6e-3, box_width=12e-3)
document = CrossSectionDocument(section,
    mesh=dict(edge_size=4e-6, far_size=.25e-3, grade=.2))
restored = CrossSectionDocument.loads(document.dumps())
line = restored.analyze()
assert line.C.shape == (2, 2)
```

Lengths are metres. Single-line `gap` is signal-to-ground bottom-edge
clearance. For pairs, `gap` separates the signals and `ground_gap` separates
each outer signal edge from its ground. `ground_width` is the physical finite
width of each ground; it is not silently replaced by an infinite ground.
Signals and rectangular grounds share `thickness`. Signal `top_width` cannot
exceed `width`. All dimensions retain the bare coplanar template meanings.

`coating_thickness` is normal film thickness, not a planar fill height.
Straight offset faces meet at miters; contacting envelopes merge as one local
region named `coating`. The film covers the substrate top and all trace faces.
It does not coat the bottom of the substrate. Metal has priority in meshing.
No overhang, rounded corner, meniscus, trapped air or deposition process is
modeled. Film outside `box_width` is rejected rather than clipped.

Upper `air_height` starts above the highest film point and defaults to 10h+t,
where h is substrate height and t is copper thickness. In unbacked sections,
positive `lower_air_height` (default 10h) moves the entire substrate, all traces
and the local film together. All exterior boundaries are open, with only the
two coplanar grounds defining the reference. Grounded variants retain the
bottom ground plane. Explicit outer dimensions are recommended for studies.

The [film resolution rule](conformal_coating.md) also applies after lower-air
translation. Unresolved positive slits, thin metal/film and air layers fail
before meshing; exactly merged seams preserve the geometry without snapping.

## Saved inputs and studies

Geometry uses [cross-section v3](polygon_sections.md), with `substrate`/`air`
layers (plus `lower_air` for unbacked variants) and the `coating` local region.
Existing [line inputs](line_model.md) can override `coating` with scalar or
[principal-axis materials](principal_dielectrics.md). Save the whole input to
preserve material overrides.

All four names support [saved studies](study.md) and [width goals](design.md).
The pair names use `z_diff`, others `z0`. Pair fixed pitch keeps signal centres
fixed; grounds still move with the outer signal edges to retain `ground_gap`.
Correlated width/film-thickness sampling, invalid-row retention and
[fixed-frequency material contracts](material_impedance.md) are unchanged.
This adds template names without changing existing schema fields. Older
readers reject unknown names. Existing bare/planar unbacked section JSON is
unchanged by preservation of the newly introduced local regions.

## Validation and limits

The 72 new tests passed on Linux with Python 3.12.14, NumPy 2.5.4,
SciPy 1.18.1, Shapely 2.2.0 and test-only scikit-fem 12.0.2. The largest
independent complex-C difference was below 6e-15. Fine vacuum panel-reference
errors were at most 0.127% / 0.158% / 0.184% / 0.168% in the table order below.
Another 41 geometry-resolution tests cover all six normal-film templates:
unresolved positive gaps and dimensions fail before meshing, while exact
contact/overlap cleanup preserves the polygon with zero symmetric-difference
area. Zero copper thickness and a resolved positive air slit remain supported.

The tests compare thin vacuum sections with independent image-charge panels
(grounded) or neutral logarithmic Green-function panels (unbacked). Reference
panel refinement must change impedance by less than 0.3%; refined FEM error
must improve and remain below 2%. Separate complex P1 assembly in test-only
scikit-fem must agree with extracted C within 1e-9. These checks supplement
exact film area, side-normal distances, ground coverage and reflection.

For the example dimensions, the preregistered mesh study changes edge 4→1 µm,
far .25→.125 mm and grade .2→.1. The outer study separately doubles box width
and every exterior air height on the fine mesh. Maximum relative complex C
entry changes are:

| Section | Mesh | Outer domain |
|---|---:|---:|
| Grounded single | 0.3433% | 0.0269% |
| Grounded pair | 0.7368% | 0.1746% |
| Unbacked single | 0.4016% | 0.0038% |
| Unbacked pair | 0.4704% | 0.0117% |

Each is below the 1% gate. Zero-thickness planar and air-equivalent limits use
a separate 0.5% gate. Saved 60 Ω single / 100 Ω pair goals require both the
requested and refined mesh residuals within 1 Ω. JSON replay, scalar/principal
material equivalence, correlated geometry studies and invalid dimensions are
tested separately. These are numerical acceptance criteria, not guaranteed
manufacturing or measured accuracy. New geometries need their own convergence.
No new shared solver, runtime dependency, bundled binary or platform claim is
introduced; existing third-party notices apply.

Rectangular-signal saved width goals (same dimensions otherwise) produced:

| Section and target | Width, mm | Requested residual, Ω | Refined residual, Ω |
|---|---:|---:|---:|
| Grounded single, 60 Ω | .3875 | −.2555 | −.1011 |
| Grounded pair, 100 Ω | .434375 | −.2660 | −.0134 |
| Unbacked single, 60 Ω | .7000 | +.6084 | +.7682 |
| Unbacked pair, 100 Ω | .54375 | −.1219 | +.1436 |

These are bounded numerical goals, not manufacturing tolerance guarantees.

[한국어](../../locales/ko/pages/packages/sipi/conformal_coplanar.md)
