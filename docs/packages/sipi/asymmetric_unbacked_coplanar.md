# Unequal unbacked coplanar pair

[Planar-coated unequal pair](asymmetric_coated_unbacked_coplanar.md) adds an explicit full-width film above the substrate.

`asymmetric_coupled_unbacked_coplanar` places two unequal signal traces between
finite coplanar ground traces on a finite substrate. There is **no backing
ground plane**. Lower and upper air separate the substrate from insulated
outer boundaries; the two ground traces alone define the common reference.
This is a uniform 2D section, with no central ground or exchange symmetry.

Signal widths, thicknesses and optional top widths are independent. Ground
traces share explicit `ground_width`, `ground_gap` and rectangular
`ground_thickness` (default zero); ground thickness never follows a signal.
The signal bottom span is centered, positive is left and negative right.
`gap` and `ground_gap` are bottom-edge clearances; taper/contact/clipping
checks remain in force. All lengths are metres.

The regions are `lower_air`, `substrate`, `air`. The substrate has its own
`eps_r` and `tan_delta`. Copper bottom faces lie at
`lower_air_height+substrate_height`. Upper `air_height` starts at the substrate
top, **includes copper height**, and must exceed every metal thickness.
Lower air must be positive and defaults to ten substrate heights; automatic
upper air is ten substrate heights plus the largest copper thickness.
Explicit air/box dimensions avoid these default dependencies in studies.
Ground width is a physical input; box and both air heights are separate
truncations. Enlarging a ground is not an outer-domain convergence check.

Equal signal dimensions and equal ground thickness reproduce
`coupled_unbacked_coplanar`, including automatic box size. The new name is
registered for existing saved studies and goals; no saved schema is added.
Older readers may reject the template name.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    left_thickness=35e-6, right_thickness=50e-6,
    ground_gap=.25e-3, ground_width=1.5e-3, ground_thickness=35e-6,
    box_width=12e-3, air_height=6e-3, lower_air_height=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_unbacked_coplanar', parameters,
    quantity='z_diff_forward', fixed_pitch_m=.7e-3,
    sampling=dict(kind='uniform', count=2, seed=71, variables=[
        dict(name='left_width', lower=.28e-3, upper=.32e-3),
        dict(name='ground_gap', lower=.24e-3, upper=.26e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
result = study.analyze(max_evaluations=2)
assert result.failed == 0
for row in result.rows:
    p = row.parameters
    assert abs(p['gap']+(p['left_width']+p['right_width'])/2-.7e-3) < 1e-15
    assert row.document.section.bottom == 'open'
    assert row.document.section.traces[0].y == p['lower_air_height']+p['substrate_height']
```

The forward quantity `z_diff_forward` imposes zero common current; it is not
an odd eigenmode or loaded impedance. Fixed pitch derives
`gap=pitch-(left_width+right_width)/2`, moving finite grounds to keep the
outer ground clearances. Invalid bounded geometry fails before meshing;
invalid normal samples remain failed without resampling or clipping.
Substrate material-study/4, iid yield and paired full-loss line study/2 reuse
this geometry. Full-loss studies explicitly select
`differential_forward_impedance_real`, distinct from the real electrostatic
forward quantity.

## Independent acceptance contract

For the finite fixture above, coarse `(5 um,.25 mm,.2)` to fine
`(2.5 um,.125 mm,.1)` edge/far/grade C/Z changes must be <1.5%.
On the fine mesh, box 12→24 mm, upper air 6→12 mm and lower air 6→12 mm
each require <.5%. Ground width 1.5→3 mm is reported separately as physical
sensitivity, without asserting that its effect is a numerical error.
Independent scikit-fem 12.0.2 (BSD-3-Clause) complex/vacuum P1 energy on
the same mesh checks C/C_loss/C0 within normalized 1e-10; it does not
independently construct geometry or mesh. Uniform coefficient scaling,
common loss, vacuum L and reciprocity use 1e-12; reflected conductor
permutation uses .5%.

A separate zero-thickness, all-vacuum fixture uses an independent free-space
`-log(distance)` panel Green integral with total charge zero and an unknown
common potential. It does not add an image plane or ground the distant
boundary. Explicit signal intervals [-.55,-.25], [.05,.55] mm and ground
intervals [-2.3,-.8], [.8,2.3] mm are independent of the factory.
The 80→160-panel C/Z changes must be <.3%. At box 24 mm and both air heights
12 mm, FEM `(4 um,.5 mm,.2)`→`(1 um,.25 mm,.1)` errors must decrease and
finish below 2%. Box 48 mm with both air heights 24 mm must change C/Z by
<1%. Existing independent panel tests also check neutrality, gauge,
reciprocity, scale invariance and the symmetric finite-ground elliptic limit.

The .7 mm fixed-pitch left-width target uses [.08,.85] mm, 100 ohm,
1 ohm tolerance and 30 evaluations. Requested fine mesh, automatic half
refinement, expanded box, upper air and lower air must all retain the same
width within that target tolerance. Material/full-complex replay uses 1e-10.
These explicit fixture gates do not establish measured-board, general 3D,
browser or Windows accuracy.

[Studies](study.md) · [한국어](../../locales/ko/pages/packages/sipi/asymmetric_unbacked_coplanar.md)
