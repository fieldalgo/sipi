# Unequal coplanar pair in a planar coating

`asymmetric_coupled_coated_grounded_coplanar` places unequal signal traces
between finite rectangular grounds above a grounded backing plane. All metal
bottom faces lie at `substrate_height`. The full-width planar coating starts
there: `coating_height` includes all copper and must exceed the largest signal
or ground thickness. `air_height` starts **above the coating**, including when
it is smaller than a metal thickness. Top and lateral boundaries are insulated.
This is a uniform 2D section, not a conformal film or a meniscus model.

Signal `left_width`, `right_width`, `left_thickness`, `right_thickness`,
`left_top_width` and `right_top_width` are independent. Finite grounds share
explicit `ground_width`, `ground_gap`, `ground_thickness` (default zero).
Ground thickness is never inferred from a signal. There is no central ground
or assumed exchange symmetry. All lengths are metres. Positive is left and
negative right; the complete signal bottom span is centered. `gap` and
`ground_gap` are bottom-edge clearances, with existing taper/contact/clipping
guards. Equal signals and equal ground thickness reproduce the canonical
`coupled_coated_grounded_coplanar` geometry, including automatic box dimensions.

The three regions are `substrate`, `coating` and `air`. Substrate `eps_r` and
`tan_delta`, and film `coating_eps_r` and `coating_tan_delta`, remain separate.
Default box and air dimensions follow the existing uncoated scaffold; the
automatic air height is 10 substrate heights plus the largest copper thickness,
now placed above the film. Explicit dimensions avoid this dependence in studies.
Ground width is physical; box width and upper air are separate truncations.

## Saved studies and targets

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    coating_height=.1e-3, coating_eps_r=3.3, coating_tan_delta=.015,
    left_thickness=35e-6, right_thickness=50e-6,
    ground_width=1.5e-3, ground_gap=.25e-3, ground_thickness=35e-6,
    box_width=12e-3, air_height=5e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_coated_grounded_coplanar',
    parameters, quantity='z_diff_forward', fixed_pitch_m=.7e-3,
    sampling=dict(kind='uniform', count=2, seed=71, variables=[
        dict(name='left_width', lower=.28e-3, upper=.32e-3),
        dict(name='coating_height', lower=.09e-3, upper=.11e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
result = study.analyze(max_evaluations=2)
assert result.failed == 0 and len(result.rows) == 2
for row in result.rows:
    p = row.parameters
    assert abs(p['gap']+(p['left_width']+p['right_width'])/2-.7e-3) < 1e-15
    assert row.document.section.layers[1].thickness == p['coating_height']
    assert row.document.section.layers[2].thickness == 5e-3
```

The two-width pitch constraint derives `gap=pitch-(left_width+right_width)/2`.
Grounds move to preserve outer ground gaps. The forward differential-current
quantity `z_diff_forward` has common current zero; it is not a symmetric odd
mode or terminated impedance. Invalid finite bounds fail before field solving;
invalid normal rows remain failed without clipping or resampling. Material
study/3 and /4 bind `substrate` and `coating` separately. Existing iid yield,
left-width goals and paired full-loss line study/2 reuse the template. The
latter uses full complex `differential_forward_impedance_real`. There is no
new saved schema or dependency; older readers may reject the new template name.

## Independent acceptance contract

For the finite fixture above, coarse `(5 um,.25 mm,.2)` to fine
`(2.5 um,.125 mm,.1)` edge/far/grade C/Z changes must be <1.5%. On the fine
mesh, box 12→24 mm and air 5→10 mm each require <.5%. Ground width 1.5→3 mm
has a separate <1% physical sensitivity gate. Independent scikit-fem 12.0.2
(BSD-3-Clause) complex/vacuum P1 assembly on the same mesh checks C/C_loss/C0
at normalized 1e-10. It does not independently generate geometry or mesh.
Uniform coefficient scaling, common loss, reciprocity and vacuum L use 1e-12;
horizontal reflection with signal permutation uses .5%.

A film with permittivity 1 and loss 0 must match the uncoated geometry with
the same top boundary (`air_height=film height+coated air height`) within .5%
for C/C_loss/C0/forward Z. A separate all-zero-thickness vacuum fixture uses
an independent image-charge Green integral panel solve: explicit signal
intervals [-.55,-.25], [.05,.55] mm and ground intervals [-2.3,-.8], [.8,2.3]
mm lie .5 mm above an infinite backing plane. The 80→160-panel C/Z changes
must be <.3%, fine FEM error <2% and decrease from coarse. This is a thin
vacuum limit, not a validation substitute for finite copper and the real film.

The .7 mm fixed-pitch left-width goal spans [.08,.6] mm, targets 100 ohm with
1 ohm tolerance and 30 evaluations. This goal uses the fine settings above
and their automatic `(1.25 um,.0625 mm,.05)` refinement. The original coarse
request was rejected because its refined result missed the same 1 ohm target;
that failure is retained rather than relaxing the tolerance.
Requested/refined/24 mm box/10 mm air
results at the same width must all satisfy the tolerance. Saved material and
complex-line replay use 1e-10. These fixture-specific gates do not establish
measured-board, general 3D, browser or Windows accuracy.

[Studies](study.md) · [한국어](../../locales/ko/pages/packages/sipi/asymmetric_coated_coplanar.md)
