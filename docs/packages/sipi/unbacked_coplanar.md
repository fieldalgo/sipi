# Coplanar sections without a backing ground plane

`unbacked_coplanar` and `coupled_unbacked_coplanar` place one or two surface
signals between two finite coplanar grounds. A finite substrate has air below
and above it. All outer boundaries are open (insulating); only the two ground
traces define the electrical reference. The existing `CrossSection` solver and
JSON contracts are reused.

```python
from sipi import coupled_unbacked_coplanar, CrossSectionDocument
section = coupled_unbacked_coplanar(
    width=.5e-3, gap=.3e-3, ground_gap=.2e-3, ground_width=1e-3,
    substrate_height=.5e-3, eps_r=4, thickness=35e-6, top_width=.4e-3,
    tan_delta=.01, lower_air_height=6e-3, air_height=6e-3, box_width=12e-3,
)
saved = CrossSectionDocument(section).dumps()
restored = CrossSectionDocument.loads(saved)
```

Lengths are metres. Single-line `gap` is signal-to-ground clearance; pair `gap`
is signal-to-signal clearance, with `ground_gap` on the outside. Clearances use
bottom signal edges. There is no central ground. Both grounds are rectangular
with the signal thickness; only signals may taper. `ground_width` is a physical
finite width, not an outer-domain setting or an infinite-ground approximation.

Layer names are `lower_air`, `substrate`, `air`. Metal sits at
`lower_air_height+substrate_height`. Lower air defaults to ten substrate heights;
upper air defaults to ten substrate heights plus metal thickness. Upper air
starts at the substrate surface and must leave clearance above the copper.
Both air heights and box width need convergence; they are numerical truncation
parameters, not manufacturing dimensions. The substrate spans the box width;
lateral board edges and three-dimensional ends are not modeled.

Both names work in `ImpedanceStudyDocument` and `ImpedanceDesignDocument`, with
`z0` for one signal and `z_diff` for the pair. Four samplers retain failures.
Fixed pitch holds signal centers, derives gap=pitch−width, and moves grounds
to preserve each row's `ground_gap`. Invalid bounded corners are rejected;
invalid normal draws remain failed rows. Older readers reject the new names.
Record the version and, for unreleased builds, source commit and wheel hash.

## Independent references and acceptance

`tests/sipi/test_unbacked_coplanar.py` uses free-space −log Green-function panels
for zero-thickness vacuum strips. An augmented equation enforces total charge
zero and solves an unknown distant common potential: the far boundary is not
grounded. Analytic panel primitives are checked by SciPy quadrature; reciprocity,
neutrality, gauge/scale invariance and 80→160-panel modal changes <=0.3% are required.

For signal [−a,a] and grounds ±[b,d], a second reference uses the complex field
proportional to `1/sqrt((z²−a²)(z²−b²)(z²−d²))`. Normal-field charge and slot-voltage
integrals give `Z=K(1−k²)/(4 eps0 c0 K(k²))`,
`k=(a/b)*sqrt((d²−b²)/(d²−a²))`. K takes the elliptic **parameter**, as in
`scipy.special.ellipk`. Endpoint-regularized quadrature must match that formula
within relative 1e-12 and the 160-panel result within 0.1%. A separate large-ground
panel case matches the infinite-ground limit within 1%; the infinite-ground
formula is never the finite-ground FEM acceptance reference.

Fine vacuum modal errors must be <=2% and decrease with refinement; doubling
the box and both air heights must change modes by <=1%. Finite tapered copper
with substrate eps=4 uses scikit-fem 12.0.2 complex P1 energy on the same mesh
(relative <=1e-9), plus separate modal mesh changes <=0.5% and outer changes <=1%.
Same-mesh agreement is not convergence evidence. Exact material areas, open
boundaries, JSON replay, four samplers, fixed pitch and invalid samples are
checked. Saved width goals use independent free-space targets: width within 4%,
requested and refined residuals <=1 ohm.

These geometry-specific checks do not establish measured-board accuracy,
radiation, 3D return-current transitions or via/stub behavior. Existing material,
mesh and quasi-TEM limits remain.

[Ground-backed pair](coupled_coplanar.md) · [Studies](study.md) · [Design](design.md) ·
[한국어](../../locales/ko/pages/packages/sipi/unbacked_coplanar.md)
