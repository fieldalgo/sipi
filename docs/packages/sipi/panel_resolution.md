# Elementwise panel-line resolution checks

[Saved requests](panel_resolution_document.md) preserve the same separate-axis results through common execution.

`assess_panel_line_resolution` compares a panel line along three separate
axes: panel controls, dielectric volume mesh and finite outer domain. It
accepts either panel-line version, preserving the selected current method.
It never replaces a requested tolerance with a whole-matrix norm.

Supply all three finer panel controls and explicit larger-domain documents.
No panel control may decrease, and at least one must increase. The volume
factor reduces `edge_size`, `far_size` and `grade`. Outer documents use the
joint finer mesh, panel count and interpolation degree; their ground-mode
count can stay the same or increase. Physical interfaces, signal geometry,
metals, materials, frequencies and ports must remain unchanged. A physical
ground plane cannot move under the name of domain refinement.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_resolution import assess_panel_line_resolution
from sipi.line_resolution import ResolutionTolerance
from sipi.line_resolution_document import resolution_record

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
report = assess_panel_line_resolution(base, refined_panel_options=fine,
    outer_documents=[PanelTransmissionLineDocument.from_dict(raw)],
    tolerances={"C0": ResolutionTolerance(.005, 0.)}, max_solves=5)
saved_report = resolution_record(report)
assert report.completed
```

Each full line evaluation runs once: base, volume-only, panel-only, joint,
then each outer document. Volume and panel results compare separately with
base; joint compares with volume and with panel; outer results compare with
joint. `reference_index` and `evaluation_index` retain that distinction.
There must be at least one outer document. `max_solves` must accommodate
`4 + len(outer_documents)`, up to 16, before any field work begins.

Choose any nonempty subset of R, internal L, external L, C, G and C0 using
the [SI tolerance contract](line_resolution.md). Each frequency and entry
must satisfy `abs(b-a) <= absolute + relative*max(abs(a), abs(b))`.
Small mutual entries get no denominator floor. A failed comparison remains
in the report; other planned evaluations still run. A field failure stops
further evaluations and retains its exact input, stage and error. Interrupts
propagate. `completed` and `accepted` remain separate: even a fully evaluated
report can fail the requested agreement conditions.

The result is a `PanelResolutionAssessment` and works with
`resolution_record` for ordinary JSON-compatible result storage. To save an
executable request, use the linked `PanelResolutionDocument` wrapper. Input
snapshots include both panel settings and the nested line. Existing
line-resolution requests remain unchanged.

This reports finite differences, not an absolute field-error bound or an
infinite-domain limit. It does not infer tolerances, expand the physical
domain, fit materials or certify measured accuracy. The documented
[small mutual resistance observation](layered_panel_line.md) is why a
whole-matrix change alone is insufficient for every application.

[한국어](../../locales/ko/pages/packages/sipi/panel_resolution.md)
