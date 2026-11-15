# Finite two-ground resolution assessment

[한국어](../../locales/ko/pages/packages/sipi/two_ground_resolution.md)

`assess_two_ground_line_resolution` compares explicit
[two-ground lines](two_ground_panel_line.md) along volume, current-panel and
outer-width axes. `TwoGroundResolutionDocument` stores the same request as
strict `sipi.two-ground-resolution/1` JSON. A completed assessment can be
unaccepted; finite agreement is not an absolute error or accuracy certificate.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_resolution import ResolutionTolerance
from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument
from sipi.two_ground_resolution_document import TwoGroundResolutionDocument
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
section = CrossSection([
    Layer('lower', .001, 3., tan_delta=.002),
    Layer('upper', .001, 5., tan_delta=.004)],
    [Trace('signal', 0., .0007, .0006, .00005)], .008, top='ground')
line = TwoGroundPanelTransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05)),
    [2e9, 5e9], materials={}, conductors=dict(signal=metal),
    reference=dict(kind='surfaces', bottom=metal, top=dict(metal, conductivity=21e6),
                   sides=None, conductors={}),
    ground_thickness=35e-6, length=.02, panels_per_edge=64, ground_modes=128,
    interpolation_degree=12)
finer = dict(panels_per_edge=128, ground_modes=256, interpolation_degree=12)
outer = []
for width, modes in ((.016, 512), (.032, 1024)):
    raw = line.to_dict()
    raw['cross_section']['box']['width'] = width
    for key in ('edge_size', 'far_size', 'grade'):
        raw['cross_section']['mesh'][key] *= .5
    raw['panel'] = dict(finer, ground_modes=modes)
    outer.append(TwoGroundPanelTransmissionLineDocument.from_dict(raw))
request = TwoGroundResolutionDocument(line, refined_panel_options=finer,
    outer_documents=outer, refinement_factor=.5, max_solves=6,
    tolerances={key: ResolutionTolerance(.01, 0.) for key in
                ('R', 'L_internal', 'L_external', 'C', 'G', 'C0')})
assert TwoGroundResolutionDocument.loads(request.dumps()).dumps() == request.dumps()
```

Preparation is field-free. `request.analyze(max_evaluations=6)` computes six
full line evaluations: base, volume-only, panel-only, joint and two explicit
outer inputs. The direct API takes the same keyword controls. `max_solves`
counts full line attempts, not the linear systems within each extraction.
The complete plan and host budget are admitted before any field work.

Volume refinement scales only edge_size, far_size and grade. All three refined
panel controls must be explicit; none can decrease and at least one increases.
Outer inputs preserve joint volume/panel settings, allowing ground_modes to
increase to resolve the larger width. They must expand the open side domain
without changing either physical ground plane, traces, interfaces, material
laws, frequency order, line length or network reference. Here open sides are
zero-normal-flux finite boundaries, not radiation boundaries. No automatic
outer domain, retry, clipping or alternate current method is selected.

For each selected R, internal/external L, C, G or C0 entry at every frequency,
the allowance is absolute + relative*max(abs(a),abs(b)), in SI units. There is
no small-entry floor. Compare volume and panel with base, joint separately with
each single axis, and every outer input with joint. The saved tolerance names
are R_ohm_per_m, L_internal_h_per_m, L_external_h_per_m, C_f_per_m, G_s_per_m
and C0_f_per_m; each stores relative and absolute explicitly. Unselected
quantities are not assessed. Each result retains differences and allowances,
exact input, current controls/evidence and actual dielectric mesh identity.

A field or comparison exception stops later evaluations, retaining completed
results and its stage/input. Typed current/mesh failures retain their original
cause details. Interrupts propagate. Common saved execution returns complete
with accepted=false for numerical disagreement, and failed with the partial
result for an exception. To save partial failures, explicitly select
`sipi.execution-record/2` in SavedExecutionRecord; version1 still rejects this
variant. Version2 checks the new source's exact planned prefix and typed failure
binding without solving. Record digests and structural validation do not prove
physical authenticity. Reopening a record or project does not calculate.

Validation retains synthetic independent entrywise comparisons, every failure
position, changed-physics/budget refusals, damaged records and prior resolution
regressions. The example is the registered finite-domain physical case: six
lines, two frequencies, all six matrix quantities, relative.01 and absolute0.
It is compared in source and exact installed wheels. This finite scalar case
does not establish convergence of every paired/manufacturing geometry,
asymptotic convergence, measured loss accuracy or new platform support.
