# Coated panel pair goals

The existing `seek_panel_forward_pair_impedances` factory can explicitly return
`PanelTransmissionLineDocument` version 2 with a nested line version 7. Each
boundary retains its fixed bulk metal and ordered planar coatings while the
two geometric parameters vary. This uses the existing panel current method,
layered surface impedance and full complex characteristic matrix.

The example starts at a previously qualified point. It still executes the
nominal, volume-only, panel-only and joint refinement checks. For an actual
search from a mismatching point, use `initial=[.7e-3,.35e-3]` and
`max_evaluations=64`. Lengths are metres, conductivities S/m and targets ohms.

```python
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_pair_goal import seek_panel_forward_pair_impedances

MESH = dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075)


def material():
    return dict(kind='layered', conductivity=58e6, relative_permeability=1., coatings=[
        dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
        dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])


def factory(width, gap, *, box=.024, air=.010):
    section = asymmetric_coupled_microstrip(left_width=width, right_width=.5e-3,
        gap=gap, substrate_height=.5e-3, eps_r=4., tan_delta=.02,
        left_thickness=35e-6, right_thickness=50e-6, box_width=box, air_height=air)
    line = TransmissionLineDocument(CrossSectionDocument(section, mesh=MESH), [1e9],
        materials={}, length=0., conductor=dict(kind='surface-boundaries',
            conductors={t.name:material() for t in section.traces}, reference=material(),
            ground_thickness=35e-6), schema='sipi.transmission-line/7')
    return PanelTransmissionLineDocument(line, schema='sipi.panel-transmission-line/2')


goal = seek_panel_forward_pair_impedances(factory,
    [[.4e-3, .9e-3], [.2e-3, .6e-3]], [110., 40.],
    tolerances=[.25, .125], initial=[.0006073049209836395, .0004082505417130786],
    max_evaluations=4)
assert len(goal.history) == 4
assert all(abs(x) <= tol for x, tol in zip(goal.residuals, goal.tolerances))
```

The actual regression starts at 103.5177/39.0961 ohms and searches toward
110/40 ohms with absolute tolerances .25/.125 ohm. The selected width and gap
are approximately .607305 and .408251 mm. All four resolutions must meet the
original targets and the separate 0.5% refinement gates, including joint
versus each single-axis refinement. This is a finite, local design search;
it does not establish a unique solution or global feasibility.

A separate check freezes the selected geometry and uses the joint resolution
at 1, 2 and 4 GHz. Box width/air height are 24/10, 36/15 and 48/20 mm; ground
modes are 512, 768 and 1024. Both successive differential changes must be at
most 1e-4 of the first value at each frequency. The second common-mode change
must be smaller than the first. These outer checks are not automatically run
by the goal API. Targets are imposed at 1 GHz only; they are not imposed at
the other two frequencies.

Independent planar transfer matrices check each coating impedance. A 4-by-4
line transfer matrix checks the full characteristic matrix and the scattering
matrix of a 20 mm line. Reciprocity and passivity are also checked at that
nonzero length. These references reuse extracted RLGC; they are not independent
geometry extraction or measured accuracy. Full input, RLGC, boundary parts,
current integrals and search history are retained in the numerical test records.

Small mutual resistance entries retain the [panel-line accuracy limits](layered_panel_line.md).
Diagonal impedance acceptance does not certify their relative accuracy or an
infinite-domain limit. Coating core/skin-depth and panel geometry restrictions
remain in force. The saved panel goal wrapper still uses its existing version
1 input contract; this factory example does not add a saved coated goal schema.

[Pair goal contract](panel_pair_goal.md) · [한국어](../../locales/ko/pages/packages/sipi/layered_panel_goal.md)
