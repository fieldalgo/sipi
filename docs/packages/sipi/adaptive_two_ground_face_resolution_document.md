# Saved bounded two-ground face refinement

[한국어](../../locales/ko/pages/packages/sipi/adaptive_two_ground_face_resolution_document.md)

`AdaptiveTwoGroundFaceResolutionDocument` stores
`sipi.adaptive-two-ground-face-resolution/1`. Its six root keys are `schema`,
`line`, `refinements`, `tolerances`, `refinement_factor` and `max_solves`.
It preserves the [direct bounded plan](adaptive_two_ground_face_resolution.md):
two through four explicit levels, two consecutive four-way passes before outer
checks, complete next-level/outer budget reservation and original typed failures.
Every refinement stores `refined_panel` and its ordered `outer_lines`.
Tolerance quantities have explicit SI names and require both relative and absolute
values. Nested line versions and all physical face/ground laws stay explicit.

This prepares and validates input without solving fields:

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_resolution import ResolutionTolerance
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
section = CrossSection([
    Layer('lower', .001, 3., tan_delta=.002),
    Layer('upper', .001, 5., tan_delta=.004)],
    [Trace('signal', 0., .0007, .0006, .00005)], .008, top='ground')
line = TwoGroundFacePanelTransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05)),
    [2e9, 5e9], materials={}, conductors=dict(signal=dict(zip(('bottom','top','left','right'),
        [dict(metal,conductivity=s) for s in (58e6,35e6,21e6,45e6)]))),
    reference=dict(kind='surfaces', bottom=metal, top=dict(metal, conductivity=21e6),
                   sides=None, conductors={}),
    ground_thickness=35e-6, length=.02, panels_per_edge=64, ground_modes=128,
    interpolation_degree=16)
from sipi.adaptive_two_ground_face_resolution import (
    TwoGroundFaceResolutionRefinement, refine_two_ground_face_line_resolution)
steps = []
mesh = line.to_dict()['cross_section']['mesh']
for level in (1, 2):
    for key in ('edge_size', 'far_size', 'grade'):
        mesh[key] *= .75
    panel = dict(panels_per_edge=64*2**level, ground_modes=128*2**level,
                 interpolation_degree=16)
    outer = []
    for width, modes in ((.016, 256*2**level), (.032, 512*2**level)):
        raw = line.to_dict()
        raw['cross_section']['box']['width'] = width
        raw['cross_section']['mesh'] = dict(mesh)
        raw['panel'] = dict(panel, ground_modes=modes)
        outer.append(TwoGroundFacePanelTransmissionLineDocument.from_dict(raw))
    steps.append(TwoGroundFaceResolutionRefinement(panel, outer))
controls = dict(refinements=steps, refinement_factor=.75, max_solves=9,
    tolerances={key: ResolutionTolerance(.01, 0.) for key in
                ('R', 'L_internal', 'L_external', 'C', 'G', 'C0')})
assert len(steps) == 2

from sipi.adaptive_two_ground_face_resolution_document import AdaptiveTwoGroundFaceResolutionDocument
from sipi.execution_request import SavedExecutionRequest
saved = AdaptiveTwoGroundFaceResolutionDocument(line, **controls)
request = SavedExecutionRequest(saved.dumps(), max_evaluations=9)
assert AdaptiveTwoGroundFaceResolutionDocument.loads(saved.dumps()).dumps() == saved.dumps()
assert request.to_dict()['input'] == saved.to_dict()
# receipt = request.run()
```

The effective whole-line budget is the smaller of the saved `max_solves` and
caller `max_evaluations`. A caller budget that cannot reserve two levels and all
outer checks is refused before fields. Input-byte and diagnostic controls also
precede calculation. Complete disagreement remains complete but unaccepted;
field failure or budget exhaustion retains a non-null partial result and failed
execution status. A qualified selected result never appears in a failed plan.

Use explicit `sipi.execution-record/2` to save partial failures. Version1 keeps
its earlier refusal. Reopening version2 reconstructs the field-free plan from
the original source and caller budget. It checks level and outer counts, exact
attempted input and evaluated prefix, comparison order/references, two-consecutive
control flow, current/mesh evidence and typed-cause binding. A later failed step
must have had room for all three batches and outer checks when it began; fitting
the one recorded failed attempt is insufficient. A budget stop must actually lack
that reservation. Comparison failure may retain its completed line calculation
without inventing a successful comparison. Project/CLI reopening does not solve.

The physical saved scalar case repeats the direct plan's nine line batches and
ten comparisons. Its full inputs, observations, differences, allowances and
selected evaluation are compared exactly with the preceding direct evidence.
Independent scalar square-root and matrix-square-root results are checked.
Synthetic cases cover every failed operation, later-level admission, caller budget
exhaustion, incomplete comparison, completed disagreement, tampered prefixes and
CLI/project restoration. A separate regression refuses a later failure relabelled
with a caller budget that could not have reserved that level.

Record validation checks structural consistency and control flow; it is not a
signature, artifact authentication or certification of recorded numerical values.
Finite agreement does not bound discretization error, establish measured accuracy,
continuous-band acceptance or platform support. Existing methods and numerical
criteria remain unchanged.
