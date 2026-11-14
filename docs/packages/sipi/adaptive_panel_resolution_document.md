# Saved bounded panel refinement

`AdaptivePanelResolutionDocument` stores the explicit
`sipi.adaptive-panel-resolution/1` contract. Its six keys are `schema`, `line`,
`refinements`, `tolerances`, `refinement_factor` and `max_solves`. Each of two to
four refinement steps contains exactly `refined_panel` and `outer_lines`.
Nested panel line versions /1 and /2 preserve their explicit conductor method.
Tolerances use SI names: R_ohm_per_m, L_internal_h_per_m, L_external_h_per_m,
C_f_per_m, G_s_per_m or C0_f_per_m, with relative and absolute values.
Unknown/missing keys, duplicate keys and nonfinite JSON numbers are rejected.

Parsing validates the entire plan without fields. The direct API's separate
axes, two consecutive passes, immutable physical inputs, independent outer
checks and finite-agreement limits all remain in force. A caller budget smaller
than seven plus the outer count is rejected before solving. Otherwise the
smaller stored/caller budget applies. No implicit plan, mesh or tolerance repair
occurs. Ordinary panel-resolution/1 and line-resolution documents are unchanged.

`execute_saved` retains every completed input/result/comparison. A field failure
returns status failed with the exact failure and partial result. Budget
exhaustion returns failed with ResolutionBudgetExceeded and the partial result.
Completed but unaccepted resolution/outer checks return complete with error null
and accepted false. Only accepted results have a selected_evaluation_index;
refinement_levels, stop_reason and outer_completed distinguish terminal states.
User interrupts propagate. Result records retain all supported SI matrices,
including quantities not selected for acceptance.

This executable example selects only C0 with a deliberately loose 10% observation
allowance. It demonstrates storage and replay, not physical accuracy, resistance
qualification, continuous-band convergence or an absolute error bound.

```python
from sipi import CrossSection, Layer, Trace, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.adaptive_panel_resolution import (
    PanelResolutionRefinement, refine_panel_line_resolution,
)

section = CrossSection([Layer('uniform', .002, 4.2)],
    [Trace('left', -.0003, .0005, .0002, thickness=35e-6),
     Trace('right', .0003, .0005, .0002, thickness=35e-6)], .004)
line = TransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1)),
    [1e9, 2e9], materials={}, conductor={'kind': 'perfect'}, length=0.)
base = PanelTransmissionLineDocument(line, panels_per_edge=8)
steps = []
for level in (1, 2):
    raw = base.to_dict()
    options = dict(base.panel_options, panels_per_edge=8 * 2**level)
    raw['panel'] = dict(options, ground_modes=1024)
    cross = raw['line']['cross_section']
    cross['box']['width'] *= 2
    cross['layers'][-1]['thickness'] *= 2
    for key in ('edge_size', 'far_size', 'grade'):
        cross['mesh'][key] *= .5**level
    steps.append(PanelResolutionRefinement(
        options, [PanelTransmissionLineDocument.from_dict(raw)]))
from sipi.adaptive_panel_resolution_document import AdaptivePanelResolutionDocument
from sipi.execution import normalize_saved, execute_saved

request = AdaptivePanelResolutionDocument(base, refinements=steps,
    tolerances={'C0': ResolutionTolerance(.1, 0.)}, max_solves=8)
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=8)
assert output['status'] == 'complete' and output['error'] is None
assert output['result']['accepted']
assert output['result']['selected_evaluation_index'] == 6
assert len(output['result']['evaluations']) == 8
```
