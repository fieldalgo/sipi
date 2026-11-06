# Planar-coated coplanar sections

`coated_grounded_coplanar` and `coupled_coated_grounded_coplanar` put one or two
surface signals between two finite grounded conductors. All conductors are
covered by the same flat, full-width dielectric layer. This prescribed profile
does not predict a conformal mask, meniscus or fabrication process.

```python
from sipi import coupled_coated_grounded_coplanar, CrossSectionDocument
section = coupled_coated_grounded_coplanar(
    width=.5e-3, gap=.3e-3, ground_gap=.2e-3, ground_width=1e-3,
    substrate_height=.5e-3, eps_r=4, thickness=.035e-3, top_width=.4e-3,
    coating_height=.1e-3, coating_eps_r=3.5, coating_tan_delta=.02,
    air_height=6e-3, box_width=12e-3,
)
saved = CrossSectionDocument(section).dumps()
restored = CrossSectionDocument.loads(saved)
```

All lengths are metres. In the single-line template, `gap` separates each signal
bottom edge from a ground. In the pair, `gap` separates signal bottom edges and
`ground_gap` separates each outer signal edge from its ground. There is no central
ground. `ground_width` is a physical finite width, not an infinite-ground setting.
Signals may taper; grounds remain rectangular with the same thickness and base
height as the signals. `coating_height` starts at the substrate and **includes
copper**, so it must exceed `thickness`. `air_height` starts above the coating.
The bottom is grounded; top and sides retain natural boundary approximations.
Converge the outer domain independently of the mesh.

Layer names are `substrate`, `coating`, `air`; permittivity and loss tangent of
substrate and coating are independent. Existing section JSON preserves all
geometry. Both names work in `ImpedanceStudyDocument` and
`ImpedanceDesignDocument`, using `z0` for one signal and `z_diff` for the pair.
Four sampling methods retain their existing semantics. Fixed pitch on the pair
holds signal centers, derives gap=pitch−width and moves grounds to preserve each
row's `ground_gap`. Bounded invalid corners are rejected; invalid normal draws
remain failed rows without resampling. Older readers reject these template names;
record the SIPI version alongside inputs.

`tests/sipi/test_coated_coplanar.py` separates these acceptance checks:

- Zero-thickness vacuum, finite grounds: independent image-charge panel integral;
  80→160 panel changes <=0.3%, fine modal impedance error <=2% and decreasing with
  mesh refinement, doubled outer-domain changes <=1%.
- Finite tapered copper with substrate eps=4/coating eps=3.5: same-mesh complex
  P1 energy comparison against scikit-fem 12.0.2 at relative <=1e-9. This is
  assembly evidence. Separate mesh changes <=0.5%, domain changes <=1% and
  eps=1 coating/uncoated reduction <=0.5% establish the sampled numerical limits.
- Exact coating area minus metal, strict section JSON replay, four samplers,
  fixed signal pitch and invalid samples. Saved width goals use independent
  vacuum targets: recovered width within 4%, both mesh residuals <=1 ohm.

These geometry-specific checks do not establish measured-board accuracy or a
universal error bound. [Manufacturing](manufacturing_sections.md) ·
[Studies](study.md) · [Design](design.md) ·
[한국어](../../locales/ko/pages/packages/sipi/coated_coplanar.md)
