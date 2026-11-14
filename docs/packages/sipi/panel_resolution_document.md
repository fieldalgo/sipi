# Saved panel resolution requests

`PanelResolutionDocument` stores the existing
[elementwise panel assessment](panel_resolution.md) as strict
`sipi.panel-resolution/1`. Its keys are `schema`, `line`, `outer_lines`,
`refined_panel`, `refinement_factor`, `max_solves` and `tolerances`.
The nested lines are panel-line version 1 or 2; all must retain the same
selected method and physical problem. Normalization performs no field work.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_resolution_document import PanelResolutionDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.execution import execute_saved

section = CrossSection([Layer("uniform", .002, 4.)],
    [Trace("signal", 0., .0005, .0002, thickness=35e-6)], .004)
line = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1)), [1e9],
    materials={}, conductor={"kind": "perfect"}, length=.02)
base = PanelTransmissionLineDocument(line, panels_per_edge=16)
fine = dict(panels_per_edge=32, ground_modes=1024, interpolation_degree=12)
raw = base.to_dict()
raw["panel"] = dict(fine, ground_modes=2048)
cross = raw["line"]["cross_section"]
cross["box"]["width"] *= 2
cross["layers"][-1]["thickness"] *= 2
for key in ("edge_size", "far_size", "grade"):
    cross["mesh"][key] *= .5
request = PanelResolutionDocument(base, refined_panel_options=fine,
    outer_documents=[PanelTransmissionLineDocument.from_dict(raw)],
    tolerances={"C0": ResolutionTolerance(.005, 0.)}, max_solves=5)
text = request.dumps()
assert PanelResolutionDocument.loads(text).dumps() == text
response = execute_saved(text, max_evaluations=5)
assert response["status"] == "complete"
assert response["result"]["expected_evaluations"] == 5
```

Tolerance keys name SI quantities explicitly: `R_ohm_per_m`,
`L_internal_h_per_m`, `L_external_h_per_m`, `C_f_per_m`, `G_s_per_m`
and `C0_f_per_m`. Each selected key requires `relative` and `absolute`.
There is no unit inference, whole-matrix normalization or small-entry floor.
Unknown, missing, duplicate and nonfinite inputs are rejected.

`max_solves` is 5 through 16 and must cover four separate-axis evaluations
plus every outer input. Common `max_evaluations` imposes an additional
whole-line evaluation budget. Both are checked before field work.
The finer panel controls and physical outer-domain admission rules are
exactly those of the direct API; no geometry, material or control is repaired.

Results preserve each exact panel-line input, frequency, ordered signals,
all six physical quantities, comparison indices, differences and allowances.
A completed request can have `accepted=false`; this is `status=complete`
with no execution error. A field exception instead produces `status=failed`,
retains the partial result and copies its exact input/stage/error to `error`.
Interrupts propagate. Consumers must inspect both completion and acceptance.

The base, volume-only, panel-only, joint and outer evaluations remain distinct.
Joint results compare separately with each singly refined input; outer results
compare with joint. These finite per-entry differences do not certify absolute
error, an infinite outer domain or hardware accuracy. The existing panel
geometry, metal and quasi-TEM limits still apply.

[한국어](../../locales/ko/pages/packages/sipi/panel_resolution_document.md)
