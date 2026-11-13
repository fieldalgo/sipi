# Trapezoidal broadside conductors

`tapered_layered_broadside_stripline` extends the explicit three-dielectric
broadside geometry with independent bottom and top widths for each conductor.
All lengths are metres. `lower_width` and `upper_width` are the widths at
each conductor's geometric bottom face (smaller y). `lower_top_width` and
`upper_top_width` are measured at its top face (larger y). Thus the faces
across the vertical gap have widths `lower_top_width` and `upper_width`.
The sides are straight; both inward and outward taper are allowed.

Copper thicknesses and all four widths must be positive. `lower_height` and
`upper_height` exclude copper; `gap` is the vertical metal-to-metal clearance.
The lower material ends at the lower copper top, the gap material fills the
gap, and the upper material starts at the upper copper bottom. The lower
conductor is `positive`, the upper one `negative`. Signed `offset` places their
centres at `-offset/2` and `+offset/2`. This does not imply exchange symmetry.

The two planes are grounded. The side walls impose zero normal flux and need
an outer-width check. The default box width is
`max(12*plane_spacing, 4*(max(all_four_widths) + abs(offset)))`.
Clipped copper and invalid materials are rejected. If each top width equals
its bottom width, the geometry document exactly matches the existing
rectangular `asymmetric_layered_broadside_stripline` factory.

```python
from sipi import tapered_layered_broadside_stripline, CrossSectionDocument

section = tapered_layered_broadside_stripline(
    lower_width=.4e-3, lower_top_width=.32e-3,
    upper_width=.7e-3, upper_top_width=.55e-3,
    lower_thickness=25e-6, upper_thickness=45e-6,
    lower_height=.35e-3, upper_height=.55e-3, gap=.25e-3,
    lower_eps_r=3., gap_eps_r=4., upper_eps_r=5.,
    lower_tan_delta=.01, gap_tan_delta=.02, upper_tan_delta=.03,
    offset=.15e-3, box_width=.012,
)
document = CrossSectionDocument(
    section, mesh=dict(edge_size=5e-6, far_size=.15e-3, grade=.15),
)
assert CrossSectionDocument.loads(document.dumps()).dumps() == document.dumps()
assert section.traces[1].top_width == .55e-3
```

`section.analyze(...)` returns the full capacitance and external inductance
matrices and the existing real `z_diff_forward` launch quantity. Asymmetric
materials and conductors generally couple differential and common coordinates;
independent even/odd modes are not inferred. This API does not add a new
conductor-loss model or a user interface form.

The specified case has independent scikit-fem complex/vacuum assembly with an
independently prescribed dielectric mask (normalized difference at most
`1e-10`), separate half-mesh (1%) and doubled box-width (0.5%) criteria,
vacuum/uniform-material invariants and positive reciprocal matrices.
Vertical reflection swaps both conductors and their top/bottom faces;
horizontal and vertical reflected solves each have a 0.5% remeshing criterion.
These are qualified numerical checks, not absolute physical error bounds or
certification of arbitrary taper angles.

## Saved studies and etch-face goals

The same factory name is registered for editable template inputs, versioned
tolerance studies and design goals. They require `quantity='z_diff_forward'`;
symmetry-based quantities are rejected. Sampling `lower_top_width` keeps the
lower bottom width, upper conductor and vertical clearances fixed. Correlated
bottom/top width samples are supported without converting them to an etch
angle. Invalid normal-distribution rows remain failed rows, not resampled ones.
Horizontal fixed pitch and the two-layer height-sum constraint are inapplicable.

```python
from sipi import ImpedanceDesignDocument
from sipi.template_document import TemplateSectionDocument

parameters = dict(
    lower_width=.4e-3, lower_top_width=.32e-3,
    upper_width=.7e-3, upper_top_width=.55e-3,
    lower_thickness=25e-6, upper_thickness=45e-6,
    lower_height=.35e-3, upper_height=.55e-3, gap=.25e-3,
    lower_eps_r=3., gap_eps_r=4., upper_eps_r=5., offset=.15e-3,
    lower_tan_delta=.01, gap_tan_delta=.02, upper_tan_delta=.03,
    box_width=.012,
)
mesh = dict(edge_size=5e-6, far_size=.15e-3, grade=.15)
name = 'tapered_layered_broadside_stripline'
editable = TemplateSectionDocument(name, parameters, mesh=mesh)
goal = ImpedanceDesignDocument(
    name, parameters, variable='lower_top_width', bounds=[.2e-3, .6e-3],
    target=50., quantity='z_diff_forward', mesh=mesh,
    tolerance=.5, search_tolerance=.05,
)
assert ImpedanceDesignDocument.loads(goal.dumps()).dumps() == goal.dumps()
```

`goal.solve()` searches that one width and performs the separate half-mesh
check. The qualified 50-ohm goal checks requested and refined residuals within
0.5 ohm and reproduces the direct API history. This is a numerical acceptance
condition, not an absolute physical error bound. Tests also cover PCG64
sampling, correlated face widths, material sweeps and common execution.

[한국어](../../locales/ko/pages/packages/sipi/tapered_broadside.md)
