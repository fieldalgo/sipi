# Panel lines with fixed metal coatings

`sipi.panel-transmission-line/2` explicitly combines a nested
`sipi.transmission-line/7` with the existing panel current calculation. Version
1 still accepts only nested line versions 1–6. The new version keeps the same
`schema`, `line` and `panel` keys; select it explicitly in the constructor.

Each signal and the common reference boundary can retain its own bulk metal
and ordered planar coating stack. The shared vacuum panel calculation supplies
the current Gram matrices. The existing layered surface impedance supplies
each boundary's frequency-dependent metal law. Their composition gives R and
internal L; dielectric C/G still use one volume mesh, and external L uses the
matching panel C0. No coating thickness is added to the saved geometry.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.execution import execute_saved

section = CrossSection([Layer("uniform", .002, 4.2, tan_delta=.02)],
    [Trace("signal", 0., .0005, .0002, thickness=35e-6)], .004)
metal = dict(kind="layered", conductivity=58e6, relative_permeability=1.,
    coatings=[dict(thickness_m=.2e-6, conductivity=14e6,
                   relative_permeability=3.)])
line = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1)), [1e9, 2e9],
    materials={}, conductor=dict(kind="surface-boundaries",
        conductors={"signal": metal}, reference=metal, ground_thickness=35e-6),
    length=.02, schema="sipi.transmission-line/7")
document = PanelTransmissionLineDocument(line, panels_per_edge=32,
    schema="sipi.panel-transmission-line/2")
result = execute_saved(document.dumps(), max_evaluations=2)
assert result["status"] == "complete"
assert result["result"]["current_solver"]["kind"] == "grounded-rectangle-panels"
```

Coatings retain the existing remaining-core, skin-depth and first-order
surface-perturbation restrictions. Geometry must satisfy the shared panel
kernel's convexity, clearance and resource restrictions: bottom ground, open
top/sides and positive conductor thickness. Unsupported common surface or
independent-face models are not converted. Perfect conductors keep zero R
and the prior panel calculation; this does not select ordinary FEM currents.

Verification separates panel refinement, dielectric volume refinement and
outer-domain changes. The fixed two-line checks preserve full matrices and
test planar transfer impedances, an independent 4-by-4 line transfer matrix,
reciprocity and passivity. A matrix maximum-norm change does not bound relative
error of a small mutual entry. Changing a current method does not resolve a
failed test of another method. Finite-domain checks are not an infinite-domain
or measured-accuracy certificate; resolve all three refinement axes for the
actual input and frequencies.

For example, the fixed symmetric pair's 1 GHz mutual R entry changes from
0.0859271 to 0.0460899 ohm/m when both outer dimensions double, about 46.4%,
although the maximum matrix-norm R change is about 0.281%. Panel refinement
alone changes that small entry by about 1.07%. These observations are not
per-entry convergence evidence. Select explicit absolute and relative limits
for every quantity that matters to the application, including mutual terms.

This version adds saved forward calculations. The existing direct factory API
can also perform [coated pair goals](layered_panel_goal.md); saved coated goal
wrappers and manufacturing studies are separate contracts. Existing [panel-line limits](panel_line.md) and
[layered metal assumptions](layered_metal.md) still apply.

[한국어](../../locales/ko/pages/packages/sipi/layered_panel_line.md)
