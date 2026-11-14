# Bounded shape-current panel and volume refinement

`refine_shape_panel_line_resolution` accepts a
`ShapePanelTransmissionLineDocument` and two to four explicit
`ShapePanelResolutionRefinement(panel_options, outer_documents)` steps.
Each step specifies finer panel controls and outer shape-line documents at its
exact finer volume resolution. Panel controls cannot decrease and at least
one increases; volume `edge_size`, `far_size` and `grade` decrease by the same
`refinement_factor`. Outer sizes and order stay fixed across steps. Ground
modes may increase for the outer domain. All physical, frequency, port and
metal inputs and `step_fraction` stay fixed. Both nested metal versions work.

All planned levels, outer inputs and shape offsets are admitted before fields.
The same bounded state machine as [panel refinement](adaptive_panel_resolution.md)
requires volume/base, panel/base, joint/volume and joint/panel to pass at two
consecutive levels. A failed level resets the count. The previous joint result
is reused as the next base. Only then are that level's outer inputs solved.
Outer disagreement stops; further panel work cannot hide an outer mismatch.

Every selected matrix entry at every frequency uses the explicit SI allowance
`abs(a-b) <= absolute + relative * max(abs(a), abs(b))`. There is no small-entry
floor. Omitted quantities are not tested. The shape derivative's two-step
check remains active in every extraction. Acceptance is finite agreement,
not an absolute error bound, asymptotic convergence, continuous-band guarantee
or physical-model/measurement validation.

`max_solves` is an integer from 8 to 32, counting whole line batches rather than
internal panel solves. The next three batches and all outer checks must fit
before a level starts. `accepted` selects the joint result on the original
domain. `resolution-unaccepted` and `outer-unaccepted` are completed but have
no selected result; `budget-exhausted` and `field-failed` are incomplete.
Interrupts propagate. All unaccepted outcomes have `selected_evaluation=None`.

`AdaptiveShapePanelResolution.to_dict()` preserves exact inputs, full matrix
observations and comparisons, all shape-current samples, stop reason and
selected index. Field failures retain prior work and the exact failed input;
a shape-line cause adds its original complete/partial current details. This is
a result report, not a saved execution input schema.

This example only prepares a two-level plan. Its loose 10% C0 allowance is a
control-flow example; it does not qualify resistance or small mutual terms.
Call the commented line to start fields and retain every unaccepted outcome.

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
# result = refine_shape_panel_line_resolution(base, **controls)  # Starts fields.
```

[Saved plans and receipts](adaptive_shape_panel_resolution_document.md).
