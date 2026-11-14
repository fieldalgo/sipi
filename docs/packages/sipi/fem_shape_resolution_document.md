# Saved finite FEM resolution requests

`FEMShapeResolutionDocument` uses `sipi.fem-shape-resolution/1`. Its six keys are
schema, line, outer_lines, refinement_factor, max_solves and tolerances. Nested
lines explicitly use the checked FEM line schema; the existing saved resolution
schemas and defaults are unchanged. Parsing is field-free and retains all
physical admission and open-domain restrictions of the direct API.

```python
from sipi import CrossSectionDocument, FEMShapeTransmissionLineDocument
from sipi import assess_fem_shape_line_resolution
from sipi.line_resolution import ResolutionTolerance
from sipi.templates import coupled_stripline

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness={'kind': 'smooth'})

line = FEMShapeTransmissionLineDocument(
    CrossSectionDocument(coupled_stripline(width=.0004, gap=.0003,
        plane_spacing=.002, thickness=.00005, eps_r=4., box_width=.008),
        mesh=dict(edge_size=5e-6, far_size=.0002, grade=.1)),
    [2e9, 3e9], materials={},
    conductors={'positive': metal(58e6), 'negative': metal(35e6)},
    reference=metal(58e6), ground_thickness=35e-6, length=.02)
outer = []
for width in (.016, .032):
    raw = line.to_dict()
    raw['cross_section']['box']['width'] = width
    for key in ('edge_size', 'far_size', 'grade'):
        raw['cross_section']['mesh'][key] *= .5
    outer.append(FEMShapeTransmissionLineDocument.from_dict(raw))
tolerances = {key: ResolutionTolerance(relative=.01, absolute=0.)
              for key in ('R', 'L_internal', 'L_external', 'C', 'G', 'C0')}
# Explicit execution (not performed by this field-free example):
# report = assess_fem_shape_line_resolution(line, outer_documents=outer,
#     tolerances=tolerances, refinement_factor=.5, max_solves=4)
# saved_observations = report.to_dict()
from sipi import FEMShapeResolutionDocument
from sipi.execution import normalize_saved
request = FEMShapeResolutionDocument(line, outer_documents=outer,
    tolerances=tolerances, refinement_factor=.5, max_solves=4)
assert FEMShapeResolutionDocument.loads(request.dumps()).dumps() == request.dumps()
assert normalize_saved(request.dumps()) == request.dumps()
```
Tolerances use explicit SI keys: R_ohm_per_m, L_internal_h_per_m,
L_external_h_per_m, C_f_per_m, G_s_per_m and C0_f_per_m. Each selected key requires
relative and absolute numbers. They retain the direct API's per-entry rule, with
no diagonal floor. Unknown/missing keys, duplicate/nonfinite JSON, physical
changes disguised as padding, and insufficient complete-line budgets are rejected.
`analyze(max_evaluations=...)` also checks the host budget before fields.

Common normalization, execution requests, records, projects and CLI accept the
schema. A completed numerical disagreement has execution status `complete` and
result `accepted=False`: completion is not acceptance. A solver failure has
status `failed`, keeps the partial result and repeats its failure in `error`.
Typed failures preserve exact input, original/partial current evidence and mesh
identity. User interruption propagates. Line characteristic/mode diagnostics
cannot be requested for a resolution result.

Validation runs the same registered four physical line inputs as the direct API.
The full six-quantity assessment remains **unaccepted** because mutual R/internal-L
mesh changes exceed the unchanged 1% criterion; outer observations pass. Stored
transport replays these observed fields explicitly and tests both retained failure
and completed nonacceptance. Selecting only C/G demonstrates acceptance of those
quantities alone, never of omitted R/L. Both record versions retain completed observations. Partial failures require
explicit execution-record/2 and survive attached-project round-trips; default
version 1 continues to reject them. Version 2 binds typed cause details to the
original failed input, kind and message, without certifying numerical validity. No additional field work is attributed to
transport replay. See [finite resolution](fem_shape_resolution.md) for scope and
limits; saved records are not accuracy certificates or platform validation.
