# Unequal pair at a two-dielectric interface

`asymmetric_coupled_layered_stripline` places unequal signal conductors between
grounded planes, with **both bottom faces** at `y=lower_height`. Copper extends
into the upper dielectric. `upper_height` includes copper; each top clearance
is `upper_height - thickness`. Total plane spacing is `lower_height+upper_height`.
This differs from the [homogeneous centred pair](asymmetric_stripline.md), where
each conductor's vertical midpoint is halfway between the planes.

All lengths are metres. Required inputs are `left_width`, `right_width`, `gap`,
`lower_height`, `upper_height`, `lower_eps_r` and `upper_eps_r`. Independent
`left_thickness`, `right_thickness` default to zero; optional `left_top_width`
and `right_top_width` describe symmetric tapers. `lower_tan_delta` and
`upper_tan_delta` default to zero. The `lower` and `upper` materials are retained
separately in the field solve, with no averaging.

Positive is left and negative right. The bottom-width span is centred at x=0:
`x_left=-(gap+right_width)/2`, `x_right=(gap+left_width)/2`.
Gap separates horizontal bottom extents, not necessarily the closest tapered
faces. Existing contact, overlap, taper and box guards remain active. Side
boundaries are insulated. Default box width is
`max(12*(lower_height+upper_height), 4*(left_width+gap+right_width))`;
specify and enlarge it independently of mesh refinement.

Equal left/right inputs reproduce the exact canonical geometry of
`coupled_layered_stripline`. Unequal pairs have no assumed exchange symmetry or
independent even/odd modes. Saved studies/goals require `z_diff_forward`, the
forward differential-current launch impedance with zero common launch current.
It does not imply zero common voltage or a terminated-circuit input impedance.

## Composed pitch and stack constraints

The [two-width pitch rule](asymmetric_pitch.md) derives
`gap=fixed_pitch_m-(left_width+right_width)/2`. Independently,
`fixed_plane_spacing_m` derives the other layer height when exactly one height
is sampled. Both constraints can be active together. Nominal inputs must
already satisfy them. Do not independently sample derived gap or both heights.
Bounded invalid corners fail before field evaluation; invalid normal samples
remain failed rows without clipping or resampling.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.4e-3,
    lower_height=.4e-3, upper_height=.6e-3, lower_eps_r=3., upper_eps_r=5.,
    left_thickness=35e-6, right_thickness=50e-6,
    lower_tan_delta=.01, upper_tan_delta=.03, box_width=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_layered_stripline', parameters,
    quantity='z_diff_forward', fixed_pitch_m=.8e-3, fixed_plane_spacing_m=1e-3,
    sampling=dict(kind='corners', variables=[
        dict(name='left_width', lower=.28e-3, upper=.32e-3),
        dict(name='lower_height', lower=.35e-3, upper=.45e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
result = study.analyze(max_evaluations=4)
assert result.failed == 0 and len(result.rows) == 4
for row in result.rows:
    a, b = row.document.section.traces
    assert abs(b.x-a.x-.8e-3) < 1e-15
    assert abs(row.document.section.height-1e-3) < 1e-15
```

Material study/3 and /4 bind `lower` and `upper` separately. Existing iid-yield,
single-variable goals and full-loss paired line study/2 can consume these
inputs. The latter explicitly requests `differential_forward_impedance_real`
and retains the full coupled characteristic matrix. There are 32 template
names and 42 saved schema versions; no schema fields or dependencies change.
Older readers can reject the new name; record the exact engine and wheel.

## Validation scope

The finite fixture above uses coarse mesh `(5 um,.25 mm,.2)` and fine mesh
`(2.5 um,.125 mm,.1)` for edge size, far size and grade. C/forward-Z changes
are 0.1916%/0.2700%, below the predeclared 1.5% gate. Doubling the fine box
from 6 to 12 mm changes them by 0.000774%/0.000672%, below the .5% gate.
Fine forward impedance is 89.4784 ohm. These are fixture-specific checks.

Independent scikit-fem 12.0.2 (BSD-3-Clause) complex/vacuum P1 assembly on the
same mesh checks C/C_loss/C0 to normwise relative `1e-10`. Separate checks
cover reciprocity/passivity, uniform permittivity scaling and uniform-loss
identities to `1e-12`. Equal materials and equal thickness at the centred
height reduce to the homogeneous pair within .5%. For **zero thickness**,
swapping lower/upper heights and materials is a vertical reflection; C/C0/L/
C_loss/Z differ by less than .5%. Finite upward copper is not reflection
symmetric under that swap.

A 100-ohm left-width goal at fixed .8 mm pitch, bounds [.1,.8] mm, selects
.1984375 mm. Requested/refined/enlarged-box residuals are
−.271112/−.188334/−.271320 ohm, all within the 1-ohm gate. Saved material/yield
and paired full-loss inputs replay against direct calculations to `1e-10`.
This is not measured-board accuracy, arbitrary-geometry convergence, a general
3D transition model or application/platform acceptance.

[Studies](study.md) · [한국어](../../locales/ko/pages/packages/sipi/asymmetric_layered_stripline.md)
