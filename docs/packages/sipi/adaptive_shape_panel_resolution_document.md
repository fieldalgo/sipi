# Saved bounded shape-current refinement plans

`AdaptiveShapePanelResolutionDocument` saves the
[explicit adaptive shape-current plan](adaptive_shape_panel_resolution.md) as
`sipi.adaptive-shape-panel-resolution/1`. The six required keys are `schema`,
`line`, `refinements`, `tolerances`, `refinement_factor` and `max_solves`.
The line and outer inputs must explicitly select shape-panel transmission-line
version 1, with the nested legacy or fixed-coating metal law. No default method
or older request is converted.

`refinements` lists two to four steps, each with `refined_panel` (all three
controls) and `outer_lines`. Normalization checks the entire plan, including
future mesh/panel/shape-offset admission, fixed shape step, unchanged physics,
and fixed outer sizes/order, without fields. Tolerance keys carry SI units:
`R_ohm_per_m`, `L_internal_h_per_m`, `L_external_h_per_m`, `C_f_per_m`,
`G_s_per_m`, `C0_f_per_m`. Each value has exactly `relative` and `absolute`.
Every selected entry/frequency is compared without a small-entry floor.

`analyze(max_evaluations=...)` caps the saved whole-batch budget by the caller's
budget. Fewer than seven batches plus the explicit outer count is rejected
before fields. The unchanged direct state machine reserves each next three
batches and all outer checks, reuses previous joint results and requires two
consecutive four-way passes before outer work. Unused future inputs are
validated but not solved.

Common execution distinguishes completion and acceptance. `accepted`,
`resolution-unaccepted` and `outer-unaccepted` produce status `complete` and
a result retaining the accepted flag. `field-failed` and `budget-exhausted`
produce status `failed`, null result, and a typed error whose
`partial_assessment` retains all attempted inputs, completed matrices, full
current samples, comparisons and stop reason. Field failure also retains
its original kind/stage/input and complete/partial current cause. Budget
exhaustion is not a field error. Interrupts propagate.

Both existing `SavedExecutionRecord` versions can retain these new-schema
receipts and reopen/prepare them without fields. Existing record rules and
older failed-result variants are unchanged. Project records retain the same
bytes and host-declared artifact metadata. Receipt integrity is not a
numerical accuracy or measurement certificate.

The example prepares a request only. Its explicit loose C0 allowance is a
control example, not a resistance or small mutual-entry acceptance criterion.
The finite geometry/frequency domain and physical-model limits remain those
of the direct API. Call `request.run()` for actual calculations and preserve
unaccepted or partial results.

```python
from sipi import CrossSection, Layer, Trace, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.adaptive_shape_panel_resolution import (
    ShapePanelResolutionRefinement, refine_shape_panel_line_resolution,
)

section = CrossSection([Layer('uniform', .002, 4.2)],
    [Trace('left', -.0003, .0005, .0002, thickness=35e-6),
     Trace('right', .0003, .0005, .0002, thickness=35e-6)], .004)
line = TransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1)),
    [1e9, 2e9], materials={}, conductor={'kind': 'perfect'}, length=0.)
base = ShapePanelTransmissionLineDocument(PanelTransmissionLineDocument(
    line, panels_per_edge=16, ground_modes=1024, interpolation_degree=16))
steps = []
for level in (1, 2):
    raw = base.to_dict()
    options = dict(base.line.panel_options, panels_per_edge=16 * 2**level)
    raw['line']['panel'] = dict(options, ground_modes=2048)
    cross = raw['line']['line']['cross_section']
    cross['box']['width'] *= 2
    cross['layers'][-1]['thickness'] *= 2
    for key in ('edge_size', 'far_size', 'grade'):
        cross['mesh'][key] *= .5**level
    steps.append(ShapePanelResolutionRefinement(
        options, [ShapePanelTransmissionLineDocument.from_dict(raw)]))
controls = dict(refinements=steps, tolerances={'C0': ResolutionTolerance(.1, 0.)},
                max_solves=8)
from sipi.adaptive_shape_panel_resolution_document import AdaptiveShapePanelResolutionDocument
from sipi.execution import normalize_saved
from sipi.execution_request import SavedExecutionRequest
saved = AdaptiveShapePanelResolutionDocument(base, **controls)
assert normalize_saved(saved.dumps()) == saved.dumps()
request = SavedExecutionRequest(saved.dumps(), max_evaluations=8)
assert request.to_dict()['input'] == saved.to_dict()
# receipt = request.run()  # Starts actual line batches.
```
