# Single material parameter impedance goals

[한국어](../../locales/ko/pages/packages/sipi/material_goals.md) · [Material studies](material_variables.md) · [Geometry design](design.md)

`ImpedanceDesignDocument` writes `sipi.impedance-design/3` when
`material_variables` is supplied. It adds this required object to version 2's
fields, with exactly one alias matching `variable`. The alias selects one numeric
material-model leaf using the [study binding contract](material_variables.md).
Geometry and observation frequency are fixed in this saved material search.
Versions 1 and 2 retain their original meanings.

```python
from sipi.design_document import ImpedanceDesignDocument
from sipi.dielectric import ConstantDielectric
import json

plan = ImpedanceDesignDocument('stripline',
    dict(width=.5e-3, plane_spacing=1e-3, eps_r=1),
    variable='dk', bounds=[2, 8], target=50, tolerance=.25,
    frequency=1e8, materials={'dielectric': ConstantDielectric(4)},
    material_variables={'dk': dict(region='dielectric', path=['eps_r'])},
    mesh=dict(edge_size=2e-6, far_size=.125e-3, grade=.15))
result = ImpedanceDesignDocument.loads(plan.dumps()).solve()
assert abs(result.residual) <= .25
assert abs(result.refined_residual) <= .25
actual = json.loads(result.material_evaluation_json)
assert actual['materials']['dielectric']['parameters']['eps_r'] == result.parameter
```

The result's parameter has the selected model field's units, such as relative
permittivity or Hz. Bounds must both be strictly positive, finite and increasing;
this API does not search zero or negative loss/angle intervals even if those
values are legal in a study. The nominal model and both endpoints must be valid.
All intermediate models are validated too. A legal model is not evidence of its
measured validity, manufacturability or availability as a real material.

The scalar goal remains real quasi-static impedance from `Re(C)` and vacuum
external inductance. This is neither complex characteristic impedance nor an
attenuation, bandwidth, yield or multi-variable optimization goal. A loss-tangent
parameter may have no effect on this real target in a homogeneous medium; an
unbracketed target is rejected rather than presented as a fitted material.

The existing bisection contract is unchanged: both endpoint solves are checked,
one solve is reserved for refinement, and the candidate must satisfy the target
on both requested and refined meshes. Refinement halves edge size, far size and
grading. The finite outer boundary is unchanged; check it separately. Nonmonotonic
models do not acquire uniqueness or global-optimality guarantees from bisection.

`result.document` contains the selected geometry and requested mesh, while
`material_evaluation_json` contains the **selected** material snapshot, not the
nominal input. Save both for direct replay, or preserve the complete design JSON
for rerunning the search. Shared saved execution accepts version 3 and retains
this snapshot, residuals, refinement and completed-search history. Existing
`GoalSeekError` behavior and budget gates remain in force; invalid factory/model
inputs propagate their validation error rather than becoming a successful goal.

For a Python-defined search, `seek_impedance(..., frequency=f,
material_factory=models_at_parameter)` accepts a callback returning a supported
region-to-model mapping. It is mutually exclusive with `materials`. The geometry
factory still receives the same scalar parameter; Python callers can explicitly
couple geometry and material changes, unlike the fixed-geometry saved contract.
Each search evaluation captures the returned model mapping immediately. The
chosen snapshot is reused for refinement without calling the callback again.
Callbacks must be deterministic for a reproducible search. No callback or code
is serialized in the saved document.

Validation infers homogeneous stripline permittivity from the independent Cohn
formula within 1%, checks requested/refined residuals within 0.25 ohm, and compares
a Debye relaxation goal with its independent real-permittivity formula (pole
within 1.5%, requested/refined residuals within 0.1 ohm on a 1um/0.1-grade
requested mesh). A 0.25-ohm stop was insufficient for the pole criterion; the
acceptance tolerance was tightened rather than relaxing that criterion. Selected material replay must agree within relative 1e-10.
Endpoint-selection tests verify that refinement uses the correct snapshot and
makes no extra callback. Malformed contracts, unbracketed goals, evaluation limits
and shared execution are checked alongside the existing design/material tests.
This extends orchestration, not the physical field solver. Existing pinned
workbench builds do not automatically contain the new schema.

```sh
python -m pytest -q tests/sipi/test_material_goals.py tests/sipi/test_material_variables.py tests/sipi/test_material_impedance.py tests/sipi/test_design_documents.py tests/sipi/test_impedance_design_document.py tests/sipi/test_execution.py
```
