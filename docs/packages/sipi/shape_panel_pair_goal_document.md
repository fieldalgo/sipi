# Saved shape-current pair goals

`ShapePanelForwardPairDesignDocument` saves an explicitly selected
[shape-current pair goal](shape_panel_pair_goal.md) as
`sipi.shape-panel-forward-pair-design/1`. The three required keys are `schema`,
`design` and `step_fraction`. `design` is an existing
`PanelForwardPairDesignDocument` version 1 or 2. Version 2 retains fixed coated
per-boundary metals. Old saved inputs and default extraction remain unchanged.

Normalization is field-free. Besides the nominal and initial/midpoint inputs,
it checks the four parameter corners and each planned volume, panel and joint
refinement as shape-current documents. An offset collision at an unsolved corner
is rejected. These finite checks do not certify every point in continuous bounds
or guarantee future mesh/field admission. Unknown, missing, duplicate and
nonfinite input fields are rejected through the nested contracts.

`solve()` uses the nested saved attempt budget. Common execution rejects a
caller `max_evaluations` smaller than that budget before fields; it does not
silently reduce the search. The budget counts whole uncached line attempts,
including probes and failures, rather than internal panel solves or elapsed time.
Both original target tolerances and the three independent refinement checks
remain required. Outer-domain qualification is separate.

Successful execution retains the chosen and refined current samples, full input
history and targets. A failed goal has null result and a typed error containing
attempts, stage, failed parameters/input and completed history. When its cause
is a `ShapePanelLineError`, `cause_details` preserves its complete or partial
current work. Failure is not a qualified design. Interrupts propagate.
`SavedExecutionRecord` preserves either receipt and restores/prepares without
fields. Existing record byte limits and host-declared artifact semantics apply.

This example prepares and normalizes a request without running fields. Call
`prepared.run()` to start the actual bounded solve. A normalized request is not
a converged or accurate result.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.pair_line_goal_document import ForwardPairDesignDocument
from sipi.panel_pair_goal_document import PanelForwardPairDesignDocument
from sipi.shape_panel_pair_goal_document import ShapePanelForwardPairDesignDocument
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
original = ForwardPairDesignDocument(study, conductor={'kind': 'perfect'},
    targets=dict(zip(quantities, [110., 40.])),
    tolerances=dict(zip(quantities, [.25, .125])),
    initial=[.7e-3, .35e-3], max_evaluations=64)
saved = ShapePanelForwardPairDesignDocument(
    PanelForwardPairDesignDocument(original), step_fraction=.001)
text = saved.dumps()
assert normalize_saved(text) == text
prepared = SavedExecutionRequest(text, max_evaluations=64)
assert prepared.to_dict()['input'] == saved.to_dict()
# receipt = prepared.run()  # Starts actual fields and bounded optimization.
```

[한국어](../../locales/ko/pages/packages/sipi/shape_panel_pair_goal_document.md)
