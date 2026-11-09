# Unequal pair with a normal-thickness coating

[Finite coplanar grounds](asymmetric_conformal_coplanar.md) add explicit lateral grounds under the same normal-thickness film.

[한국어](../../locales/ko/pages/packages/sipi/asymmetric_conformal_microstrip.md) ·
[Planar coating](asymmetric_coated_microstrip.md) · [Equal conformal pair](conformal_coating.md)

`asymmetric_coupled_conformal_coated_microstrip` puts two unequal signals on
a substrate above a backing ground plane. A film of prescribed normal thickness
covers the substrate, conductor tops and straight sloping sides; corners meet
at miters. There are no lateral ground traces. This is a uniform quasistatic
2D section, without exchange symmetry, rounded corners, a meniscus or a
prediction of an actual deposition profile.

All lengths are metres. Positive is left, negative is right, and the combined
signal bottom span is centered. gap separates bottom edges. Left/right widths,
metal thicknesses and optional top widths are independent. Only rectangular
or narrowing-top metal is supported; overhangs reject. coating_thickness is
normal to each surface, and is distinct from the total height of a planar film.
Meeting envelopes unite into one coating region; clipping and enclosed air
pockets are rejected. Finite positive features below the existing box-relative
resolution threshold also reject, without snapping or deleting gaps.

The substrate and air remain layers; coating is one local dielectric region
with coating_eps_r and coating_tan_delta. Copper takes priority inside it.
Upper air starts above the highest coated trace, at
substrate_height+max(left_thickness,right_thickness)+coating_thickness.
Any resolvable positive upper air is geometrically valid, but its numerical
truncation must still be checked. Top and side boundaries are insulated.
Specify box and air explicitly when sampling manufactured dimensions.

Equal signal dimensions reproduce coupled_conformal_coated_microstrip geometry
exactly. Geometry uses existing cross-section/3; study/design schemas register
the new name without a new saved schema. Older readers can reject the name.

## Save and evaluate a correlated study

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved, execute_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    coating_thickness=20e-6, coating_eps_r=3.3, coating_tan_delta=.015,
    left_thickness=35e-6, right_thickness=50e-6,
    box_width=12e-3, air_height=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_conformal_coated_microstrip',
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
```

Fixed pitch derives gap=pitch-(left_width+right_width)/2. Invalid bounded input
rejects before fields; invalid normal rows retain original parameters and fail
without clipping or resampling. Study/4 material numeric leaves can target the
named coating region. Existing iid-yield and full-complex line-quantity studies
replay explicit materials/conductors with their existing capability checks.

z_diff_forward is the real electrostatic launch with zero common current, not
an odd eigenmode or loaded impedance. z_diff requiring exchange symmetry rejects.
The full-complex differential_forward_impedance_real is a distinct quantity.

## Independent acceptance contract

Independent offset-line intersections check normal side distance and, for
disjoint envelopes, film-minus-metal area = box_width*d + sum(2*delta_i*t_i),
where s_i=(width_i-top_width_i)/(2*t_i) and
delta_i=d/(sqrt(1+s_i*s_i)+s_i). Unequal-height rectangular envelopes at gaps
20/40/60um check merged/separate topology for d20um. Thin conductors reduce to
a planar film with the same materials; a vacuum film reduces to uncoated
geometry at the same exterior height, each within.5% on the fine mesh.

The documented .3/.5mm widths, gap.3mm, substrate.5mm, metal35/50um, film20um
fixture uses coarse(edge5um/far.25mm/grade.2)→fine(2.5um/.125mm/.1): C/Z changes
below1.5%. Separate box12→24mm and upperair6→12mm changes, and reflected tapered
signal permutation, must stay below.5%. Scaling, vacuum, reciprocity and
same-mesh dielectric energy monotonicity use1e-12.

Test-only scikit-fem12.0.2(BSD-3-Clause) independently assembles complex/vacuum
P1 energy on the same mesh: normalized C/C_loss/C0 error<=1e-10. A separate
thin-vacuum image-plane integral uses explicit intervals[-.55,-.25]/[.05,.55]mm
at height.5mm. Reference80→160-panel change<.3%; coarse/fine FEM errors decrease
and finish below2%, doubled box/air changes below1%.

The .7mm fixed-pitch left-width goal uses [.08,.85]mm,100ohm±1ohm,max30
evaluations. Fine, automatic half refinement, separate doubled box and air
must retain the same solved width within tolerance; outer relative changes
must also stay below.5%. Material/full-complex replay uses1e-10.
These checks qualify bounded fixtures, not arbitrary geometry, measured
accuracy, radiation/3D transitions, browser execution or Windows builds.
