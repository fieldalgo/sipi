# Saved finite resolution of face-metal lines

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_resolution_document.md)

`TwoGroundFaceResolutionDocument` stores strict
`sipi.two-ground-face-resolution/1` input for the
[direct finite assessment](two_ground_face_resolution.md). It connects the
same explicit plan to shared execution, requests, result records, projects
and CLI files. Existing whole-boundary schemas and numerical limits remain unchanged.

This example prepares and normalizes the plan without fields:

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_resolution import ResolutionTolerance
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument
from sipi.two_ground_face_resolution_document import TwoGroundFaceResolutionDocument
from sipi.execution import normalize_saved
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
finer = dict(panels_per_edge=128, ground_modes=256, interpolation_degree=16)
outer = []
for width, modes in ((.016, 512), (.032, 1024)):
    raw = line.to_dict()
    raw['cross_section']['box']['width'] = width
    for key in ('edge_size', 'far_size', 'grade'):
        raw['cross_section']['mesh'][key] *= .5
    raw['panel'] = dict(finer, ground_modes=modes)
    outer.append(TwoGroundFacePanelTransmissionLineDocument.from_dict(raw))
controls = dict(refined_panel_options=finer, outer_documents=outer,
    refinement_factor=.5, max_solves=6,
    tolerances={key: ResolutionTolerance(.01, 0.) for key in
                ('R', 'L_internal', 'L_external', 'C', 'G', 'C0')})
request = TwoGroundFaceResolutionDocument(line, **controls)
text = request.dumps()
assert normalize_saved(text) == text
# Run the admitted plan explicitly when ready:
# assessment = request.analyze(max_evaluations=6)
```

The seven root keys are schema, line, refined_panel, outer_lines,
refinement_factor, max_solves and tolerances. The base and all outer lines must
use the face-line schema. Nested tolerances use explicit SI names:
R_ohm_per_m, L_internal_h_per_m, L_external_h_per_m, C_f_per_m, G_s_per_m and
C0_f_per_m; select a nonempty subset and supply both relative and absolute.
No floor, inferred allowance or automatic domain is introduced.

Parsing rejects duplicate, missing, extra, nonfinite and malformed fields.
The entire volume/panel/joint/outer plan is checked before field work, including
fixed geometry, physical ground planes, metals, coatings, roughness, materials
and ports. Inputs are detached snapshots. The direct 5..16 full-line attempt
limit remains; the caller budget must also cover every planned evaluation.
Unsupported diagnostics and input-byte limits are rejected before fields.

`request.analyze(max_evaluations=6)` or
`execute_saved(text, max_evaluations=6)` executes the same direct assessment.
Completed numerical disagreement retains `completed=true`, `accepted=false`
and a complete execution status. A field/comparison exception stops the plan,
retaining the failed stage, exact input, completed prefix and available typed
current/mesh cause details. Interrupts propagate. The CLI preserves its source
file and writes the execution receipt, including partial failures.

To store a partial failed assessment, explicitly select
`sipi.execution-record/2` in `SavedExecutionRecord`; version1 continues to reject
that variant. Version2 checks the exact planned prefix, stage, count, input,
current/mesh evidence and typed failure binding without solving. Changed face
inputs or failure details cannot silently become another plan. Structural checks
and declared artifact hashes do not prove physical authenticity. Restoring a
request, record or selected project result does not execute fields.

The physical saved check repeats the direct API's registered layered scalar
case: 2/5 GHz, six line evaluations, six selected matrix quantities and
relative0.01/absolute0. Its full assessment is compared exactly with the earlier
direct observation and the installed result. The direct study's independent
characteristic, entrywise and paired checks remain separate evidence. Synthetic
checks cover all six failure positions, complete disagreement, malformed or
changed records, interruption, CLI refusals and project restoration.
No continuous-band, measured-accuracy, arbitrary-domain or new-platform
qualification follows from these transport checks.
