# Saved lossy scalar-line goals

[Explicit /2 paired goals](differential_goal_document.md) add an asymmetric forward launch. The default /1 and the scalar contract below remain unchanged.

[한국어](../../locales/ko/pages/packages/sipi/line_goal_document.md) · [Goal API](line_goal.md) · [Study inputs](study.md)

`sipi.line-quantity-design/1` saves a bounded scalar goal without a Python
callable. It reuses a study's template, parameters, material bindings, mesh and
interval, then runs the [lossy goal API](line_goal.md). It never runs a preliminary
impedance study.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_goal_document import LineQuantityDesignDocument
from sipi.execution import normalize_saved, execute_saved

mesh = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)
source = ImpedanceStudyDocument('stripline', dict(width=.5e-3, plane_spacing=1e-3,
    thickness=50e-6, eps_r=4., tan_delta=.02, box_width=4e-3),
    quantity='z0', frequency=1e9, materials={}, mesh=mesh,
    sampling=dict(kind='sweep', count=2,
        variables=[dict(name='width', lower=.3e-3, upper=.8e-3)]))
goal = LineQuantityDesignDocument(source,
    conductor=dict(kind='surface', conductivity=58e6, relative_permeability=1.,
        roughness=dict(kind='hammerstad', rms_m=.5e-6), ground_thickness=35e-6),
    quantity='impedance_real', target=50., tolerance=.5, max_evaluations=24)
assert normalize_saved(goal.dumps()) == goal.dumps()
report = execute_saved(goal.dumps(), max_evaluations=24)
assert report['status'] == 'complete'
assert abs(report['result']['residual']) <= .5
assert abs(report['result']['refined_residual']) <= .5
assert report['result']['input']['schema'] == 'sipi.transmission-line/6'
```

The object has exactly `schema`, `study`, `conductor`, `quantity`, `target`,
`tolerance` and `max_evaluations`. Unknown/missing fields, duplicate JSON keys
and nonfinite numbers reject. Goal quantity is `impedance_real` (Re(Zc), ohm) or
`attenuation` (Re(gamma), Np/m), with the API's explicit positive tolerance.
It does not target abs(Zc) or finite-line insertion loss.

The nested study must be version 3 or 4, with explicit material evaluation at
one positive frequency, `quantity='z0'`, sweep sampling, count 2 and exactly one
variable with positive increasing bounds. Nested `z0` selects the scalar source
contract; it is not the new goal's value. The old study schema/meaning is retained.
Count 2 defines endpoints, not the number of goal evaluations. Stochastic/corner
sampling, multiple variables and pair modal goals are rejected. Version 4 can
bind a single numeric material-model leaf. Existing fixed total plane spacing
is preserved for supported scalar layered templates.

The fixed conductor is a strict line/6 record, including ground-face laws when
present. Trials use zero-length line/6 at a 50-ohm power-wave reference; this
reference does not set the characteristic impedance target. Frequency stays fixed.

```python
import json
from sipi.dielectric import ConstantDielectric

loss_source = ImpedanceStudyDocument('stripline', dict(width=.5e-3,
    plane_spacing=1e-3, eps_r=1., box_width=4e-3), quantity='z0', frequency=1e9,
    materials={'dielectric': ConstantDielectric(4., .02)}, mesh=mesh,
    material_variables={'loss': dict(region='dielectric', path=['tan_delta'])},
    sampling=dict(kind='sweep', count=2,
        variables=[dict(name='loss', lower=.01, upper=.1)]))
loss_goal = LineQuantityDesignDocument(loss_source, conductor=dict(kind='perfect'),
    quantity='attenuation', target=1., tolerance=.001, max_evaluations=24)
result = LineQuantityDesignDocument.loads(loss_goal.dumps()).solve()
assert max(abs(result.residual), abs(result.refined_residual)) <= .001
assert result.document.to_dict()['materials']['dielectric']['parameters']['tan_delta'] == result.parameter
json.dumps(result.to_dict(), allow_nan=False)
```

Parsing performs no meshing, study or goal solve. Existing study endpoint
geometry/material preflight remains active, with added nominal conductor guards.
Later failures, including endpoint skin depth or an invalid interior trial, count
as factory attempts. No repair or dropped sample occurs. Selected geometry and
material inputs are frozen for refinement.

Shared execution rejects a saved budget above the caller's limit before field
work without clamping. Success retains values, units, requested/refined line
inputs and every completed trial. Full matrices are available in the Python
result or by replaying retained lines. `LineQuantityGoalError` gives failed
status, null result, and attempts, stage, failed parameter, cause type, available
trial input and completed history. Invalid saved input still raises. Optional
diagnostics require a top-level line document, not this goal. Budgets do not
limit memory or elapsed time.

Tests require exact saved/direct histories and inputs, RLGC/value agreement
within 1e-10, finite-metal requested/refined residuals within 0.5 ohm, and
material-leaf attenuation residuals within 0.001 Np/m with analytic tangent
agreement within 0.5%. Independent scikit-rf Zc/gamma checks use identical RLGC
and require relative error below 1e-10. Prior API field/mesh/box evidence remains
separate from this transport acceptance. No measured fitting, multimode goal,
global optimum, continuous-band, app or Windows acceptance is implied.

```sh
python -m pytest -q tests/sipi/test_line_goal_document.py tests/sipi/test_execution.py tests/sipi/test_material_variables.py
```
