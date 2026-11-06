# Coupled grounded coplanar pair

**English** | [한국어](../../locales/ko/pages/packages/sipi/coupled_coplanar.md)

`coupled_grounded_coplanar` returns an ordinary `CrossSection` with two equal-width
surface signals, two outer finite coplanar grounds and a bottom ground plane.
There is no ground between the signals. It uses the existing quasistatic FEM;
it does not add a new field solver or a high-frequency full-wave model.

```python
from sipi import CrossSectionDocument, coupled_grounded_coplanar

section = coupled_grounded_coplanar(
    width=.5e-3, gap=.3e-3, ground_gap=.2e-3, ground_width=1e-3,
    substrate_height=.5e-3, eps_r=4, thickness=.035e-3,
    air_height=6e-3, box_width=12e-3)
doc = CrossSectionDocument(section,
    mesh=dict(edge_size=2e-6, far_size=.125e-3, grade=.15))
restored = CrossSectionDocument.loads(doc.dumps())
line = restored.analyze()
print(line.even_odd()['z_diff'])
```

All lengths are metres. `gap` is between the two signal bottom edges;
`ground_gap` is between each outer signal bottom edge and its adjacent ground.
`ground_width` is the physical width of each outer ground. The signal centres
are `±(width + gap)/2`; the ground centres are
`±(width + gap/2 + ground_gap + ground_width/2)`. Signal names are ordered
`positive`, `negative`; the other traces are `ground_left`, `ground_right`.
Only the two signals form ports; all reference conductors are held at zero volts.

Signals and grounds share `thickness` (default 0). `top_width` tapers signals
only; grounds remain rectangular. Gaps are defined at the bottom faces, so an
outward taper reduces actual clearance. Overlapping/touching conductors and
out-of-box geometry are rejected before meshing. Optional `tan_delta` applies
to the substrate; the upper layer is air. Thickness, loss and taper follow the
existing template and document contracts.

The default air height is `10*h+t`. Default box width is
`max(20*h, 4*w, 2*w+gap+2*ground_gap+2*ground_width+4*h)`.
Top and side walls are open (zero normal displacement), a finite-domain
approximation to open space. Check mesh, box and air dimensions separately.
Finite `ground_width` is part of the physical geometry: enlarge it only when
investigating a larger ground or an infinite-ground approximation.

## Saved inputs, tolerance and design

The ordinary cross-section JSON stores all four traces and their ground flags;
no new cross-section schema is needed. `sipi.impedance-study/1` accepts template
`coupled_grounded_coplanar`, with `quantity='z_diff'`. Sweep, corners, uniform and
correlated normal sampling use the existing contracts and preserve failed rows.
Older study readers reject the new template name. Record the engine version.

For fixed-pitch studies, `fixed_pitch_m = width + gap` preserves the **signal**
centres. The outer grounds follow the outer signal edges to retain each row's
`ground_gap`; they do not stay at fixed coordinates. This matters when comparing
width tolerances with a manufactured layout in which ground edges are fixed.
Use explicit `CrossSection` geometry for other placement constraints.

`seek_impedance(lambda width: coupled_grounded_coplanar(...), bounds, target,
quantity='z_diff', ...)` reuses bounded design and its separate refined-mesh
confirmation. The target must be bracketed and both mesh residuals must meet the
specified tolerance. No generic monotonicity or manufacturing-yield guarantee is
made. See [design](design.md) and [studies](study.md).

## Independent reference and acceptance criteria

`tests/sipi/test_coupled_coplanar.py` includes a test-only integral calculation
that does not use SIPI geometry, meshing or solvers. For vacuum, infinitely thin
coplanar strips at height `h` above an infinite ground plane, the image-charge
Green kernel is

`G(x,x') = log(sqrt((x-x')² + (2h)²)/abs(x-x')) / (2*pi*epsilon_0)`.

Piecewise constant charge panels use midpoint collocation and an analytic panel
integral. Endpoints cluster with cosine spacing to resolve edge singularities.
Strip potentials give strip charges and the capacitance matrix; outer strips
have zero potential. In this homogeneous TEM case,
`Z_even/odd = 1 / (c * (C11 ± C12))`. This reference assumes infinite open space
above the bottom plane, independently of the FEM's finite top and side walls.
The primitive is also checked against independent adaptive quadrature, including
the logarithmic singularity. Reciprocity, positive capacitance and scale
invariance are checked separately.

Criteria fixed before the comparison:

- 80 to 160 panels per strip: modal impedance change below 0.3%.
- FEM coarse to fine: each modal error decreases; fine error below 2%.
- Doubling box width and air height: modal impedance change below 1%.
- Width design: target from the integral's odd-mode impedance, both FEM mesh
  residuals at most 1 ohm and inferred width within 4% of the reference geometry.

The reference case has `w=.5 mm`, signal gap `.3 mm`, ground gap `.2 mm`,
ground width `1 mm`, height `.5 mm`, relative permittivity 1 and zero thickness.
FEM box/air are `12/6 mm`, expanded to `24/12 mm`. Coarse
`(edge_size, far_size, grade) = (8 um, .25 mm, .3)` and fine
`(2 um, .125 mm, .15)` preserve all original acceptance thresholds.
Linux CPython 3.12.14 results: integral even/odd `131.91940 / 86.22839 ohm`,
fine FEM `132.02692 / 85.91806 ohm`, relative errors `0.0815% / 0.3599%`;
expanded domain `131.68938 / 85.91612 ohm` (changes `0.256% / 0.0023%`).
These are evidence for the stated ideal case, not measured-board validation,
finite-thickness accuracy or a blanket error bound for arbitrary dielectrics.
Finite copper and dielectric cases have geometry, input and API regression
coverage; their accuracy still requires the relevant mesh/material studies.

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python -m pytest -q -s tests/sipi/test_coupled_coplanar.py
```
