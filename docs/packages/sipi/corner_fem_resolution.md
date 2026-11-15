# Finite FEM resolution with explicit corner control

`assess_corner_fem_shape_line_resolution` compares a corner FEM line, its finer
input and explicit larger open domains. The saved `CornerFEMShapeResolutionDocument`
uses `sipi.corner-fem-shape-resolution/1` with exactly `schema`, `line`,
`outer_lines`, `refinement_factor`, `max_solves` and `tolerances`. Every nested
line is an explicit corner FEM line. Normalization performs no field solves.

```python
from sipi import CrossSectionDocument, FEMShapeTransmissionLineDocument
from sipi import (assess_corner_fem_shape_line_resolution,
                  CornerFEMShapeTransmissionLineDocument)
from sipi.line_resolution import ResolutionTolerance
from sipi.templates import coupled_stripline

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness={'kind': 'smooth'})

line = FEMShapeTransmissionLineDocument(
    CrossSectionDocument(coupled_stripline(width=.0004, gap=.0003,
        plane_spacing=.002, thickness=.00005, eps_r=4., box_width=.008),
        mesh=dict(edge_size=5e-6, far_size=.0002, grade=.1)),
    [2e9, 5e9], materials={},
    conductors={'positive': metal(58e6), 'negative': metal(35e6)},
    reference=metal(58e6), ground_thickness=35e-6, length=.02)
line = CornerFEMShapeTransmissionLineDocument(line, corner_size=2.5e-6)
outer = []
for width in (.016, .032):
    raw = line.to_dict()
    raw['line']['cross_section']['box']['width'] = width
    for key in ('edge_size', 'far_size', 'grade'):
        raw['line']['cross_section']['mesh'][key] *= .5
    raw["corner_size"] *= .5
    outer.append(CornerFEMShapeTransmissionLineDocument.from_dict(raw))
tolerances = {key: ResolutionTolerance(relative=.01, absolute=0.)
              for key in ('R', 'L_internal', 'L_external', 'C', 'G', 'C0')}
# Explicit execution (not performed by this field-free example):
# report = assess_corner_fem_shape_line_resolution(line, outer_documents=outer,
#     tolerances=tolerances, refinement_factor=.5, max_solves=4)
# saved_observations = report.to_dict()
from sipi import CornerFEMShapeResolutionDocument
from sipi.execution import normalize_saved
request = CornerFEMShapeResolutionDocument(line, outer_documents=outer,
    tolerances=tolerances, refinement_factor=.5, max_solves=4)
assert CornerFEMShapeResolutionDocument.loads(request.dumps()).dumps() == request.dumps()
assert normalize_saved(request.dumps()) == request.dumps()
```

The original FEM preflight rules apply to the inner lines. Edge, far and grade
must be explicit, the refinement factor lies strictly between zero and one,
and at least one outer line is required. Corner size scales by the same factor.
All outer inputs must retain that exact refined corner value and refined mesh
controls. They may expand an open side or topmost layer below an open top;
physical interfaces, traces, materials, metals, frequencies and ports are fixed.
Moving a grounded plane is a physical change and is rejected.

Each selected SI quantity uses `absolute + relative * max(abs(base), abs(actual))`
at every entry and frequency. No diagonal floor is added to small mutual terms.
The mesh comparison uses the base; every outer comparison uses the finer input.
The host and document budgets count complete line attempts, each containing
multiple field solves, and are checked before any field work.

Completed disagreement is retained as `completed=True, accepted=False`.
Field failures retain their exact full corner input, stage, mesh identity and
complete or partial current evidence, then stop. Interruptions propagate.
Requests, records and projects preserve these observations without recomputing
on reopen. Partial failed results require explicit execution-record/2; version 1
keeps its original rejection. Diagnostic requests on assessments are rejected.

Validation compares default-corner results with the original four-input FEM
assessment, including its **unaccepted** mutual R/internal-L mesh comparison.
A separate smaller-corner four-input observation also remains unaccepted. Its
largest entrywise R changes are 21.865% for mesh and 8.662%/8.121% for the two
outer comparisons, above the unchanged 1% allowance; internal-L changes also
fail. Independent network identities still pass. Finer corner controls alone
do not establish loss convergence. These finite comparisons do not
prove absolute accuracy, asymptotic convergence, all-geometry acceptance or
new-platform support. Selecting only some quantities never certifies the others.

[한국어](../../locales/ko/pages/packages/sipi/corner_fem_resolution.md)
