# Lossy differential forward-impedance goal

[Saved /2](differential_goal_document.md) connects this API to JSON requests.

[한국어](../../locales/ko/pages/packages/sipi/differential_line_goal.md) · [Goal API](line_goal.md) · [Forward matrices](characteristic.md)

`differential_forward_impedance_real` targets Re(Zdd) in ohms for exactly two
ordered signals at one fixed positive frequency. It uses the full lossy forward
characteristic matrix, including asymmetric geometry, dielectric and metal laws.
With u=[1,-1], Zdd=u Zc u^T. The launch coordinates are Vd=V1−V2,
Vc=(V1+V2)/2, Id=(I1−I2)/2 and Ic=I1+I2. At the launch plane Ic=0,
so Vd=Zdd Id and Vc=Zcd Id. Common voltage generally remains nonzero.

This is a specified forward-current launch, not an uncoupled differential
mode, a finite-terminal input impedance or an assertion that Ic stays zero
along the line. No absolute value or exchange-symmetric projection is used.
A real target leaves the imaginary part unconstrained. Inspect the retained
complex matrix and coupling. Existing reciprocal/passive/conditioning checks
still apply; a diagnostic failure cannot be treated as a valid candidate.

The example keeps center pitch at 0.95 mm while changing the first width.
Thickness, conductivity and roughness differ between the two signals.

```python
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_goal import seek_line_quantity

def pair(width):
    section = asymmetric_coupled_microstrip(left_width=width, right_width=.5e-3,
        gap=.95e-3-(width+.5e-3)/2, substrate_height=.5e-3, eps_r=4., tan_delta=.02,
        left_thickness=35e-6, right_thickness=50e-6, air_height=5e-3, box_width=12e-3)
    def metal(sigma, rms):
        return dict(conductivity=sigma, relative_permeability=1.,
                    roughness=dict(kind='hammerstad', rms_m=rms))
    cross = CrossSectionDocument(section,
        mesh=dict(edge_size=2.5e-6, far_size=.125e-3, grade=.075))
    return TransmissionLineDocument(cross, [1e9], materials={}, length=0.,
        schema='sipi.transmission-line/3', conductor=dict(kind='surface-boundaries',
            conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
            reference=metal(58e6, 0.), ground_thickness=35e-6))

goal = seek_line_quantity(pair, [.2e-3, 1e-3], 100.,
    quantity='differential_forward_impedance_real', tolerance=.5, max_evaluations=24)
assert max(abs(goal.residual), abs(goal.refined_residual)) <= .5
mixed = goal.result.characteristic().mixed_mode()
assert goal.value == mixed.z_characteristic[0, 0, 0].real
assert abs(mixed.z_characteristic[0, 1, 0]) > 1
selected_input = goal.document.dumps()
```

Signal order and frequency stay fixed; length is zero. The API's positive
bounds, counted failure budget, complete input history and frozen refinement
are the same as for [scalar goals](line_goal.md). Both original and halved mesh
controls must meet the target tolerance. Bisection is a bounded search, not a
proof of global optimality, monotonicity or continuity. Outer-domain convergence
remains a separate check. The selected `TransmissionLineDocument` can be saved;
the factory itself is not serialized. Saved `line-quantity-design/1` and
`line-quantity-study/1` remain scalar-only and reject this quantity.

The asymmetric 100-ohm fixture requires requested, refined and enlarged-box/air
residuals at most 0.5 ohm, outer change below 0.5%, and replayed RLGC/Zc agreement
within 1e-10. Independent scikit-rf scalar modes under a known nonorthogonal
transform and a separate 2N telegrapher forward eigenspace each require Zc/Zdd
relative agreement within 1e-10. The latter reference uses positive-phase roots
of a balanced voltage/current block matrix, independently of the production
Schur square root. Symmetric modal and lossless asymmetric forward limits are
also checked within 1e-10. These algebraic and numerical checks establish no
new measured geometry accuracy, full-wave validity, app or Windows acceptance.

```sh
python -m pytest -q tests/sipi/test_differential_line_goal.py tests/sipi/test_line_goal.py tests/sipi/test_line_goal_document.py tests/sipi/test_line_study.py tests/sipi/test_characteristic_matrix.py tests/sipi/test_mixed_characteristic.py
```
