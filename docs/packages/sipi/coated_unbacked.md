# Planar-coated coplanar sections without backing ground

`coated_unbacked_coplanar` and `coupled_coated_unbacked_coplanar` place one or two
signals between finite coplanar grounds in a full-width planar coating. A finite
substrate has air underneath. All outer boundaries are open (insulating); only
the two ground traces define the electrical reference. The existing geometry,
meshing and electrostatic solver contracts are reused.

```python
from sipi import coupled_coated_unbacked_coplanar, CrossSectionDocument
section = coupled_coated_unbacked_coplanar(
    width=.5e-3, gap=.3e-3, ground_gap=.2e-3, ground_width=1e-3,
    substrate_height=.5e-3, eps_r=4, tan_delta=.01,
    coating_height=.1e-3, coating_eps_r=3.5, coating_tan_delta=.02,
    thickness=35e-6, top_width=.4e-3,
    lower_air_height=6e-3, air_height=6e-3, box_width=12e-3,
)
saved = CrossSectionDocument(section).dumps()
restored = CrossSectionDocument.loads(saved)
```

Lengths are metres. Single-line `gap` is signal-to-ground clearance; paired
`gap` is signal-to-signal clearance and `ground_gap` is the outer clearance.
Dimensions use bottom signal edges. There is no central ground. Grounds are
rectangular with the same thickness as the signals; only signals may taper.
`ground_width` is an actual finite width, not an infinite-ground approximation.

Layers are `lower_air`, `substrate`, `coating`, `air`. `coating_height` starts at
the substrate surface, includes copper height, and must exceed `thickness`.
Upper `air_height` starts **above the coating** and can be less than copper
thickness; it defaults to ten substrate heights plus copper thickness. Lower
air defaults to ten substrate heights. Both air heights and box width require
outer-domain convergence. Substrate and coating span the box: lateral board
edges, conformal/meniscus masks and 3D return-current transitions are not modeled.

Both template names work in `ImpedanceStudyDocument` and
`ImpedanceDesignDocument`, using `z0` for a single signal or `z_diff` for the pair.
All four samplers retain failed rows. Fixed pitch holds signal centers and
derives `gap=pitch−width`; grounds move to preserve each row's `ground_gap`.
Invalid bounded corners are rejected, while invalid normal draws remain failures.
Existing JSON schemas retain their meanings; older readers reject the new names.
Record the exact commit and wheel hash for unreleased versions.

## Independent checks and scope

Vacuum, zero-thickness strips use the independent neutral free-space logarithmic
charge panels from [unbacked sections](unbacked_coplanar.md). The finite-ground
reference is not replaced by an infinite-ground formula. Panel 80→160 modal
changes must be <=0.3%; fine FEM errors <=2% and smaller than coarse errors;
doubling box width and both air heights changes modes by <=1%.

Finite tapered copper with substrate eps=4 and coating eps=3.5 uses independent
scikit-fem 12.0.2 complex P1 energy on the same mesh (relative C difference <=1e-9).
Separate modal mesh changes must be <=0.5%, outer changes <=1%. Setting coating
eps=1 and loss=0 reproduces the plain unbacked section with upper air increased
by coating height within 0.5%; the positive coating increases capacitance.
Material areas subtract the actual metal, and open bottom, layer positions,
JSON replay, thin upper-air clearance, four samplers, fixed pitch and invalid
samples are checked. Saved width goals use independent vacuum targets: width
within 4%, requested and refined impedance residuals each <=1 ohm.

Same-mesh agreement is not mesh convergence. These geometry-specific checks do
not establish measured-board, radiation, 3D via/stub or platform accuracy. Use
the existing material and quasi-TEM validity limits.

[Ground-backed coating](coated_coplanar.md) · [Studies](study.md) · [Design](design.md) ·
[한국어](../../locales/ko/pages/packages/sipi/coated_unbacked.md)
