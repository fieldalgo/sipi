# Bounded mesh refinement

`refine_line_resolution` applies the existing line calculation on successively
finer meshes. It requires two consecutive elementwise comparisons to meet
explicit tolerances before checking the supplied larger domains. It retains
failed comparisons and never changes a tolerance to obtain acceptance.

```python
from sipi import stripline, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.adaptive_line_resolution import refine_line_resolution

section = stripline(width=.5e-3, plane_spacing=1e-3, thickness=50e-6,
                    eps_r=4., box_width=.008)
line = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=5e-6, far_size=.2e-3, grade=.1)), [1e9],
    materials={}, conductor={'kind': 'perfect'}, length=.02)
larger = line.to_dict()
larger['cross_section']['box']['width'] = .016
for key in ('edge_size', 'far_size', 'grade'):
    larger['cross_section']['mesh'][key] *= .5
report = refine_line_resolution(line,
    outer_documents=[TransmissionLineDocument.from_dict(larger)],
    tolerances={'C': ResolutionTolerance(.005, 0.)}, max_levels=3, max_solves=6)
accepted_input = report.selected_evaluation
```

Outer templates use the first finer mesh settings, following the ordinary
[resolution assessment](line_resolution.md) admission rules. After two adjacent
mesh comparisons pass, the engine replaces only those templates' mesh settings
with the selected level's settings. It compares each outer result with the
selected finer result on the original domain. An unmet outer criterion stops
the process with `outer-unaccepted`; it does not move a physical boundary or
continue reducing the mesh to mask a domain discrepancy.

`max_levels` is 2 through 8 and `max_solves` is 4 through 16. Full line
evaluations count once, and existing results are reused. Before another finer
solve, its cost plus all required outer checks must fit the remaining budget.
The underlying mesh resource limits remain active. A solver/setup failure
retains its exact attempted input and stage. User interrupts propagate.

Read `stop_reason`: `accepted`, `mesh-unaccepted`, `outer-unaccepted`,
`budget-exhausted` or `field-failed`. `completed` is false for the last two;
a completed assessment can be unaccepted. `outer_completed` separately tells
whether all outer comparisons ran. `evaluations` and `comparisons` retain
every completed result and elementwise difference/allowance. `mesh_levels`
counts attempted finer levels, including a failed attempt. On acceptance,
`selected_evaluation` identifies the finer result on the original domain;
otherwise it is `None`, while the full history remains available.

Acceptance concerns only selected quantities and supplied frequencies.
Two finite comparisons do not certify absolute error, asymptotic convergence,
small unselected mutual entries or measured accuracy. The original extraction
methods, physical inputs, saved request schemas and numerical test gates remain
unchanged. This is a separate Python API with explicit budgets.

[한국어](../../locales/ko/pages/packages/sipi/adaptive_line_resolution.md)
