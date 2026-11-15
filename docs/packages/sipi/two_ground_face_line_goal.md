# One-parameter goals with two-ground face metals

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_line_goal.md)

`seek_two_ground_face_line_quantity` in `sipi.two_ground_face_line_goal` connects
[face-metal lines](two_ground_face_panel_line.md) to the existing bounded
one-positive-parameter search. Select scalar `impedance_real` (Re(Zc), ohms)
or `attenuation` (Re(gamma), Np/m), or paired
`differential_forward_impedance_real` / `common_forward_impedance_real`
(Re(Zdd)/Re(Zcc), ohms). Paired values use the full characteristic matrix under
separate Ic=0/Id=0 launches. They are not independent modes or terminal impedances.

The factory must return an explicit face-metal document with one positive
frequency, zero length and one scalar or two ordered paired signals. Whole-boundary
documents are refused. Both endpoints must succeed; an endpoint within absolute
tolerance can be selected. Otherwise residuals must bracket zero. Bisection
establishes neither continuity, monotonicity, uniqueness nor a global optimum.
The callable is not serialized. Existing whole-boundary goals remain unchanged.

The example admits a factory without executing the search:

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument
from sipi.two_ground_face_line_goal import seek_two_ground_face_line_quantity

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1., roughness=dict(kind="smooth"))

def line(width):
    section = CrossSection([Layer("dielectric", .002, 4., tan_delta=.003)],
        [Trace("signal", 0., width, .0007, .00005)], .008, top="ground")
    faces = dict(zip(("bottom", "top", "left", "right"),
                     [metal(sigma) for sigma in (58e6, 35e6, 21e6, 45e6)]))
    return TwoGroundFacePanelTransmissionLineDocument(
        CrossSectionDocument(section, mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05)),
        [2e9], materials={}, conductors=dict(signal=faces),
        reference=dict(kind="surfaces", bottom=metal(58e6), top=metal(21e6), sides=None, conductors={}),
        ground_thickness=35e-6, length=0., panels_per_edge=128,
        ground_modes=128, interpolation_degree=16)

assert line(.0006).to_dict()["length_m"] == 0.
# Explicit field work:
# result = seek_two_ground_face_line_quantity(line, [.00055, .00065], 58.,
#     quantity="impedance_real", tolerance=.05, max_evaluations=40)
```

The 5..10000 attempt budget reserves three actual evaluations: joint refinement,
volume-only, then panel-only. History preserves that order. All refined inputs
are admitted before each search solve. Halve resolved edge/far/grade for volume
refinement and double panels for current refinement. Frequency, signal names,
ground modes and interpolation controls stay fixed. Refinements use the frozen
selected input without recalling the factory, preserving every face, coating,
roughness, reference-metal and dielectric assignment.

Every refinement must meet the original absolute target. Relative changes from
nominal and joint versus each single-axis result must be at most 0.005; the
previous value is the denominator, and zero admits only zero. No tolerance
relaxation, clipping or retry turns a failed refinement into success. Only
identical dielectric meshes are reused within this call; face currents remain
explicit. The attempt budget does not bound wall time, memory or matrix work.

`TwoGroundFaceLineQuantityGoalError.to_dict()` retains attempts, history, stage,
failed input/parameter, original typed line error and available current/mesh
observations. Failed attempts count; interrupts propagate. Successful results
retain all selected/refined documents and diagnostics. Use the separate
[quantity study](two_ground_face_line_study.md) for manufacturing samples.

The registered physical case uses the example's 2 GHz offset scalar line,
width 0.55–0.65 mm, target 58 ohms with 0.05-ohm tolerance, 128→256 panels and
40 attempts. Independent sqrt(Z/Y) and sqrt(ZY) are checked at relative 1e-12.
A frozen selected geometry is separately checked at 256 panels/256 ground modes
with mesh halving and 8/16/32 mm finite outer boxes, applying the unchanged 0.01
relative limit to R/L/C0, real impedance and attenuation. That explicit large-box
resolution does not qualify the default 128 modes there. Tests also retain the
original four-quantity roots, failed stages, budgets and convergence gates.
These selected checks are not an infinite-domain, browser, cross-platform or
measured-accuracy certificate; consult exact artifact records for results.

[Save a face-metal goal](two_ground_face_line_goal_document.md)
