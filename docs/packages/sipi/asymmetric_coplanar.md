# Unequal pair with finite coplanar grounds

`asymmetric_coupled_grounded_coplanar` places two unequal surface signals and
two finite rectangular ground traces above a backing ground plane. Positive is
left, negative right, with no ground between them. All four bottom faces are at
`substrate_height`. The upper and side boundaries of the finite box are insulated.

Lengths are metres. `left_width`, `right_width`, `left_thickness`,
`right_thickness`, `left_top_width` and `right_top_width` independently describe
the signals. Thickness defaults to zero and top width to the bottom width.
Both grounds share positive `ground_width`, positive `ground_gap` and explicit
`ground_thickness` (default zero). Ground thickness is **not inferred** from
either signal. Grounds are rectangular; only the signals taper.

`gap` separates signal bottom extents. `ground_gap` separates each outer signal
bottom extent from its adjacent ground. The bottom signal span is centred at 0:

```
S = left_width + right_width + gap
x_left = -(gap + right_width)/2
x_right = (gap + left_width)/2
x_ground = +/-(S/2 + ground_gap + ground_width/2)
```

Tapers can reduce actual face clearances. Existing contact/overlap, clipping and
air-clearance guards remain active. `eps_r` and `tan_delta` belong to the
substrate, while air has relative permittivity 1 and zero dielectric loss.
Default air thickness is `10*substrate_height+max(left_thickness,right_thickness,
ground_thickness)`. Default box width is
`max(20*substrate_height,4*max(left_width,right_width),
S+2*ground_gap+2*ground_width+4*substrate_height)`.
Finite ground width is part of the physical geometry, not an infinite-ground
approximation. Vary it separately from the numerical box and air height.

Equal signals and matching ground thickness reproduce the canonical geometry
of `coupled_grounded_coplanar`. Unequal pairs require `z_diff_forward` in saved
studies and goals. This is differential voltage per forward differential-current
launch with common launch current zero, not a symmetric odd mode or terminated
input impedance. Full-loss paired line study/2 uses the separate explicit
`differential_forward_impedance_real` quantity and full coupled matrices.

## Saved inputs and tolerances

The [two-width fixed-pitch rule](asymmetric_pitch.md) derives gap from
`fixed_pitch_m-(left_width+right_width)/2`. Ground traces move with the outer
signal span to preserve specified ground gaps; their absolute positions are
not fixed. Ground gap/width/thickness remain explicit sampled parameters.
Nominal inputs must satisfy the pitch. Do not sample gap independently under
that constraint. No fixed-total-plane-spacing constraint applies here.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    left_thickness=35e-6, right_thickness=50e-6,
    ground_width=1.5e-3, ground_gap=.25e-3, ground_thickness=35e-6,
    box_width=12e-3, air_height=5e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_grounded_coplanar', parameters,
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

Sweeps, corners, uniform and correlated normal samples retain existing rules:
bounded invalid inputs fail before fields; invalid normal rows stay failed in
place without clipping/resampling. Material study/3 or /4 binds the `substrate`
region. Existing iid-yield, width-goal and paired line studies reuse the inputs.
There are 33 templates and 42 saved schema versions, with no new schema fields
or runtime dependencies. Older readers may reject the new name; record the
exact engine/wheel with inputs.

## Independent acceptance criteria

The finite fixture above compares `(edge_size,far_size,grade)` settings
`(5 um,.25 mm,.2)` and `(2.5 um,.125 mm,.1)`. C/forward-Z changes must be below
1.5%. On the fine mesh, changing box width 12→24 mm or air height 5→10 mm
separately must change C/Z by less than .5%. Changing finite ground width
1.5→3 mm has a separate 1% sensitivity criterion for this fixture. These do
not establish universal domain truncation or ground-width independence.

Independent scikit-fem 12.0.2 (BSD-3-Clause) complex/vacuum P1 energy assembly
checks C/C_loss/C0 on the same mesh to normwise relative `1e-10`. Separate
coefficient scaling and vacuum identities use `1e-12`; reciprocity/passivity
and reflected conductor permutation (within .5%) are checked independently.

A second reference uses the analytic image-charge Green integral, constant
charge panels and a dense solve, independent of SIPI geometry/mesh/solver.
For all-zero thickness and vacuum, explicit signal intervals are
[-.55,-.25] and [.05,.55] mm, ground intervals [-2.3,-.8] and [.8,2.3] mm at
height .5 mm. The grounded signal capacitance block gives `Zc=inv(C)/c`.
The 80→160 panels/strip reference change must be below .3%; fine FEM C/Z
error must be below 2% and decrease from coarse. Doubling box and air together
must change fine C/Z by less than 1%. This thin-vacuum limit does not replace
the separate finite-copper and layered-material tests.

A 100-ohm left-width goal over [.1,.8] mm at fixed .7 mm pitch requires
requested/refined, expanded-box and expanded-air residuals within 1 ohm, and
each outer Z change below .5%. Material/yield and full-loss direct replay use
`1e-10`. These are numerical fixture checks, not measured-board accuracy,
general 3D validation or application/platform acceptance.

[Studies](study.md) · [한국어](../../locales/ko/pages/packages/sipi/asymmetric_coplanar.md)
