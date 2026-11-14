# Saved lines with capacitance-shape currents

`ShapePanelTransmissionLineDocument` stores the explicit shape-current method
as `sipi.shape-panel-transmission-line/1`. Its three keys are `schema`, `line`
and `step_fraction`. The nested `line` is a `panel-transmission-line/1` or `/2`
document, preserving its panel controls and nested legacy or fixed-coating
transmission-line contract. Existing constructors and schema defaults remain
unchanged; an ordinary panel line does not select shape currents.

Normalization validates the complete nested inputs and offset polygons without
field solves. The step-fraction bounds, convex finite-thickness geometry,
bottom-ground/open-wall restrictions and surface-metal admission are those of
[shape currents](panel_shape_conductor.md). Shared quadrature and domain
admission are checked when the actual solver runs, without fallback.

Analysis uses those vacuum current factors and the saved volume mesh for
matched dielectric C/G. Its external inductance uses the same vacuum C0;
per-boundary metal laws supply R and internal L. Perfect conductors have zero
R/internal L. The full frequency-dependent network uses the saved length and
port references. Fixed coatings retain their original material contract.

```python
from sipi import CrossSection, Layer, Trace, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.execution import execute_saved, normalize_saved

section = CrossSection([Layer('uniform', .002, 4.2, tan_delta=.02)],
    [Trace('signal', 0., .0005, .0002, thickness=35e-6)], .004)
metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness={'kind': 'smooth'})
line = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1)), [1e9, 2e9],
    materials={}, conductor=dict(kind='surface-boundaries',
        conductors={'signal': metal}, reference=metal, ground_thickness=35e-6),
    length=.02, schema='sipi.transmission-line/3')
source = ShapePanelTransmissionLineDocument(PanelTransmissionLineDocument(
    line, panels_per_edge=16, ground_modes=512, interpolation_degree=16))
assert normalize_saved(source.dumps()) == source.dumps()
output = execute_saved(source.dumps(), max_evaluations=2)
assert output['status'] == 'complete'
current = output['result']['current_solver']
assert current['kind'] == 'grounded-rectangle-capacitance-shape'
assert len(current['samples']) == 9
```

Common execution and `SavedExecutionRequest` support the existing
`characteristic` and `modes` diagnostics. As for an ordinary panel line,
`max_evaluations` admits the **frequency count before any field solve**; it does
not count internal panel solves or bound memory/time. One shape-current
calculation uses `1+4*(number_of_traces+1)` shared solves. Hosts own cancellation
and resource limits.

The current-solver output keeps controls, C0, ordered boundary factors and
currents, diagnostics, both step matrices before/after reference grouping, and
every exact solver request/capacitance sample. A `ShapePanelLineError` identifies
material admission, conductor admission, current extraction, mesh, dielectric
or network stage. Completed current work is retained when a later stage fails;
a failed current solve keeps its partial samples and failed request. Common
execution returns `status='failed'`, null result and this typed error record.
User interrupts propagate. `SavedExecutionRecord` can preserve a successful or
failed receipt without rerunning fields; artifact declarations remain
host-declared, not verified by storing a record.

Validation checks actual legacy/coated fields, direct/common/receipt equality,
uniform dielectric identities, independent coating transfer and full network
matrices, strict nested input rejection, all failure stages and interrupts.
Panel and finite outer-domain observations are retained separately. A successful
saved execution or difference-step check does not establish requested physical
accuracy. This unit adds no automatic resolution acceptance, inverse search,
yield study, browser qualification or deployment.

[한국어](../../locales/ko/pages/packages/sipi/shape_panel_line.md)
