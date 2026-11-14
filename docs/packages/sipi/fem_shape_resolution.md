# Finite resolution observations for checked FEM lines

`assess_fem_shape_line_resolution` connects a checked FEM line to explicit
mesh and open-domain comparisons. It does not automatically change the current
method or certify absolute accuracy. Existing line resolution APIs retain their
inputs and numerical criteria.

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
assert len(outer) == 2
```

The budget counts complete line attempts, including base, finer mesh and every
outer input. Each line performs its original current, geometry derivative,
finite-difference, material and flux checks. Internal capacitance and voltage
solves are additional work within each attempt. Preflight validates the complete
budget and all inputs before fields; it requires explicit edge_size, far_size and
grade. Refinement multiplies only these three settings by a factor in (0,1).

Every outer input must use the refined mesh settings, retain all physical traces,
interfaces, materials, surface metals, frequencies, length and port references,
and strictly expand an open side or the topmost layer under an open top. Grounded
planes cannot move. No width or top padding may shrink. Internal interfaces and
layer count cannot change. The finer mesh is compared with base; every outer
input is compared independently with that finer mesh, not with the previous outer.

Each selected matrix entry at every supplied frequency is checked against
`absolute + relative * max(abs(reference), abs(actual))`. Units are ohm/m for R,
H/m for internal/external L, F/m for C/C0, and S/m for G. There is no small-entry
floor, inferred tolerance or diagonal scaling. Zero allowance requests exact
agreement. Unselected quantities are not assessed. A completed disagreement is
retained with `completed=True`, `accepted=False` and no solver failure.

The report contains immutable comparisons and exact normalized inputs. Its
`to_dict()` adds every completed line's full current evidence. A field/comparison
exception stops subsequent work while retaining completed results, stage, input,
kind and message. Typed FEM line failures also preserve original current/partial
evidence in detached `failure.details`. User interruption propagates unchanged.

Tests exercise the registered 1% per-entry, zero-absolute criterion on the closed
pair at 2/3 GHz, with 8 mm base width and 16/32 mm outer inputs. They retain actual
observations, independently verify uniform-dielectric and coated-metal/network
relations, and replay those results to check exact disagreement and staged failure
handling. These finite samples do not prove asymptotic convergence, weak-mode
accuracy, arbitrary geometry/frequency coverage, empirical validity or another
platform's results. No general nested-mesh capability is added.

[한국어](../../../locales/ko/pages/packages/sipi/fem_shape_resolution.md)

The registered coarse-to-finer input is **not accepted**: the largest mutual
R change is about 6.57% and internal-L change about 2.93%, both above the
unchanged 1% allowance. The two outer comparisons pass for these samples.
Tests preserve that completed disagreement, not a claim of sufficient mesh
resolution. The original failed all-accepted expectation is retained in the
development evidence; no physical input or numerical allowance was changed.
