# Independently oriented Debye tensors

[한국어](../../locales/ko/pages/packages/sipi/tensor_debye.md) · [Fixed principal axes](principal_dielectrics.md) · [Material studies](material_variables.md) · [Material goals](material_goals.md)

`TensorDebyeDielectric` describes a reciprocal transverse relative permittivity
with independent real orientations for the high-frequency tensor and each
positive-semidefinite Debye residue. Frequencies are Hz and angles are radians
counterclockwise from global transverse x. In the `exp(+j omega t)` convention,

`eps(f) = R(theta_inf) diag(eps_inf) R(theta_inf)^T
        + sum_k R(theta_k) diag(strengths_k) R(theta_k)^T / (1 + j*f/pole_k)`.

`eps_inf` has two finite real entries at least one. `strengths` has 1–64 pairs
of finite nonnegative entries, `relaxation_hz` has one strictly positive finite
pole per pair, and `angles_rad` has the same length. `eps_inf_angle_rad` is a
finite real scalar, default zero. Booleans and complex inputs are rejected.
The conservative static bound `max(eps_inf) + sum(max(strengths_k))` must be
finite. Inputs become immutable tuples; returned arrays and records are detached.
Scalar frequency gives `(2,2)` and a nonempty frequency vector gives `(F,2,2)`;
zero frequency is allowed for material evaluation. Line analyses retain their
existing positive-frequency requirements.

Different residue orientations can produce frequency-dependent, noncoincident
real and loss principal axes. The model does not assume a common rotating frame
or track eigenvectors. `Re(eps)` is positive definite and `-Im(eps)` positive
semidefinite; the sign of an individual off-diagonal entry is not a passivity
test. Each causal relaxation has impulse response
`2*pi*pole_k*A_k*exp(-2*pi*pole_k*t)*H(t)` and a negative-real Laplace pole.
These properties describe this finite family, not a measured laminate or an
arbitrary causal anisotropic spectrum. Longitudinal/magnetic response, full-wave
propagation and tensor parameter fitting are outside this contract.

## Material input and saved line

```python
import json
import numpy as np
from sipi import CrossSectionDocument, coupled_microstrip
from sipi.dielectric import TensorDebyeDielectric, dielectric_to_dict, dielectric_from_dict
from sipi.line_model import TransmissionLineDocument
from sipi.execution_request import SavedExecutionRequest

material = TensorDebyeDielectric(
    eps_inf=[2, 3], strengths=[[4, .5], [.25, 3]],
    relaxation_hz=[1e8, 1e10], angles_rad=[0, np.pi/4],
)
record = dielectric_to_dict(material)
assert record['schema'] == 'sipi.dielectric/3'
assert dielectric_from_dict(json.loads(json.dumps(record))) == material
section = coupled_microstrip(width=.5e-3, gap=.3e-3,
    substrate_height=.5e-3, thickness=35e-6, eps_r=4,
    box_width=8e-3, air_height=4e-3)
document = TransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=10e-6, far_size=.25e-3, grade=.2)),
    [1e6, 1e8, 1e10], materials={'substrate': material},
    conductor={'kind': 'perfect'}, length=.01,
)
request = SavedExecutionRequest(document.dumps(), max_evaluations=3)
receipt = request.run()
assert receipt['execution']['status'] == 'complete'
assert receipt['execution']['input'] == document.to_dict()
```

The nested material schema is exactly `sipi.dielectric/3`, kind `tensor-debye`,
with exactly the five constructor fields in `parameters`, including the default
angle. Unknown or missing keys and invalid field values are rejected. Scalar
`/1` and fixed-axis `/2` inputs retain their meanings; tensor models cannot be
children of `PrincipalAxisDielectric`. Existing line/study/goal envelopes embed
this material version without a new top-level saved schema. Old readers reject
it. Geometry `eps_r` remains scalar: `section.analyze()` alone uses its geometry
defaults. Apply this model through the frequency-dependent material mapping.
The example's mesh is illustrative; request identity does not certify numerical
accuracy, host cancellation or platform support.

## Material variation

Existing material-variable bindings select numeric leaves such as
`['strengths', 0, 0]`, `['relaxation_hz', 0]` or `['angles_rad', 1]`.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

study = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
         substrate_height=.5e-3, eps_r=4, left_thickness=35e-6,
         right_thickness=50e-6, box_width=12e-3, air_height=6e-3),
    quantity='z_diff_forward', frequency=1e8,
    materials={'substrate': material},
    material_variables={'d': dict(region='substrate', path=['strengths', 0, 0])},
    sampling=dict(kind='uniform', count=2, seed=71,
                  variables=[dict(name='d', lower=2, upper=4)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
result = study.analyze()
assert result.failed == 0
for row, sample in zip(result.rows, study.samples()):
    actual = json.loads(row.material_evaluation_json)
    assert actual['materials']['substrate']['parameters']['strengths'][0][0] == sample[0]
```

Saved study `/4` keeps invalid normal samples as failures, including the original
material snapshots and denominator; it does not resample them. Saved goal `/3`
can search one strictly positive numeric leaf while fixing geometry and
observation frequency. The chosen material snapshot is retained for refinement.
The target remains real quasi-static impedance from `Re(C)` and vacuum external
inductance. It does not become a complex impedance or attenuation optimizer;
no uniqueness, availability or measured validity of the fitted material follows.
Existing budget, bracket and requested/refined residual checks apply.

## Verification boundaries

```sh
python -m pytest -q -s tests/sipi/test_tensor_debye.py tests/sipi/test_tensor_debye_fields.py
```

Checks cover an independently stored rational/rotation reference, fixed-axis
and isotropic reductions, passivity, covariance, immutable/strict inputs and
extreme finite frequencies. The reference contract and generator are retained
under `tests/sipi/reference_data/tensor_debye`; regenerating it is not a substitute
for matching the committed values.

The complex layered capacitor requires relative error below `1e-9`. A transformed
elliptic coax uses three radial/angular refinements, decreasing error, final
error below 0.1% and final observed order at least 1.5. An unequal-angle coupled
line at 1 MHz, 100 MHz and 10 GHz uses independent scikit-fem 12.0.2 tensor
assembly, normalized complex-C error below `1e-9`, and separate mesh, box-width
and air-height changes below 1%. Network reciprocity/passivity tolerance is
`1e-10`. These checks qualify the declared fixtures, not arbitrary geometries.

The material study replays both selected samples within relative `1e-10`.
An isotropic pole goal uses the independent Cohn stripline formula at effective
permittivity 3.5, requires the recovered pole within 1.5% of 100 MHz and both
requested/refined residuals within 0.1 ohm. This checks material-goal wiring with
an independent analytic target; it is not a general anisotropic impedance formula.
No measured-data, new platform, browser or portable-binary validation is implied.
