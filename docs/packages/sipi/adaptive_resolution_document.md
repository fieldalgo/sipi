# Saved bounded refinement

Explicit `sipi.line-resolution/2` stores the existing
[bounded refinement](adaptive_line_resolution.md) request. It has the version-1
keys plus required `max_levels`. Version 1 keeps its original fixed comparison
sequence and canonical inputs. Construction and normalization perform no field
work; nested line versions 1–7, SI tolerances and unchanged-physics outer
admission rules are the same as for the direct API.

```python
from sipi import stripline, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.line_resolution_document import LineResolutionDocument
from sipi.execution import execute_saved

section = stripline(width=.5e-3, plane_spacing=1e-3, thickness=50e-6,
                    eps_r=4., box_width=.008)
line = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=5e-6, far_size=.2e-3, grade=.1)), [1e9],
    materials={}, conductor={"kind": "perfect"}, length=.02)
raw = line.to_dict()
raw["cross_section"]["box"]["width"] = .016
for key in ("edge_size", "far_size", "grade"):
    raw["cross_section"]["mesh"][key] *= .5
request = LineResolutionDocument(line,
    outer_documents=[TransmissionLineDocument.from_dict(raw)],
    tolerances={"C": ResolutionTolerance(.005, 0.)},
    schema="sipi.line-resolution/2", max_levels=3, max_solves=5)
text = request.dumps()
assert LineResolutionDocument.loads(text).dumps() == text
output = execute_saved(text, max_evaluations=5)
assert output["status"] == "complete"
```

`max_levels` is an integer from 2 through 8; `max_solves` is 4 through 16.
Both the stored solve budget and the common execution `max_evaluations`
limit count full line evaluations. At least `3 + len(outer_lines)` must fit
before any field work. Before another mesh solve, the engine reserves all
required outer evaluations. Existing results are reused; it does not spend
that reserved budget and then silently omit outer checks.

The result retains exact inputs, completed field arrays, differences,
allowances and failures. Additional fields are `stop_reason`, `mesh_levels`,
`expected_outer_evaluations`, `outer_completed` and
`selected_evaluation_index`. On acceptance the selected index identifies
the finer result on the original domain; otherwise it is `null`.

| Stop reason | Common status | Completed | Accepted |
|---|---|---|---|
| `accepted` | `complete` | true | true |
| `mesh-unaccepted` | `complete` | true | false |
| `outer-unaccepted` | `complete` | true | false |
| `budget-exhausted` | `failed` | false | false |
| `field-failed` | `failed` | false | false |

Budget exhaustion keeps the partial result and emits a
`ResolutionBudgetExceeded` error at stage `budget`. The result's field
`failure` remains `null` because no field exception caused that stop.
A field failure instead preserves the original exception and exact attempted
input/stage. User interrupts propagate. A completed but unaccepted request
has no execution error; clients must inspect `accepted` as well as status.

Two consecutive finite mesh comparisons and the explicit outer checks do not
prove absolute error or measured accuracy. No tolerance, geometry, material
or extraction method is changed to obtain acceptance. Panel-line assessment
remains a [separate explicit API](panel_resolution.md).

[한국어](../../locales/ko/pages/packages/sipi/adaptive_resolution_document.md)
