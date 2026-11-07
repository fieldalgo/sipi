# Unequal buried coplanar pair at a dielectric interface

`asymmetric_coupled_layered_coplanar_stripline` places two independently sized
signal traces and two finite rectangular ground traces between grounded planes.
All bottom faces lie at `lower_height`, the lower/upper dielectric interface.
Copper extends upward: `upper_height` includes copper, and every signal/ground
thickness must be smaller than it. Sides are insulated. There is no central
ground, and the two materials are not averaged.

Signals have independent `left_width`, `right_width`, `left_thickness`,
`right_thickness`, `left_top_width` and `right_top_width`. Grounds share explicit
`ground_gap`, `ground_width` and `ground_thickness` (default zero); ground
thickness never follows a signal implicitly. All lengths are metres.
The full signal bottom span S=wL+wR+gap is centered: signal centers are
`-(gap+wR)/2` and `(gap+wL)/2`, positive then negative. Ground centers are
`+/-(S/2+ground_gap+ground_width/2)`. Clearances refer to bottom edges; taper
contact/overlap and box/plane clipping are rejected by the geometry validator.

`lower_eps_r`, `upper_eps_r`, `lower_tan_delta`, `upper_tan_delta` describe
separate regions named `lower` and `upper`. Equal signals and matching ground
thickness reduce to the exact canonical geometry of
`coupled_layered_coplanar_stripline`, including default box width. With total
height H, the default width is `max(12*H,4*S,S+2*ground_gap+2*ground_width+4*H)`.
Ground width is physical; box width is a separate truncation parameter.
This model describes a uniform 2D cross-section.

## Saved studies, constraints and targets

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    lower_height=.4e-3, upper_height=.6e-3, lower_eps_r=3., upper_eps_r=5.,
    lower_tan_delta=.01, upper_tan_delta=.03,
    left_thickness=35e-6, right_thickness=50e-6,
    ground_gap=.25e-3, ground_width=1.5e-3, ground_thickness=35e-6,
    box_width=8e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_layered_coplanar_stripline',
    parameters, quantity='z_diff_forward', fixed_pitch_m=.7e-3,
    fixed_plane_spacing_m=1e-3,
    sampling=dict(kind='uniform', count=2, seed=71, variables=[
        dict(name='left_width', lower=.28e-3, upper=.32e-3),
        dict(name='lower_height', lower=.38e-3, upper=.42e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
result = study.analyze(max_evaluations=2)
assert result.failed == 0 and len(result.rows) == 2
for row in result.rows:
    p = row.parameters
    assert abs(p['lower_height']+p['upper_height']-1e-3) < 1e-15
    assert abs(p['gap']+(p['left_width']+p['right_width'])/2-.7e-3) < 1e-15
```

Fixed pitch derives `gap=pitch-(left_width+right_width)/2`; grounds move to
preserve their outer clearances. Fixed plane spacing samples exactly one layer
height and derives the other. The two constraints compose. Invalid bounded
geometries fail before solving; invalid normal rows remain failed without
clipping or resampling. Saved study/3 or /4 material bindings use `lower` and
`upper`, including independent material variables. Existing iid yield, width
goals and full-loss paired line study/2 reuse this template.

`z_diff_forward` means explicit differential-current launch with common current
zero, not a symmetric odd mode or terminated input impedance. Full-loss line
study/2 uses `differential_forward_impedance_real` from the full complex matrix.
No schema or runtime dependency is added. Older engines may reject this new
template name; retain engine/wheel identity with saved inputs.

## Independent acceptance contract

The finite fixture above uses coarse `(edge_size,far_size,grade)`
`(5 um,.25 mm,.2)` and fine `(2.5 um,.125 mm,.1)`. C/forward-Z mesh changes must
be <1.5%; fine-mesh box 8→16 mm changes <.5%. Ground width 1.5→3 mm has a
separate <1% physical sensitivity gate, not a domain-convergence claim.
Independent scikit-fem 12.0.2 (BSD-3-Clause) complex/vacuum P1 energy assembly
on the same mesh checks C/C_loss/C0 at normalized 1e-10; that reference does
not independently generate geometry or mesh. Coefficient scaling, common-loss
proportionality, reciprocity and L=mu0·eps0·inv(C0) use 1e-12. Equal materials
reduce to the homogeneous buried coplanar fixture within .5%. Horizontal
reflection permutes the two signals, with field differences <.5%.

An independent analytic limit uses **zero thickness for all four traces** and
equal .5 mm upper/lower heights. Reflection symmetry makes the complex energy
equal to `[(epsL*(1-j*tanL)+epsU*(1-j*tanU))/2]*C0`. For epsL=2, epsU=6 and
loss tangents .01/.03, C=4*C0 and C_loss=.1*C0 must agree within .5% on the
fine mesh. This identity does not justify averaging for finite copper or
unequal heights. Separately, reflecting the .4/.6 mm zero-thickness fixture
and swapping both materials must preserve matrices/forward Z within .5%.

The fixed .7 mm pitch left-width target spans [.08,.6] mm and targets 100 ohm
with 30 evaluations and 1 ohm tolerance. Requested/refined/16 mm-box results
at the same candidate must all remain within that tolerance. Saved material
and complex line replay use 1e-10. These are fixture-specific numerical gates;
they do not establish measured-board, general 3D or platform accuracy.

[Studies](study.md) · [한국어](../../locales/ko/pages/packages/sipi/asymmetric_layered_coplanar_stripline.md)
