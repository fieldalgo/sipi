# Saved two-variable forward impedance targets

[한국어](../../locales/ko/pages/packages/sipi/pair_line_goal_document.md) ·
[Direct API](pair_line_goal.md) · [Saved scalar and paired goals](line_goal_document.md)

`ForwardPairDesignDocument` saves two ordered geometry/material variables and
two explicit full-loss forward-current targets. Its schema is
`sipi.forward-pair-design/1`. The seven root keys are `schema`, `study`,
`conductor`, `targets_ohm`, `tolerances_ohm`, `initial` and `max_evaluations`.
Targets and tolerances each contain exactly
`differential_forward_impedance_real` and `common_forward_impedance_real`.
Their values are positive finite ohms. The direct API defines the separate
Ic=0 and Id=0 forward launches and retains asymmetric complex coupling.

## Save and execute

The nested `impedance-study/3` or `/4` supplies paired `z_diff_forward`
template inputs, one fixed positive frequency and `corners` sampling with
exactly two ordered, positive-bounded variables. That label selects the
paired input contract only: no quasi-static source study or corner field
study runs. Geometry dimensions are metres, frequency Hz and conductivity S/m.

This short example starts at a qualified point and still runs the required
mesh refinement. To perform the full width/gap search instead, set
`initial=[.7e-3, .35e-3]` and `max_evaluations=64` in both the document and
the outer executor budget. The numerical tests exercise that full search.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.pair_line_goal_document import ForwardPairDesignDocument
from sipi.execution import normalize_saved, execute_saved

def surface(conductivity, rms):
    return dict(conductivity=conductivity, relative_permeability=1.,
                roughness=dict(kind='hammerstad', rms_m=rms))

study = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3,
         substrate_height=.5e-3, eps_r=4., tan_delta=.02,
         left_thickness=35e-6, right_thickness=50e-6,
         box_width=24e-3, air_height=10e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='corners', variables=[
        dict(name='left_width', lower=.4e-3, upper=.9e-3),
        dict(name='gap', lower=.2e-3, upper=.6e-3)]))
quantities = ('differential_forward_impedance_real',
              'common_forward_impedance_real')
doc = ForwardPairDesignDocument(study,
    conductor=dict(kind='surface-boundaries',
        conductors={'positive': surface(58e6, .5e-6),
                    'negative': surface(35e6, 1e-6)},
        reference=surface(58e6, 0.), ground_thickness=35e-6),
    targets=dict(zip(quantities, [110., 40.])),
    tolerances=dict(zip(quantities, [.25, .125])),
    initial=[.6013576047896128e-3, .4103854246303812e-3],
    max_evaluations=2)
assert doc.to_dict()['schema'] == 'sipi.forward-pair-design/1'
assert normalize_saved(doc.dumps()) == doc.dumps()
result = ForwardPairDesignDocument.loads(doc.dumps()).solve()
```

The outer budget must cover the saved attempt budget before any solve.
No callback, code, file path or network operation is serialized. Canonical
round trips preserve the two variable positions; target objects use explicit
keys rather than object insertion order.

```python
import json
import numpy as np
report = execute_saved(doc.dumps(), max_evaluations=2)
assert report['status'] == 'complete'
assert report['input'] == doc.to_dict()
assert report['result'] == result.to_dict()
assert report['result']['quantities'] == list(quantities)
assert report['result']['evaluations'] == 2
assert np.all(abs(np.array(result.residuals)) <= result.tolerances)
assert np.all(abs(np.array(result.refined_residuals)) <= result.tolerances)
json.dumps(report, allow_nan=False)
```

## Preflight and execution contract

Parsing checks nominal and four corner geometry/material inputs, and builds
the initial line without meshing. A null initial value means the midpoint of
each bound; an explicit initial point must lie in the closed bounds. The
attempt budget is an integer from 2 to 10000. Boolean/nonfinite values,
duplicate or unknown keys and unsupported schema versions are rejected.

Existing fixed center pitch, total layer height, typed material models and
numeric material-leaf bindings retain their study semantics. The nominal
resolved mesh controls are reused. The conductor is a fixed, explicit
transmission-line/6 record; nominal and initial line construction validate it.
Preflight does not certify conductor validity at every corner or physical
validity throughout the search domain. It is outside the solve attempt
budget and is not a worst-case or statistical assessment.

Solving delegates to the direct two-variable API. Its uncached attempt count,
original failures, final reserved refinement and dual target tests remain
unchanged. Chosen/refined inputs are zero-length line/6 records at a 50-ohm
network reference; that reference does not define Zdd or Zcc. No source
sampling, clipping, resampling or physical repair occurs.

`execute_saved` returns `status='failed'` for a direct goal failure, with
completed history, attempts, stage, failed parameters, original cause type,
message and the available failed input. It does not turn unresolved attempts
into successful rows. Optional top-level line diagnostics are rejected for
this goal document. Successful reports and underlying R/L/G/C remain
inspectable through the direct result; saved reports are transport independent.

## Validation and limits

Saved/direct/executor reports match on independent modal known-root cases;
variable order, strict input, no-preliminary-solve behavior, pitch/stack and
material-leaf factories are checked. Original failure and budget information
survive the execution adapter. All prior canonical saved inputs remain exact.

The asymmetric 1 GHz width/gap example matches the direct full search's
inputs and history exactly, and full requested/refined RLGC within 1e-10.
Both targets satisfy (.25,.125) ohm on both meshes, with each mesh change
at most 0.5%. Refined 36/15 and 48/20 mm box/air domains meet the same
target tolerances and 0.5% relative gates, with decreasing successive absolute
changes. Independent balanced 2N eigenspaces compare Zc/Zdd/Zcc within 1e-10.
A uniform PEC pair with two material leaves checks complex dielectric scaling
against an independent SPD vacuum characteristic on both meshes within 1e-10.
The latter starts at a matching point and does not establish a unique two-leaf
solution. Matrix comparisons reuse extracted RLGC or vacuum fields and do not
replace independent geometry extraction or measured validation.

Finite-domain tests do not certify infinite-domain error, a unique/global
optimum, full-wave accuracy, production yield or a new platform. The direct
API's resource and physical-validity limits still apply. Existing goal and
study schemas retain their previous input contracts.
