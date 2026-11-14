# Saved shape-current resolution checks

`ShapePanelResolutionDocument` saves the [separate resolution comparisons](shape_panel_resolution.md)
as `sipi.shape-panel-resolution/1`. Its seven required keys are `schema`, `line`,
`refined_panel`, `outer_lines`, `tolerances`, `refinement_factor` and `max_solves`.
Only explicit shape-current line documents are accepted, including fixed coated
metals. Unknown, missing, duplicate and nonfinite JSON values are rejected.

Tolerance keys use SI names: `R_ohm_per_m`, `L_internal_h_per_m`,
`L_external_h_per_m`, `C_f_per_m`, `G_s_per_m` and `C0_f_per_m`.
Each contains explicit `relative` and `absolute` values. Normalization checks the
entire plan without field work. It does not choose tolerances or expand scope.
The shape derivative step remains fixed across every stage.

Both saved `max_solves` and caller `max_evaluations` bound **complete line
evaluations**. Four base/refined stages plus every outer input must fit both
budgets before fields. They do not count the internal shared panel calls and
are distinct from the frequency-count admission of a top-level saved line.

Common execution and `SavedExecutionRequest` preserve these outcomes:

- Completed comparisons use `status: complete`, a result and null error.
  `accepted: false` remains a valid completed assessment, not a passing check.
- Field failures use `status: failed` and null result. The typed error's
  `partial_assessment` retains preceding evaluations, original stage/input/cause,
  complete or partial current samples and derivative-step diagnostics.
- Interrupts propagate. Admission failures occur before field work.

Both outcomes fit `SavedExecutionRecord` without recalculating on load or prepare.
Existing record byte limits still apply to large collections of current samples.
Artifact declarations are host claims, not an accuracy or execution certificate.
The example selects only C0 with a deliberately loose 10% allowance to demonstrate
transport. It does not qualify resistance, outer-domain sufficiency or accuracy.

```python
from sipi import CrossSection, Layer, Trace, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.shape_panel_resolution_document import ShapePanelResolutionDocument
from sipi.execution import normalize_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.line_resolution import ResolutionTolerance

section = CrossSection([Layer('uniform', .002, 4.2, tan_delta=.02)],
    [Trace('left', -.0003, .0005, .0002, thickness=35e-6),
     Trace('right', .0003, .0005, .0002, thickness=35e-6)], .004)
line = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1)), [1e9],
    materials={}, conductor={'kind': 'perfect'}, length=0.)
base = ShapePanelTransmissionLineDocument(PanelTransmissionLineDocument(
    line, panels_per_edge=16, ground_modes=512, interpolation_degree=16))
fine = dict(panels_per_edge=32, ground_modes=1024, interpolation_degree=16)
raw = base.to_dict()
raw['line']['panel'] = dict(fine, ground_modes=2048)
cross = raw['line']['line']['cross_section']
cross['box']['width'] *= 2
cross['layers'][-1]['thickness'] *= 2
for key in ('edge_size', 'far_size', 'grade'):
    cross['mesh'][key] *= .5
outer = ShapePanelTransmissionLineDocument.from_dict(raw)
saved = ShapePanelResolutionDocument(base, refined_panel_options=fine,
    outer_documents=[outer], tolerances={'C0': ResolutionTolerance(.1, 0.)},
    max_solves=5)
text = saved.dumps()
assert normalize_saved(text) == text
receipt = SavedExecutionRequest(text, max_evaluations=5).run()
out = receipt['execution']
assert out['status'] == 'complete' and out['error'] is None
assert out['result']['completed'] and out['result']['accepted']
assert len(out['result']['evaluations']) == 5
assert len(out['result']['evaluations'][0]['current_solver']['samples']) == 13
```

[한국어](../../locales/ko/pages/packages/sipi/shape_panel_resolution_document.md)
