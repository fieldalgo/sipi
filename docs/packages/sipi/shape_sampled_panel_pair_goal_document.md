# Saved finite-frequency shape-current pair goals

`ShapeSampledPanelForwardPairDesignDocument` explicitly saves a
[finite-frequency shape-current goal](shape_sampled_panel_pair_goal.md) as
`sipi.shape-sampled-panel-forward-pair-design/1`. Its required keys are
`schema`, `design` and `step_fraction`. `design` is an existing
`SampledPanelForwardPairDesignDocument` version 1 or 2; version 2 preserves
fixed coated per-boundary metal laws. Existing inputs and default current
methods are unchanged.

Each of 2–64 increasing positive frequencies needs two explicit positive
real targets and tolerances: `differential_forward_impedance_real` and
`common_forward_impedance_real`, in ohms. Arrays have one entry per frequency;
there is no scalar broadcast. The source study frequency equals the first
requested frequency. Two positive bounded variables, their ordering, fixed
pitch/material leaves and the entire grid retain the nested input contract.

Normalization solves no fields. It admits the nominal input, initial point
(or midpoint), four corners and each planned volume/panel/joint refinement,
including shape offsets and the full material frequency range. These checks
do not guarantee every continuous interior point can be solved. Missing,
unknown, duplicate and nonfinite fields are rejected.

`solve()` passes the saved budget, grid, targets and tolerances to the direct
API. The selected result and all three refinements must meet every target;
original relative refinement checks remain unchanged. Budgets count whole
uncached grid attempts, including probes and failures. Common execution
rejects a caller budget smaller than the saved budget before any field work.

Success preserves selected/refined current samples and completed history.
Failure has a null result and the original frequency vector, attempts, stage,
failed parameters/input and completed history. A `ShapePanelLineError` cause
adds `cause_details`, including partial current work. Interrupts propagate.
`SavedExecutionRecord` round-trips success or failure without solving again;
its existing size limits, digest checks and host artifact declarations apply.

The example prepares a request without solving it. Repeated targets here are
explicit user specifications, not a claim that this geometry meets them. Run
`prepared.run()` to attempt the search. A normalized request is not a result.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_goal_document import SampledPanelForwardPairDesignDocument
from sipi.shape_sampled_panel_pair_goal_document import ShapeSampledPanelForwardPairDesignDocument
from sipi.execution import normalize_saved
from sipi.execution_request import SavedExecutionRequest

study = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3,
         substrate_height=.5e-3, eps_r=4., tan_delta=.02,
         left_thickness=35e-6, right_thickness=50e-6,
         air_height=.01, box_width=.024),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='corners', variables=[
        dict(name='left_width', lower=.4e-3, upper=.9e-3),
        dict(name='gap', lower=.2e-3, upper=.6e-3)]))
quantities = ('differential_forward_impedance_real',
              'common_forward_impedance_real')
original = SampledPanelForwardPairDesignDocument(study, conductor={'kind': 'perfect'},
    frequencies=[1e9, 2e9, 4e9],
    targets=dict(zip(quantities, [[110.]*3, [40.]*3])),
    tolerances=dict(zip(quantities, [[.25]*3, [.125]*3])),
    initial=[.7e-3, .35e-3], max_evaluations=64)
saved = ShapeSampledPanelForwardPairDesignDocument(original, step_fraction=.001)
text = saved.dumps()
assert normalize_saved(text) == text
prepared = SavedExecutionRequest(text, max_evaluations=64)
assert prepared.to_dict()['input'] == saved.to_dict()
# receipt = prepared.run()  # Starts actual fields and bounded optimization.
```

The finite bottom-ground/open-wall geometry and finite grid do not establish outer-domain sufficiency, small mutual-entry accuracy, a continuous-band bound, measured accuracy, uniqueness or a global optimum.
