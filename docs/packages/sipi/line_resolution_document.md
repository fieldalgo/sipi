# Saved line-resolution requests

`sipi.line-resolution/1` saves a [finite mesh/domain assessment](line_resolution.md)
with its original line, explicit outer lines, refinement factor, evaluation
budget and selected SI tolerances. Nested lines remain transmission-line/1
through /7. Normalization and preflight do not solve fields.

```python
from sipi import stripline, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.line_resolution_document import LineResolutionDocument
from sipi.execution import normalize_saved

section = stripline(width=.5e-3, plane_spacing=1e-3, thickness=50e-6,
                    eps_r=4., box_width=.008)
line = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=5e-6, far_size=.2e-3, grade=.1)), [1e9],
    materials={}, conductor={'kind': 'perfect'}, length=.02)
larger = line.to_dict()
larger['cross_section']['box']['width'] = .016
for key in ('edge_size', 'far_size', 'grade'):
    larger['cross_section']['mesh'][key] *= .5
request = LineResolutionDocument(line,
    outer_documents=[TransmissionLineDocument.from_dict(larger)],
    tolerances={'C': ResolutionTolerance(.005, 0.)}, max_solves=3)
assert normalize_saved(request.dumps()) == request.dumps()
```

The JSON has exactly `schema`, `line`, `outer_lines`, `refinement_factor`,
`max_solves` and `tolerances`. Tolerance keys include their units:
`R_ohm_per_m`, `L_internal_h_per_m`, `L_external_h_per_m`, `C_f_per_m`,
`C0_f_per_m` and `G_s_per_m`. Select at least one; each value has explicit
`relative` and `absolute` numbers. The absolute number uses the parent key's
SI unit. Unknown units, fields, versions, duplicates and nonfinite values are
rejected. There is no automatic unit conversion or tolerance floor.

`request.analyze()` returns the same assessment as the direct API.
`execute_saved(request.dumps(), max_evaluations=3)` returns JSON-compatible
inputs, stages, all six physical matrix arrays, selected differences and
allowances. Its common budget and the saved `max_solves` both limit full
line evaluations (original + finer + outer inputs), before field work.

The result separates `completed` from `accepted`. Finished calculations with
unmet finite tolerances have execution `status='complete'` and
`result.accepted=false`. A field failure has `status='failed'`, retains all
completed evaluations and comparisons, and records the failed stage, exact
input, exception kind and message. Later solves do not run. Supplied input
documents are unchanged; user interrupts propagate.

Acceptance applies only to the selected quantities at the supplied frequencies.
It is not an absolute error estimate or evidence that resistance meets a
capacitance tolerance. The original numerical methods, unresolved refinement
failures, independent-reference requirements and other saved inputs are unchanged.

[한국어](../../locales/ko/pages/packages/sipi/line_resolution_document.md)
