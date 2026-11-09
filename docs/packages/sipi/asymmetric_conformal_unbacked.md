# Unequal unbacked pair with a normal-thickness coating

[한국어](../../locales/ko/pages/packages/sipi/asymmetric_conformal_unbacked.md) ·
[With a backing plane](asymmetric_conformal_coplanar.md) · [Planar unbacked film](asymmetric_coated_unbacked_coplanar.md)

`asymmetric_coupled_conformal_coated_unbacked_coplanar` puts two unequal signals
between finite rectangular grounds on a finite substrate, with air below and
a normal-thickness mitered film above. There is no backing plane or central
ground. All outer boundaries are insulated; only the finite grounds define the
reference. This is a uniform quasistatic 2D section without exchange symmetry.

Lengths are metres. Positive is left, negative is right; the signal bottom span
is centered. gap separates signal bottom edges; ground_gap separates the outer
signal bottom edges and grounds. Left/right widths, thicknesses and narrowing
top widths are independent. Grounds share ground_width and explicit rectangular
ground_thickness (default0), independent of either signal thickness.

The same coating_thickness is normal to substrate, trace tops and straight
sides, with mitered corners. Meeting envelopes form one named coating region;
overhangs, clipped film, enclosed air pockets and unresolvable features reject.
This is not a meniscus, rounded-corner or measured deposition profile. The
film has independent coating_eps_r/coating_tan_delta; metal takes priority.

Layers are lower_air/substrate/air. Conductor bottoms and the local film are
translated together by lower_air_height (default ten substrate heights).
Upper air begins above the highest coated signal or ground. Set box and both
air heights explicitly when sampling manufactured dimensions. Each truncation
requires independent convergence; ground width is a physical dimension.
Equal signals with matching ground thickness reproduce the equal conformal
unbacked factory exactly. Existing cross-section/3 and study/design schemas
preserve the geometry/name; older readers can reject the new name.

## Saved correlated study

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved, execute_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    ground_gap=.25e-3, ground_width=1.5e-3, ground_thickness=35e-6,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    coating_thickness=20e-6, coating_eps_r=3.3, coating_tan_delta=.015,
    left_thickness=35e-6, right_thickness=50e-6,
    box_width=12e-3, air_height=6e-3, lower_air_height=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_conformal_coated_unbacked_coplanar',
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

Fixed pitch derives gap=pitch-(left_width+right_width)/2, preserving outer ground
clearances. Invalid bounded inputs reject before meshing; invalid normal rows
retain original parameters and fail without clipping or resampling. Existing
region-material study/4, iid-yield and full-complex line-quantity replay retain
their explicit material/conductor capability gates. A new geometry does not
automatically qualify every conductor approximation for an open-bottom domain.

z_diff_forward is the real electrostatic launch with zero common current,
not an odd eigenmode or loaded impedance. z_diff requiring symmetry rejects;
full-complex differential_forward_impedance_real is a separate quantity.

## Independent acceptance contract

Exact lower-air translation preserves all metal and local-film shapes. Separate
normal-distance/area, unequal-height union topology, explicit ground thickness,
equal-input and JSON checks qualify geometry. Thin-metal→planar-film and
vacuum-film→uncoated limits at the same exterior height require below.5% C/Z
and capacitance/loss differences on the fine mesh.

For the stated fixture, coarse(edge5um/far.25mm/grade.2) to
fine(2.5um/.125mm/.1) C/Z changes must be below1.5%; separate doubled box12→24mm,
upperair6→12mm and lowerair6→12mm changes and reflected conductor permutation
below.5%. Groundwidth1.5→3mm is physical sensitivity. Scaling, vacuum identity,
reciprocity and same-mesh film dielectric energy monotonicity use1e-12.

Test-only scikit-fem12.0.2(BSD-3-Clause) independently assembles complex/vacuum
P1 energy on the same mesh: normalized C/C_loss/C0 error<=1e-10. A separate
thin-vacuum neutral free-space -log(distance) integral uses an unknown common
potential and zero total charge, without an image plane or a distant grounded
wall. Explicit signal intervals[-.55,-.25]/[.05,.55]mm and grounded intervals
[-2.3,-.8]/[.8,2.3]mm are independent of the factory. Reference80→160-panel
change<.3%. At box24mm and upper/lowerair12mm, FEM(4um/.5mm/.2)→(1um/.25mm/.1)
errors must decrease and finish below2%; doubling all outer dimensions changes
C/Z below1%.

The .7mm fixed-pitch left-width goal uses [.08,.85]mm,100ohm±1ohm,max30
evaluations. Fine, automatic half refinement and individual doubled box/upper/
lower air must retain the same solved width within tolerance, with outer
relative changes below.5%. Material/full-complex replay uses1e-10. These checks
do not establish arbitrary-geometry or measured accuracy, radiation/3D support,
browser execution or Windows support.
