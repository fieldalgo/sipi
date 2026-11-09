# Unequal coplanar pair with a normal-thickness coating

[한국어](../../locales/ko/pages/packages/sipi/asymmetric_conformal_coplanar.md) ·
[Without lateral grounds](asymmetric_conformal_microstrip.md) · [Equal coated coplanar pair](conformal_coplanar.md)

`asymmetric_coupled_conformal_coated_grounded_coplanar` places unequal signals
between two finite rectangular coplanar grounds above a backing plane. A
normal-thickness mitered dielectric film covers the substrate and all four
conductors. There is no central ground or exchange-symmetry assumption.

Lengths are metres. Positive is left, negative is right, and the signal bottom
span is centered. gap separates signal bottom edges; ground_gap separates
outer signal bottom edges from the adjacent ground. Signal width/thickness and
narrowing top width are independent. Grounds share ground_width and an explicit
ground_thickness, which defaults to zero and is never inferred from signals.
The film uses coating_thickness normal to substrate, tops and straight sides;
meeting envelopes unite. Overhangs, enclosed air pockets, implicit clipping
and features below the existing resolution threshold reject. This prescribed
mitered profile is not a rounded-corner, meniscus or measured deposition model.

Coating is one named local dielectric region with independent permittivity and
loss. Metal takes priority inside it. air_height starts above the highest
coated signal or ground, at substrate_height+max(left_thickness,right_thickness,
ground_thickness)+coating_thickness. A resolvable positive air height is a
geometry condition, not evidence of convergence. Top/sides are insulated;
finite coplanar grounds and the backing plane set the reference.

Equal signals and matching ground thickness reproduce the equal coated coplanar
factory exactly. Existing cross-section/3 and study/design schemas preserve the
geometry/new template name; older readers can reject that name. No new schema
is introduced. Explicit box and air separate truncation from physical sampling;
changing ground width is physical sensitivity, not outer-boundary convergence.

## Correlated fixed-pitch study

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved, execute_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    ground_gap=.25e-3, ground_width=1.5e-3, ground_thickness=35e-6,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    coating_thickness=20e-6, coating_eps_r=3.3, coating_tan_delta=.015,
    left_thickness=35e-6, right_thickness=50e-6,
    box_width=12e-3, air_height=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_conformal_coated_grounded_coplanar',
    parameters, quantity='z_diff_forward', fixed_pitch_m=.7e-3,
    sampling=dict(kind='normal', count=2, seed=71, correlation=[[1., .4], [.4, 1.]],
        variables=[dict(name='left_width', mean=.3e-3, std=10e-6),
                   dict(name='coating_thickness', mean=20e-6, std=2e-6)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
output = execute_saved(study.dumps(), max_evaluations=2)
assert output['status'] == 'complete' and output['result']['failed'] == 0
for row in study.sample_parameters():
    assert abs(row['gap']+(row['left_width']+row['right_width'])/2-.7e-3) < 1e-15
    assert row['ground_gap'] == parameters['ground_gap']
```

Fixed pitch derives gap=pitch-(left_width+right_width)/2 while preserving outer
ground clearances. Invalid bounded inputs reject before fields; invalid normal
rows retain original parameters without clipping or resampling. Existing
study/4 region-material numeric leaves, iid-yield and full-complex line-quantity
studies replay the geometry with explicit material/conductor capability checks.

z_diff_forward is the real electrostatic zero-common-current launch, not an odd
eigenmode or loaded impedance. z_diff requiring exchange symmetry rejects.
Full-complex differential_forward_impedance_real is a distinct quantity.

## Independent acceptance contract

Independent offset-line side distances and film-minus-all-metal area qualify
disjoint mitered envelopes. Unequal-height signal envelopes at gaps20/40/60um
check merged/separate topology for a20um film. Explicit ground thicknesses
0/20/80um verify the highest coating surface and independence from signals.
Thin metal→planar film and vacuum film→uncoated limits at the same exterior
height require C/C_loss/C0/Z differences below.5% on the fine mesh.

For the documented fixture, coarse(edge5um/far.25mm/grade.2) to
fine(2.5um/.125mm/.1) C/Z changes must be below1.5%; separate box12→24mm,
air6→12mm and reflected tapered conductor permutation below.5%. Ground
width1.5→3mm is recorded separately. Scaling, vacuum identity, reciprocity and
same-mesh dielectric energy monotonicity use1e-12.

Test-only scikit-fem12.0.2(BSD-3-Clause) independently assembles complex/vacuum
P1 energy on the same mesh, with normalized C/C_loss/C0 error<=1e-10. A separate
thin-vacuum grounded-image integral uses explicit signal intervals
[-.55,-.25]/[.05,.55]mm and grounded intervals[-2.3,-.8]/[.8,2.3]mm, all at
height.5mm. The full matrix is reduced to its signal block at zero ground
potential. Reference80→160-panel change<.3%; FEM errors decrease under
coarse/fine refinement and finish below2%; doubled box/air changes below1%.

The .7mm fixed-pitch left-width goal uses [.08,.85]mm,100ohm±1ohm,max30
evaluations. Fine, automatic half refinement, separate doubled box and air
must retain the same solved width within tolerance, with outer changes below.5%.
Material/full-complex replay uses1e-10. These bounded fixtures do not establish
arbitrary-geometry or measured accuracy, radiation/3D support, browser execution
or Windows support.
