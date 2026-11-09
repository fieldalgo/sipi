# Saved explicit panel-current pair goals

[한국어](../../locales/ko/pages/packages/sipi/panel_pair_goal_document.md) ·
[Direct panel goals](panel_pair_goal.md) · [Panel lines](panel_line.md)

`PanelForwardPairDesignDocument` saves an explicit panel-current goal as
`sipi.panel-forward-pair-design/1`. The three root keys are `schema`, `design`
and `panel`. `design` is a canonical `sipi.forward-pair-design/1` input; `panel`
contains exactly `panels_per_edge`, `ground_modes` and `interpolation_degree`.
Prior saved goals retain their original calculation method.

The nested study/3 or /4 supplies two ordered positive-bounded geometry or
material variables, one positive frequency, conductor laws, named Re(Zdd)/Re(Zcc)
targets and absolute ohm tolerances. Fixed pitch and supported material-leaf
rules retain their meaning. The nested attempt budget must be 4..10000.
The panel line's bottom-ground/open-top/open-sides and conductor restrictions
still apply: other templates are rejected, not converted to a different solver.

## Example

The example uses a previously qualified point and still performs the nominal,
volume-only, panel-only and joint evaluations. For an actual search from a
mismatching point use `initial=[.7e-3,.35e-3]` and a saved/caller budget of 64.
Lengths are metres and targets/tolerances are ohms.

```python
import json
from sipi.study import ImpedanceStudyDocument
from sipi.pair_line_goal_document import ForwardPairDesignDocument
from sipi.panel_pair_goal_document import PanelForwardPairDesignDocument
from sipi.execution import normalize_saved, execute_saved

study = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3,
         substrate_height=.5e-3, eps_r=4., tan_delta=.02,
         left_thickness=35e-6, right_thickness=50e-6,
         air_height=10e-3, box_width=24e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='corners', variables=[
        dict(name='left_width', lower=.4e-3, upper=.9e-3),
        dict(name='gap', lower=.2e-3, upper=.6e-3)]))
def metal(conductivity, rms):
    return dict(conductivity=conductivity, relative_permeability=1.,
                roughness=dict(kind='hammerstad', rms_m=rms))
conductor = dict(kind='surface-boundaries',
    conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
    reference=metal(58e6, 0.), ground_thickness=35e-6)
quantities = ['differential_forward_impedance_real', 'common_forward_impedance_real']
design = ForwardPairDesignDocument(study, conductor=conductor,
    targets=dict(zip(quantities, [110., 40.])),
    tolerances=dict(zip(quantities, [.25, .125])),
    initial=[.000603169086210573, .00040941866189257275], max_evaluations=4)
document = PanelForwardPairDesignDocument(design,
    panels_per_edge=32, ground_modes=512, interpolation_degree=10)
text = document.dumps()
assert normalize_saved(text) == text
assert PanelForwardPairDesignDocument.loads(text).dumps() == text
output = execute_saved(text, max_evaluations=4)
assert output['status'] == 'complete'
assert output['input'] == document.to_dict()
assert output['result']['evaluations'] == 4
assert [row['stage'] for row in output['result']['refinements']] == [
    'volume-refinement', 'panel-refinement', 'joint-refinement']
json.dumps(output, allow_nan=False)
```

## Admission, execution and failures

Parsing canonicalizes a deep copy and checks nominal, initial/midpoint and
four corner inputs, including the three future refinement documents. It does
not mesh or run an impedance study. These finite checks do not establish
validity throughout the search domain, skin-depth admission, field convergence
or success of a later solve. There is no input repair, resampling or fallback.
Unknown/missing/duplicate keys, unsupported versions and nonfinite JSON values
are rejected. Accessors reconstruct independent documents and panel settings.

`solve()` calls the explicit panel goal directly and returns its complete
Python result. It preserves selected/refined panel-line snapshots and original
errors. `execute_saved()` returns a JSON-compatible report with the whole saved
request and the goal's history, parameters, quantities, residuals and three
refinements. It does not serialize a Python factory. Raw matrix/field objects
are available on the direct result, not implied by the summary report.

The caller's execution budget must be at least the saved budget; it is never
silently clamped. Unsupported top-level diagnostics and oversized inputs are
rejected before solving. Control/parse errors raise exceptions. A goal failure
returns `status='failed'`, `result=null` and the original stage, cause type,
attempt count, failed parameters/input and completed history. Arrays and tuples
become JSON arrays; failed rows are not dropped or converted into success.
Callers own cancellation, process isolation and memory/time limits.

## Validation and scope

Independent modal roots check saved/direct parity and parameter ordering.
Tests cover fixed-pitch material leaves, field-free admission, resource and
transport limits, and failures from each search/refinement stage. A qualified
heterogeneous asymmetric case retains all four canonical line inputs and
matches the prior direct calculation's target values exactly in the recorded
study. Product checks execute the saved request and compare all four full
characteristic matrices with independent balanced 2N eigenspaces within 1e-10.
This reuses extracted RLGC, not independent geometry or measured data.

The common registry gains this explicit schema; previous canonical inputs
and methods remain unchanged. This is an engine execution contract, not a
claim of new browser forms, Worker/EXE integration, continuous-band acceptance,
outer-domain error bounds, global optimization or measured accuracy.
