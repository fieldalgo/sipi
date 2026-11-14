# Separate resolution checks for shape-current lines

`assess_shape_panel_line_resolution` evaluates an explicit saved shape-current
line along separate panel, volume and outer-domain axes. The original document
is followed by volume-only, panel-only and joint refinements, then the supplied
outer documents. Volume/base, panel/base, joint/volume and joint/panel are four
separate comparisons; each outer result compares with joint.

Use `ResolutionTolerance(relative, absolute)` for selected `R`, `L_internal`,
`L_external`, `C`, `G` or `C0` matrices, with absolute values in their SI units.
Every entry at every supplied frequency must satisfy
`abs(a-b) <= absolute + relative * max(abs(a), abs(b))`. Small mutual entries
have no denominator floor. Unselected quantities are not assessed. Completed
agreement remains a finite observation, not an absolute accuracy certificate.

All planned inputs are validated before fields. Refined panel controls are
explicit, cannot decrease, and at least one must increase. Only volume
`edge_size`, `far_size` and `grade` scale by `refinement_factor`. Outer documents
preserve the joint mesh, panel resolution and all physical/material/port inputs;
ground Fourier modes may increase. Their open side/top padding expands without
moving physical interfaces or traces. The shape `step_fraction` remains fixed
throughout, and every line still performs its own two-step derivative check.

`max_solves` (integer 5–16) counts **complete line evaluations**, including all
requested outer cases. It is distinct from the frequency-count admission of a
top-level saved line and from the multiple shared panel solves inside each line.
An insufficient budget is rejected before any field work. Each stage executes
once. No tolerance, physical geometry or solver control is silently adjusted.

The returned assessment separates `completed` from `accepted`. A completed but
unaccepted result retains every comparison. A field failure stops subsequent
stages and retains preceding evaluations, its exact input and stage. A saved
shape-line failure also retains its complete/partial current history in
`failure.details`; reading that property makes an independent copy. Interrupts
propagate. Use the assessment's `to_dict()` for method-specific current samples
and failure details; the generic matrix-only resolution serializer is unchanged.

This control-flow example deliberately selects only C0 with a loose 10%
allowance. It does not qualify resistance, mutual entries or physical accuracy.

```python
from sipi import CrossSection, Layer, Trace, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.shape_panel_resolution import assess_shape_panel_line_resolution
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
result = assess_shape_panel_line_resolution(base, refined_panel_options=fine,
    outer_documents=[outer], tolerances={'C0': ResolutionTolerance(.1, 0.)},
    max_solves=5)
assert result.completed and result.accepted
assert len(result.evaluations) == len(result.comparisons) == 5
assert len(result.to_dict()['evaluations'][0]['current_solver']['samples']) == 13
```

Validation retains actual legacy/coated five-stage results, independent uniform
dielectric and metal/network identities, unaccepted small-mutual and exact-zero
allowances, four-way truth tables, last-frequency checks and every failure stage.
Existing extraction defaults, saved schemas and numerical acceptance criteria
are unchanged. This direct API does not add an inverse search or yield study.

[한국어](../../locales/ko/pages/packages/sipi/shape_panel_resolution.md)
