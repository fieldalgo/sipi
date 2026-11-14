# Saved bounded FEM refinement

`FEMShapeAdaptiveResolutionDocument` uses `sipi.fem-shape-adaptive-resolution/1`.
The seven keys are schema, line, outer_lines, tolerances, refinement_factor,
max_levels and max_solves. Nested lines and explicit SI tolerances retain the
[direct bounded API](fem_shape_adaptive_resolution.md) contract. Parsing is
field-free; existing fixed-resolution schemas/defaults remain unchanged.

```python
from sipi import CrossSectionDocument, FEMShapeTransmissionLineDocument
from sipi import refine_fem_shape_line_resolution
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
# report = refine_fem_shape_line_resolution(line, outer_documents=outer,
#     tolerances=tolerances, refinement_factor=.5, max_levels=2, max_solves=5)
# saved_observations = report.to_dict()
from sipi import FEMShapeAdaptiveResolutionDocument
from sipi.execution import normalize_saved
request = FEMShapeAdaptiveResolutionDocument(line, outer_documents=outer,
    tolerances=tolerances, refinement_factor=.5, max_levels=2, max_solves=5)
assert FEMShapeAdaptiveResolutionDocument.loads(request.dumps()).dumps() == request.dumps()
assert normalize_saved(request.dumps()) == request.dumps()
```
Call analyze() or use common saved execution, requests, records, projects or CLI.
The host max_evaluations limits whole line attempts and is checked before fields.
The configured minimum two-comparison/all-outer budget must fit; later exhaustion
retains completed attempts instead of silently adding work. Every line retains
its current, derivative, material and flux checks. Unselected quantities are not
qualified, and finite accepted differences are not absolute error certificates.

A level-limited or outer-unaccepted result is completed but accepted=False; no
selected line exists. Budget exhaustion and field/setup errors have status=failed
and preserve their partial result. A budget failure has failure=None inside the
result and ResolutionBudgetExceeded in the execution error, bound to the original
saved request and controls. Typed field errors retain their original current
observations and exact failed input. User interruption propagates.

Default execution-record/1 continues to reject non-null partial failed results.
Explicit execution-record/2 preserves the supported typed and budget variants,
including attached project round-trips. It checks flags and input/error binding;
it does not certify the numerical validity of an imported receipt.

The actual saved test repeats the registered base/half/quarter closed pair. It
remains mesh-unaccepted under the original all-six-quantity 1% criterion, selects
nothing and runs no outer fields. Exact direct-API observations and independent
line identities are checked. Transport deliberately reuses those observed fields
for budget/typed failures and does not count replay as new physical validation.
