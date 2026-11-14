# Explicit mesh and outer-domain assessment

[Saved requests](line_resolution_document.md) preserve SI tolerances and partial failures through common execution.

[Bounded automatic refinement](adaptive_line_resolution.md) requires two consecutive mesh comparisons before checking the explicit outer domains.

`assess_line_resolution` evaluates a saved line on its original mesh, a finer
mesh and explicitly expanded domains. It reports finite agreement for selected
quantities and tolerances. It does not certify absolute accuracy or change a
calculation to make a check pass.

```python
from sipi import stripline, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_resolution import assess_line_resolution, ResolutionTolerance

section = stripline(width=.5e-3, plane_spacing=1e-3, thickness=50e-6,
                    eps_r=4., box_width=.008)
base = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=5e-6, far_size=.2e-3, grade=.1)), [1e9],
    materials={}, conductor={'kind': 'perfect'}, length=.02)
larger = base.to_dict()
larger['cross_section']['box']['width'] = .016
for key in ('edge_size', 'far_size', 'grade'):
    larger['cross_section']['mesh'][key] *= .5
outer = TransmissionLineDocument.from_dict(larger)
report = assess_line_resolution(base, outer_documents=[outer], max_solves=3,
    tolerances={'C': ResolutionTolerance(relative=.005, absolute=0.)})
assert report.completed
accepted_for_capacitance = report.accepted
```

The line already stores resolved mesh defaults. Only `edge_size`, `far_size`
and `grade` are multiplied by `refinement_factor` (default 0.5). Each outer
input must use those same finer settings and preserve traces, internal
interfaces, materials, frequencies and ports. It must strictly enlarge an
open side's width or the last layer under an open top. Shrinking a domain or
moving a grounded wall/plane is rejected before solving.

Select a nonempty subset of `R` (ohm/m), `L_internal` and `L_external` (H/m),
`C` and `C0` (F/m), and `G` (S/m), each with an explicit `ResolutionTolerance`.
Every frequency and matrix entry must satisfy
`abs(b-a) <= absolute + relative*max(abs(a), abs(b))`.
Both tolerances may be zero for exact agreement. Small mutual entries are
checked individually, without an implicit denominator floor. Absolute
allowances use the selected quantity's SI unit. Unselected quantities are
not assessed: capacitance agreement says nothing about resistance agreement.

The first `comparisons` row compares the finer mesh with the original; later
rows compare each outer result with the finer result. Read-only `differences`
and `allowances` retain every matrix entry. `evaluations` retain each exact
input JSON, stage and ordinary line result. Input documents remain unchanged.

`completed` means all requested evaluations finished. `accepted` additionally
requires every requested comparison to pass. A completed assessment can remain
unaccepted. A solver failure stops subsequent evaluations, retaining completed
results and `failure.stage`, `input_json`, `kind` and `message`. `max_solves`
limits full line evaluations, including original and finer meshes, before
field work; it does not count internal linear solves separately. Interrupts
propagate.

Finite changes do not prove asymptotic convergence, remove remeshing noise,
validate unsampled frequencies or replace independent fields and measurements.
This Python API adds no saved request schema and changes no execution default.

[한국어](../../locales/ko/pages/packages/sipi/line_resolution.md)
