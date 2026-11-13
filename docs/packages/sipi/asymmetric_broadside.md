# Unequal broadside conductors in three dielectrics

`asymmetric_layered_broadside_stripline` builds two rectangular conductors
between grounded planes. The lower conductor is `positive` and the upper
conductor is `negative`. Each has its own positive width and copper thickness.
All lengths are metres; permittivities and loss tangents are dimensionless.

`lower_height` and `upper_height` are copper-to-plane clearances, excluding
copper. `gap` separates the facing copper surfaces. The lower dielectric ends
at the lower copper top, the gap dielectric fills the gap, and the upper
dielectric starts at the upper copper bottom. The total plane spacing is
`lower_height + lower_thickness + gap + upper_thickness + upper_height`.
The three materials may have independent permittivity and loss tangent.

The signed horizontal `offset` places the two centres at `-offset/2` and
`+offset/2`; it is not an edge gap or a pitch constraint. Side walls are open
(zero normal electrostatic flux), requiring a separate outer-width check.
The default width is `max(12*plane_spacing, 4*(max(widths) + abs(offset)))`.
Zero copper thickness, nonpositive clearances, invalid material data and
conductors touching the outer box are rejected. No taper is inferred.

```python
from sipi import asymmetric_layered_broadside_stripline, CrossSectionDocument

section = asymmetric_layered_broadside_stripline(
    lower_width=.4e-3, upper_width=.7e-3,
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
assert [trace.name for trace in section.traces] == ['positive', 'negative']
```

The geometry document retains the actual conductors, layers and mesh controls.
The same factory name is available in editable template inputs, tolerance
studies and width goals. Existing named inputs retain their previous contracts.
This registration does not add a user interface form.

`section.analyze(...)` returns full capacitance and vacuum-derived inductance
matrices. Unequal conductors or unequal surrounding materials generally have
coupled differential/common coordinates; do not call them independent even/odd
modes. `z_diff_forward` is the existing real forward differential-launch
quantity, not a general complex lossy mode impedance.

The qualified case above compares complex and vacuum P1 energy matrices with
independent scikit-fem assembly and an independently specified height/material
mask. Tests retain separate mesh (1%) and doubled outer-width (0.5%) gates,
vacuum/uniform-material invariants, reciprocity/positive energy, vertical and
horizontal reflection (0.5% after remeshing), and exact geometry reduction to
the existing equal-width/equal-thickness factory. These tests do not certify
arbitrary dimensions, conductor loss, material data or measured accuracy.

## Saved studies and width goals

Saved studies and goals require `quantity='z_diff_forward'`; symmetric-mode
objectives are rejected even if one particular input happens to be symmetric.
Sampling a lower width or an upper copper thickness preserves the other explicit
dimensions. A thickness change changes total plane spacing because the external
clearances stay fixed. Horizontal fixed pitch and the two-layer height-sum
constraint are not applicable to this vertical, three-material stack.

```python
from sipi import ImpedanceDesignDocument
from sipi.template_document import TemplateSectionDocument

parameters = dict(
    lower_width=.4e-3, upper_width=.7e-3,
    lower_thickness=25e-6, upper_thickness=45e-6,
    lower_height=.35e-3, upper_height=.55e-3, gap=.25e-3,
    lower_eps_r=3., gap_eps_r=4., upper_eps_r=5., offset=.15e-3,
    lower_tan_delta=.01, gap_tan_delta=.02, upper_tan_delta=.03,
    box_width=.012,
)
mesh = dict(edge_size=5e-6, far_size=.15e-3, grade=.15)
name = 'asymmetric_layered_broadside_stripline'
editable = TemplateSectionDocument(name, parameters, mesh=mesh)
goal = ImpedanceDesignDocument(
    name, parameters, variable='lower_width', bounds=[.2e-3, .8e-3],
    target=50., quantity='z_diff_forward', mesh=mesh,
    tolerance=.5, search_tolerance=.05,
)
assert ImpedanceDesignDocument.loads(goal.dumps()).dumps() == goal.dumps()
```

Call `goal.solve()` to search and perform the separate half-mesh check. Both
requested and refined residuals must meet the explicit tolerance. The qualified
50-ohm case checks both within 0.5 ohm and replays the direct API history exactly;
this does not establish an absolute physical impedance error. Saved tests also
cover PCG64 sampling, correlated width/thickness rows, gap-material sweeps,
common execution and preservation of invalid normal-distribution rows.

[한국어](../../locales/ko/pages/packages/sipi/asymmetric_broadside.md)
