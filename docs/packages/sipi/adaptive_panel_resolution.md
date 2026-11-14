# Bounded panel and volume refinement

`refine_panel_line_resolution` executes two to four explicit refinement steps.
Each step supplies `PanelResolutionRefinement(panel_options, outer_documents)`.
All inputs are checked before field work. Panel controls cannot decrease and at
least one must increase; volume `edge_size`, `far_size` and `grade` decrease by
the same `refinement_factor`. Outer documents must use that step's finer mesh
and panel settings (ground modes may increase). Their physical domain sizes
and order remain fixed across steps. Material, conductor, port and frequency
inputs stay unchanged. Both panel line schema versions are supported.

Each step evaluates volume-only, panel-only and joint settings, reusing the
previous joint result as its base. Four separate comparisons must pass:
volume/base, panel/base, joint/volume and joint/panel. Two consecutive accepted
steps are required before the selected step's outer documents are evaluated.
An intervening failure resets the count. Outer disagreement stops the process.

Use `ResolutionTolerance(relative, absolute)` in each selected quantity's SI
units. Every matrix entry at every supplied frequency must meet
`abs(a-b) <= absolute + relative * max(abs(a), abs(b))`. There is no denominator
floor for a small mutual entry. Quantities omitted from the tolerance mapping
are not assessed. Finite agreement, even twice, is not an absolute error bound,
asymptotic convergence proof, continuous-band guarantee or measured accuracy.

`max_solves` (integer 8–32) counts complete line evaluations, not their internal
linear solves. The next three evaluations and every required outer check must
fit before a step starts. The returned immutable history keeps each exact input,
result and comparison. `accepted` selects a joint result on the original domain.
`resolution-unaccepted` and `outer-unaccepted` are completed but unaccepted;
`budget-exhausted` and `field-failed` are incomplete. Every unaccepted result has
`selected_evaluation is None`. A field failure retains its attempted input and
previous results. User interrupts propagate. No physical input or tolerance is
silently adjusted. Unused explicit future steps are validated but not solved.

This example deliberately checks only C0 with a loose 10% observation allowance
to demonstrate control flow. It does not qualify resistance or small mutual
terms. Choose physical acceptance criteria separately and retain unaccepted
results.

```python
from sipi import CrossSection, Layer, Trace, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.adaptive_panel_resolution import (
    PanelResolutionRefinement, refine_panel_line_resolution,
)

section = CrossSection([Layer('uniform', .002, 4.2)],
    [Trace('left', -.0003, .0005, .0002, thickness=35e-6),
     Trace('right', .0003, .0005, .0002, thickness=35e-6)], .004)
line = TransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1)),
    [1e9, 2e9], materials={}, conductor={'kind': 'perfect'}, length=0.)
base = PanelTransmissionLineDocument(line, panels_per_edge=8)
steps = []
for level in (1, 2):
    raw = base.to_dict()
    options = dict(base.panel_options, panels_per_edge=8 * 2**level)
    raw['panel'] = dict(options, ground_modes=1024)
    cross = raw['line']['cross_section']
    cross['box']['width'] *= 2
    cross['layers'][-1]['thickness'] *= 2
    for key in ('edge_size', 'far_size', 'grade'):
        cross['mesh'][key] *= .5**level
    steps.append(PanelResolutionRefinement(
        options, [PanelTransmissionLineDocument.from_dict(raw)]))
result = refine_panel_line_resolution(base, refinements=steps,
    tolerances={'C0': ResolutionTolerance(.1, 0.)}, max_solves=8)
assert result.completed and result.accepted and result.outer_completed
assert result.selected_evaluation is result.evaluations[6]
assert len(result.evaluations) == 8
```

Validation covers legacy and fixed-coating inputs, uniform dielectric identities,
independent coating transfer and network equations, actual unaccepted resistance
comparisons, two consecutive four-way passes, reset, exact budgets, failures and
interrupts. This API adds no extraction method, changes no existing numerical
gate, and does not resolve earlier surface-current accuracy failures.
