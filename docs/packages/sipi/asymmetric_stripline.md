# Unequal buried edge-coupled pair

`asymmetric_coupled_stripline` places two unequal signal conductors in a
homogeneous dielectric between grounded planes. It independently accepts
`left_width`, `right_width`, `left_thickness`, `right_thickness` and optional
`left_top_width`, `right_top_width`. Lengths are metres. `eps_r` and `tan_delta`
describe the single dielectric; the side boundary is insulated.

## Geometry and impedance contract

`plane_spacing=H` is the complete plane-to-plane distance, including copper.
Each conductor's **vertical midpoint** is H/2, so its bottom height is
`(H-thickness)/2`. Different thicknesses do **not** share a bottom face.
The positive conductor is left and negative is right. The total horizontal
bottom-width span is centred at x=0:

```
x_left  = -(gap + right_width)/2
x_right =  (gap + left_width)/2
pitch   = gap + (left_width + right_width)/2
```

`gap` separates the bottom-width horizontal extents, not necessarily the
closest tapered faces. Thickness may be zero; gap and widths must be positive.
Existing trace/taper/contact/overlap and box-clipping guards remain active.
Both conductors must clear both ground planes. The default box width is
`max(12*H, 4*(left_width+gap+right_width))`; specify it for reproducible finite-box
studies and check outer convergence. This template adds no vertical offset,
layered dielectric or nonuniform ground plane.

Equal left/right widths, thicknesses and top widths produce the exact same
canonical geometry as the existing centred `coupled_stripline`. For unequal
inputs, exchange symmetry and independent even/odd modes are not assumed.
Saved studies and goals require **`z_diff_forward`**: differential voltage over
forward differential-current launch, with common launch current zero. It is
not a terminal impedance or an assertion of zero common voltage downstream.

## Saved studies, tolerances and goals

The template is registered in existing geometry/study/design contracts. The
existing [two-width fixed-pitch rule](asymmetric_pitch.md) applies to either or
both width variables: derive `gap = fixed_pitch_m - (left_width+right_width)/2`.
Nominal width/gap must already match the pitch. Do not independently sample gap
under that constraint. Top width does not define pitch, and fixed pitch does
not fix either absolute centre coordinate.

Sweeps, corners, uniform and correlated normal samples retain their existing
rules. Bounded invalid corners are rejected before fields; invalid normal rows
remain failed in place without clipping/resampling. Material study/3 or /4 uses
the `dielectric` region. Existing iid-yield and scalar width-goal engines can
consume the saved forward-quantity study. A full-loss paired line study/2 uses
`differential_forward_impedance_real` explicitly; it is a different quantity.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.4e-3,
    plane_spacing=1e-3, eps_r=4., left_thickness=35e-6,
    right_thickness=50e-6, tan_delta=.02, box_width=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_stripline', parameters,
    quantity='z_diff_forward', fixed_pitch_m=.8e-3,
    sampling=dict(kind='uniform', count=2, seed=71,
        variables=[dict(name='left_width', lower=.28e-3, upper=.32e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
result = study.analyze(max_evaluations=2)
assert result.failed == 0 and len(result.rows) == 2
for row in result.rows:
    left, right = row.document.section.traces
    assert abs((right.x-left.x)-.8e-3) < 1e-15
```

The template registry grows to 31 names; input schema fields and the 42 saved
schema versions remain unchanged. Older readers may reject the new template
name; retain the exact engine/wheel identity with input. This adds no new
runtime dependency or application/platform release.

## Validation scope

The finite fixture uses widths .3/.5 mm, gap .4 mm, plane spacing 1 mm,
thicknesses 35/50 um, eps_r=4, tan_delta=.02 and box width 6 mm. Separate gates
compare 5 um/.25 mm/grade .2 to 2.5 um/.125 mm/grade .1 mesh settings:
capacitance matrix and forward impedance changes must be below 1.5%.
Doubling the box on the fine mesh must change both by less than .5%.
These are discretization checks at the stated fixture, not universal accuracy.

Independent scikit-fem 12.0.2 (BSD-3-Clause) complex/vacuum P1 assembly on the
same mesh checks C, C_loss and C0 to normwise relative `1e-10`. Separate
homogeneous identities check C=eps_r*C0, C_loss=tan_delta*C, the vacuum-based
L and forward-impedance scaling to `1e-12`. At gap 5H/box 32H, normalized
cross capacitance is below `1e-4`; self capacitances approach the corresponding
isolated strips within 1%, allowing separately generated mesh errors.

Saved material binding/yield and full-loss PEC sampling check the independent
homogeneous complex characteristic matrix to `1e-10`. A 100-ohm width target at
fixed .8 mm pitch requires requested/refined and enlarged-box residuals within
1 ohm, with outer impedance change below .5%. Geometry/strict guards, original
asymmetric surface-pair behavior and related saved contracts remain in the
regression. These checks do not establish measured manufacturing accuracy,
arbitrary input convergence or general 3D transition behavior.

[Studies](study.md) · [한국어](../../locales/ko/pages/packages/sipi/asymmetric_stripline.md)
