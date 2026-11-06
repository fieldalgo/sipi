# Edge-coupled traces in a planar coating

`coupled_coated_microstrip` returns an existing `CrossSection`: equal-width
`positive`/`negative` traces at the substrate surface, a flat full-width coating
and air above. This is a prescribed planar profile, not a conformal mask,
meniscus or manufactured-profile prediction.

```python
from sipi import coupled_coated_microstrip, CrossSectionDocument
section = coupled_coated_microstrip(
    width=.5e-3, gap=.3e-3, substrate_height=.5e-3, eps_r=4,
    thickness=.035e-3, top_width=.4e-3, coating_height=.1e-3,
    coating_eps_r=3.5, tan_delta=.01, coating_tan_delta=.02,
    air_height=6e-3, box_width=12e-3,
)
document = CrossSectionDocument(section)
restored = CrossSectionDocument.loads(document.dumps())
```

Lengths are metres. `gap` separates bottom edges; centers are ±(width+gap)/2.
`coating_height` starts at the substrate and **includes copper**, so it must
exceed `thickness`. `air_height` starts above the coating. `top_width` changes
only signal taper. The bottom is grounded; top/sides retain natural boundary
approximations. Check outer-domain convergence separately from mesh refinement.

Layer names `substrate`, `coating`, `air` work with existing material documents.
Substrate/coating permittivity and loss are independent. Section JSON preserves
the geometry. `ImpedanceStudyDocument` and `ImpedanceDesignDocument` accept the
new name with `z_diff`. Fixed pitch derives gap=pitch−width and holds centers.
Changing metal thickness alone changes the clearance under the fixed coating
surface. Invalid bounded corners are rejected; invalid normal samples remain
failed rows. Older readers reject the new template; record the SIPI version.

Validation gates are geometry-specific, not universal accuracy guarantees:

- Zero-thickness vacuum: independent two-strip image-charge panel integral;
  80→160 panel changes <=0.3%, fine even/odd Z errors <=2% and decreasing with
  refinement, doubled outer-domain changes <=1%.
- Finite tapered copper, substrate eps=4/coating eps=3.5: independent scikit-fem
  12.0.2 complex P1 matrix on the same mesh, relative difference <=1e-9. This
  validates assembly, not mesh accuracy. Separate modal mesh changes <=0.5%,
  domain changes <=1%, eps=1 coating/uncoated reduction <=0.5% are required.
- Exact areas/interfaces, JSON replay, four samplers/fixed pitch, invalid inputs;
  saved width goal from the independent vacuum integral, width within 4% and
  requested/refined residuals <=1 ohm. No measured-board validation is inferred.

[Manufacturing](manufacturing_sections.md) · [Studies](study.md) · [Design](design.md)
