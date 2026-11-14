# Bounded refinement of checked FEM lines

`refine_fem_shape_line_resolution` retains a finite history while refining the
explicit mesh recipe. Every selected entry/frequency must pass two consecutive
finer-versus-previous comparisons before the larger-domain checks run. Every
outer comparison must then pass before `selected_evaluation` returns a line.
The ordinary FEM line and other resolution defaults are unchanged.

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
assert len(outer) == 2
```
Input rules and SI tolerances are those of [finite resolution](fem_shape_resolution.md).
Outer templates describe fixed expanded domains with the first finer mesh recipe.
At selection, only those mesh settings are replaced by the candidate recipe;
physical traces, layers, metal properties, frequency, length and ports stay fixed.
All input templates and the minimum two-pass/outer budget are checked before fields.

`max_levels` counts attempted finer meshes (2–8). `max_solves` counts whole line
attempts (4–16), including base and all outer checks; internal vacuum/voltage solves
are additional work. Before each finer attempt, the remaining budget must also
cover every required outer attempt. Completed results are reused. The original
current, derivative, material and flux checks still run at every actual extraction.

The report's stop_reason is accepted, mesh-unaccepted, outer-unaccepted,
budget-exhausted or field-failed. Level-limited and outer disagreements are
completed but unaccepted. Exhausted budgets and field/setup errors are incomplete.
Only accepted reports expose selected_evaluation on the original physical domain.
No result is selected after one pass, separated passes, or unresolved outer checks.

`to_dict()` retains every attempted input, completed current record, per-entry
comparison and typed partial failure. Setup errors preserve the raw attempted
input. User interruption propagates. Finite agreement is not an asymptotic or
absolute error certificate; this algorithm does not repair a difficult geometry.

The actual two-level test uses the registered closed pair at 2/3 GHz, with
5/2.5/1.25 micrometre edge sizes and all six quantities at 1% relative, zero
absolute allowance. It **remains mesh-unaccepted**, retains all three fields,
selects no result and runs no outer fields. Independent line identities and
exact earlier observations are checked separately. Controlled tests cover two
consecutive passes, outer disagreement, budget reservation, preparation/extraction
failure and typed evidence; those controls are not additional physical validation.
