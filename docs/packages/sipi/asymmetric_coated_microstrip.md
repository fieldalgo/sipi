# Unequal planar-coated microstrip pair

[한국어](../../locales/ko/pages/packages/sipi/asymmetric_coated_microstrip.md) · [Equal coated pair](coated_pair.md)

`asymmetric_coupled_coated_microstrip` places two independently dimensioned
signals on a substrate above a grounded backing plane. A flat full-width film
covers both signals; there are no lateral ground traces. Top and side boundaries
are insulated. This is a uniform quasistatic 2D section.

Positive is left and negative is right. The combined bottom signal span is
centered; gap separates bottom edges. left_width/right_width, independent metal
thicknesses and optional top widths use metres. Existing taper, overlap and
domain checks apply. The three layers are substrate/coating/air. Coating height
starts at the substrate surface, includes all metal, and must exceed both metal
thicknesses. Upper air starts above the film; any positive height is geometrically
valid, though a small truncation does not establish numerical convergence.
The flat film is not a conformal mask or meniscus.

With equal signal dimensions, explicit box and upper air, geometry is exactly
the existing coupled_coated_microstrip geometry. Automatic box width and upper
air reuse the existing microstrip scaffold. Specify truncations explicitly when
sampling dimensions so they remain independent of the manufactured variables.
The new template is registered in existing study/design schemas; older readers
can reject its name. No new saved schema is introduced.

## Save and evaluate a fixed-pitch study

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved, execute_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    coating_height=.1e-3, coating_eps_r=3.3, coating_tan_delta=.015,
    left_thickness=35e-6, right_thickness=50e-6,
    box_width=12e-3, air_height=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_coated_microstrip',
    parameters, quantity='z_diff_forward', fixed_pitch_m=.7e-3,
    sampling=dict(kind='uniform', count=2, seed=71, variables=[
        dict(name='left_width', lower=.28e-3, upper=.32e-3),
        dict(name='coating_height', lower=.09e-3, upper=.11e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
output = execute_saved(study.dumps(), max_evaluations=2)
assert output['status'] == 'complete'
assert output['result']['failed'] == 0
for row in study.sample_parameters():
    assert abs(row['gap']+(row['left_width']+row['right_width'])/2-.7e-3) < 1e-15
```

Fixed pitch derives gap=pitch-(left_width+right_width)/2. Invalid bounded inputs
reject before meshing; invalid normal samples retain their original parameters
as failed rows without clipping or resampling. Study/4 can vary numeric material
leaves in substrate/coating; existing iid-yield and full-complex line-quantity
study/2 can replay the same sampled geometry with explicit material/conductor
models. Their capability and skin-depth checks still apply.

z_diff_forward is the real electrostatic launch with zero common current; it is
not an odd eigenmode or loaded impedance. z_diff requiring exchange symmetry is
rejected. The full-complex differential_forward_impedance_real is a distinct
quantity. Arbitrary dimensions require their own mesh and truncation studies.

## Independent acceptance contract

The stated .3/.5mm signal widths, .3mm gap, .5mm substrate and .1mm coating use
35/50um metal. Coarse mesh (edge5um/far.25mm/grade.2) to fine
(2.5um/.125mm/.1) C/Z change must be below1.5%; separate box12→24mm and
upper-air6→12mm changes below.5%. Reflected conductor permutation and replacing
a vacuum film by air at the same top height also require below.5%. Coefficient
scaling, vacuum identity, common loss and reciprocity use1e-12.

Independent scikit-fem12.0.2 (BSD-3-Clause, test-only) complex/vacuum P1 energy
on the same mesh checks C/C_loss/C0 within normalized1e-10. This is independent
assembly, not independent geometry. A separate thin all-vacuum fixture uses
explicit signal intervals[-.55,-.25]/[.05,.55]mm, height.5mm and a grounded-image
integral panel reference. Reference80→160-panel C/Z changes must be below.3%;
coarse-to-fine FEM errors must decrease and finish below2%. Doubling box and air
must change C/Z below1%.

The fixed-pitch left-width goal uses [.08,.85]mm, target100ohm, tolerance1ohm
and at most30 evaluations. Fine, automatic half refinement, doubled box and
doubled air must all retain the same width within the target tolerance; outer
changes must also be below.5%. Material/full-complex replay uses1e-10. These
fixture checks do not certify measured boards, radiation, 3D transitions,
browser execution or Windows builds.
