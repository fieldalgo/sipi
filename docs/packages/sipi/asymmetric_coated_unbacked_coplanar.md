# Unequal planar-coated unbacked coplanar pair

[한국어](../../locales/ko/pages/packages/sipi/asymmetric_coated_unbacked_coplanar.md) ·
[Uncoated unequal pair](asymmetric_unbacked_coplanar.md) · [Equal coated pair](coated_unbacked.md)

`asymmetric_coupled_coated_unbacked_coplanar` puts unequal signals between two
finite coplanar grounds on a finite substrate, under a full-width planar film.
There is no backing plane or central ground. All outer boundaries are insulated;
only the finite ground traces set the reference. This is a uniform quasistatic
2D section, without an exchange-symmetry assumption.

Left/right width, thickness and optional top width are independent. Ground
traces share explicit ground_width, ground_gap and rectangular ground_thickness
(default zero); ground thickness does not follow either signal. Positive is left,
negative is right and the signal bottom span is centered. gap separates signal
bottom edges, and ground_gap separates outer signal bottom edges from grounds.
Existing taper/contact/clipping checks apply. All lengths are metres.

The ordered regions are lower_air, substrate, coating, air. Signal and ground
bottoms are at lower_air_height+substrate_height. coating_height starts there,
includes all copper and must strictly exceed every metal thickness. air_height
starts above the coating, so even a positive air height smaller than copper
thickness is geometrically valid. The film has independent coating_eps_r and
coating_tan_delta. This flat full-width film is not a conformal mask or meniscus.

Lower air defaults to ten substrate heights. Automatic upper air uses ten
substrate heights plus the largest copper thickness, measured above the film.
Specify both air heights and box width explicitly to avoid changing automatic
truncations when sampling other dimensions. Ground width is a physical variable;
box and upper/lower air are separate truncations. Enlarging grounds is not an
outer-domain convergence test.

Equal widths, thicknesses and tapers, including equal ground thickness, reproduce
the existing coupled_coated_unbacked_coplanar geometry exactly. The new factory
is registered in existing study/design JSON schemas; older readers can reject
the new template name. No new saved schema is introduced.

## Saved geometry and material studies

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved, execute_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    coating_height=.1e-3, coating_eps_r=3.3, coating_tan_delta=.015,
    left_thickness=35e-6, right_thickness=50e-6,
    ground_gap=.25e-3, ground_width=1.5e-3, ground_thickness=35e-6,
    box_width=12e-3, air_height=6e-3, lower_air_height=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_coated_unbacked_coplanar',
    parameters, quantity='z_diff_forward', fixed_pitch_m=.7e-3,
    sampling=dict(kind='uniform', count=2, seed=71, variables=[
        dict(name='left_width', lower=.28e-3, upper=.32e-3),
        dict(name='coating_height', lower=.09e-3, upper=.11e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
output = execute_saved(study.dumps(), max_evaluations=2)
assert output['status'] == 'complete'
assert output['result']['failed'] == 0
for parameters in study.sample_parameters():
    assert abs(parameters['gap']+(parameters['left_width']+parameters['right_width'])/2-.7e-3) < 1e-15
```

Use z_diff_forward for the real electrostatic forward launch with zero common
current. It is neither an odd eigenmode nor a loaded impedance; z_diff requiring
exchange symmetry is rejected. Fixed pitch derives
gap=pitch-(left_width+right_width)/2 and preserves the specified outer ground
clearances. Invalid bounded input rejects before meshing; invalid normal samples
remain failed with original parameters, without resampling or clipping.

Study/4 can vary numeric material leaves in substrate and coating. Existing iid
yield and full-complex line-quantity study/2 reuse the geometry with explicit
material/conductor definitions. The latter's differential_forward_impedance_real
is distinct from the electrostatic quantity. A reusable template does not make
every field method or conductor approximation applicable to this open-bottom
section; existing capability and skin-depth gates remain in force.

## Independent acceptance contract

For the stated unequal finite fixture, coarse (edge5um, far.25mm, grade.2) to
fine (2.5um, .125mm, .1) C/Z change must be below 1.5%. On the fine mesh,
box12→24mm, upper-air6→12mm and lower-air6→12mm each require below .5%.
Ground width1.5→3mm is reported separately as physical sensitivity. Reflected
conductor permutation and a vacuum film replaced by air at the same top height
each use .5%. Uniform coefficient scaling, vacuum identity, common loss and
reciprocity use 1e-12.

Independent scikit-fem12.0.2 (BSD-3-Clause, test-only) complex/vacuum P1 energy
on the same mesh checks C/C_loss/C0 within normalized 1e-10. It does not build an
independent geometry or mesh. A separate thin all-vacuum fixture uses neutral
free-space -log(distance) integral panels with an unknown common potential,
without an image plane or a distant grounded boundary. Explicit signal intervals
[-.55,-.25], [.05,.55]mm and ground intervals[-2.3,-.8], [.8,2.3]mm are independent
of the factory. Reference80→160-panel changes must be below .3%. At box24mm,
upper/lower air12mm, FEM (4um,.5mm,.2)→(1um,.25mm,.1) C/Z errors must decrease
and finish below2%; doubling all outer dimensions must change C/Z below1%.

The .7mm fixed-pitch left-width goal uses [.08,.85]mm, target100ohm, tolerance1ohm
and at most30 evaluations. Requested fine mesh, automatic half refinement and
separate doubled box/upper/lower air must all retain the same width within the
target tolerance, with each outer change below .5%. Material/full-complex replay
uses 1e-10. These fixture checks are not a certificate for arbitrary dimensions,
measured boards, radiation/3D transitions, browser execution or Windows builds.
