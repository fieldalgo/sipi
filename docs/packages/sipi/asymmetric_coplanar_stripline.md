# Unequal buried pair with finite coplanar grounds

`asymmetric_coupled_coplanar_stripline` places two independently dimensioned
signals and two finite rectangular ground traces between grounded planes.
The dielectric is homogeneous (`eps_r`, `tan_delta`), with insulated sides.
All four bottom faces share explicit `trace_height` above the lower plane;
`plane_spacing` is the full distance between planes.

Signal `left_width`, `right_width`, `left_thickness`, `right_thickness`,
`left_top_width` and `right_top_width` are independent. Thickness defaults to
zero; top width defaults to bottom width. Grounds share explicit `ground_width`,
`ground_gap` and `ground_thickness` (default zero). Ground thickness is never
inferred from signal thickness. There is no central ground and no assumed
exchange symmetry. All lengths use metres.

Positive is left and negative right. For signal bottom span S=wL+wR+gap:

```
x_left = -(gap+wR)/2
x_right = (gap+wL)/2
x_ground = +/-(S/2+ground_gap+ground_width/2)
```

`gap` and `ground_gap` refer to bottom-edge clearances; tapers can reduce actual
face clearance. Existing contact, overlap and box/plane clipping guards apply.
Signals extend upward from the common bottom height, so unequal thicknesses
do not share a vertical midpoint. This differs from
[the vertically centered unequal stripline pair](asymmetric_stripline.md).
Equal signals with matching ground thickness reproduce the exact canonical
geometry of `coupled_coplanar_stripline`, including automatic box dimensions.

Default box width is `max(12*plane_spacing,4*S,
S+2*ground_gap+2*ground_width+4*plane_spacing)`. Finite ground width is physical;
box width is a separate numerical truncation. Ground planes and side traces
share one PEC reference. This is a uniform 2D cross-section, not a via or a
spatially varying return-plane model.

## Saved inputs, tolerances and targets

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    plane_spacing=1e-3, trace_height=.4e-3, eps_r=4., tan_delta=.02,
    left_thickness=35e-6, right_thickness=50e-6,
    ground_width=1.5e-3, ground_gap=.25e-3, ground_thickness=35e-6,
    box_width=8e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_coplanar_stripline', parameters,
    quantity='z_diff_forward', fixed_pitch_m=.7e-3,
    sampling=dict(kind='uniform', count=2, seed=71,
        variables=[dict(name='left_width', lower=.28e-3, upper=.32e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
result = study.analyze(max_evaluations=2)
assert result.failed == 0 and len(result.rows) == 2
for row in result.rows:
    a, b, left_ground, right_ground = row.document.section.traces
    assert abs(b.x-a.x-.7e-3) < 1e-15
    assert abs(a.x0-left_ground.x1-.25e-3) < 1e-15
```

Unequal-pair saved studies/goals require `z_diff_forward`, the explicit forward
differential-current launch with common current zero, not a symmetric odd mode
or terminated input impedance. [Fixed pitch](asymmetric_pitch.md) derives
`gap=pitch-(left_width+right_width)/2`; grounds move with the outer signal span
to maintain the specified ground gaps. Do not independently sample gap under
this constraint. `plane_spacing` is a direct dimension, not a two-layer
fixed-total-height constraint.

Sweeps, corners, uniform and correlated normal samples retain existing failure
rules: invalid bounded geometry fails before fields; invalid normal rows remain
failed without clipping/resampling. Material study/3 or /4 binds `dielectric`.
Existing iid yield, left-width goal and paired full-loss line study/2 reuse this
template. Full-loss studies use `differential_forward_impedance_real` and full
coupled matrices, distinct from the real electrostatic forward quantity.
No saved schema or runtime dependency changes; older readers can reject the new
template name, so retain exact engine and wheel identity with input files.

## Independent acceptance

For the finite fixture above, compare `(edge_size,far_size,grade)`
`(5 um,.25 mm,.2)`→`(2.5 um,.125 mm,.1)`: C/forward-Z changes must be <1.5%.
On the fine mesh, box width 8→16 mm must change C/Z by <.5%. Ground width
1.5→3 mm has a separate <1% physical sensitivity criterion; it is not numerical
domain convergence or a universal ground-width independence claim.

Independent scikit-fem 12.0.2 (BSD-3-Clause) complex/vacuum P1 energy assembly
on the same mesh checks C/C_loss/C0 to normwise relative 1e-10. Geometry is not
independently meshed by that comparison. Homogeneous C=eps_r·C0,
C_loss=tan_delta·C, L=mu0·eps0·inv(C0), coefficient scaling and reciprocity use
1e-12. Swapping unequal conductors and reflecting geometry must permute the
field matrices/forward Z within .5% on independently generated meshes.

A separate all-zero-thickness vacuum limit uses the analytic image-charge
Green integral and constant-charge panel solve, independent of SIPI geometry,
mesh and solver. Explicit signal intervals [-.55,-.25], [.05,.55] mm and ground
intervals [-2.3,-.8], [.8,2.3] mm lie .5 mm above one infinite grounded plane.
The reference has **no upper plane**. Its 80→160 panels/strip C/Z change must
be <.3%; fine FEM error <2% and decrease from coarse. The FEM limit uses an
upper plane at 12 mm and box width 12 mm; increasing each separately to 24 mm
must change C/Z by <.5%. This upper-plane limit does not replace acceptance of
the finite 1 mm homogeneous manufactured cross-section.

A 100-ohm left-width goal over [.08,.6] mm at fixed .7 mm pitch requires the
requested mesh, its halved refinement and an expanded 16 mm box at the same
candidate width to remain within 1 ohm. Material/full-loss replay uses 1e-10.
These are fixture-specific numerical checks, not measured-board accuracy,
general 3D validation or application/platform acceptance.

For this fixture, observed C/Z mesh changes were .2262%/.3099%, box changes
below .000044%, and ground-width sensitivity below .000700%. The same-mesh
independent maximum difference was 5.557e-15. The 100-ohm candidate left width
was .12875 mm, with requested/refined/expanded-box residuals
0.094641/0.430341/0.430097 ohm. In the separate thin limit, fine C/Z reference
errors were .2767%/.3521%; raising the upper plane changed C/Z by less than
.06355%, and widening the box by less than .03419%.

[Studies](study.md) · [한국어](../../locales/ko/pages/packages/sipi/asymmetric_coplanar_stripline.md)
