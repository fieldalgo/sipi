# Explicit shape-current pair impedance goals

[Finite-frequency paired goals](shape_sampled_panel_pair_goal.md) require every supplied frequency to meet its targets.

`seek_shape_panel_forward_pair_impedances` connects the
[capacitance-shape current method](panel_shape_conductor.md) to the existing
bounded two-parameter search. Its factory returns a
`ShapePanelTransmissionLineDocument`; it does not silently convert an existing
panel or volume-line goal. Legacy and fixed coated per-boundary metals retain
their existing material and skin-depth rules.

Targets are the separate real forward differential and common impedances in ohms,
using the full complex characteristic matrix. They retain power-dual coordinates
Vd=V1−V2, Id=(I1−I2)/2, Vc=(V1+V2)/2, Ic=I1+I2. They are separate Ic=0 and Id=0
launches, not modal magnitudes or terminated input impedances.

The factory has two positive bounded parameters, two ordered signals, one fixed
positive frequency and zero length. Panel count, ground modes, interpolation
degree and `step_fraction` stay fixed during search. The shared bounded optimizer,
cache and budget rules follow [panel pair goals](panel_pair_goal.md).
`max_evaluations` (integer 4–10000) counts complete uncached attempts, including
failures and optimizer probes, not internal panel solves, time or memory.

Three attempts are reserved for the frozen chosen input: halve the volume mesh
controls; double panels per edge; then do both. Ground modes, interpolation and
shape step stay fixed. Every planned input is admitted before search field work.
All four results must meet both original absolute target tolerances. Each refined
value must change by at most 0.5% from nominal; joint must also change by at most
0.5% from each single-axis result. An initial target match still needs four actual
evaluations. No failed goal is returned as a qualified design.

`ShapePanelForwardPairDesign` retains selected and refined full results and fresh
shape-document accessors. `to_dict()` includes all current samples and two-step
diagnostics for those four results; search history contains completed inputs and
impedances. It is a report, not a saved factory/request schema. A
`ForwardPairGoalError` retains attempt counts, completed history, stage, failed
parameters/input and the original exception chain. If its cause is a
`ShapePanelLineError`, that cause's `to_dict()` exposes complete or partial current
work. Interrupts propagate. Existing methods, JSON inputs and numerical criteria
are unchanged.

The example starts outside the target tolerances. Dimensions are metres,
conductivity S/m and impedance tolerances ohms.

```python
import numpy as np
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.shape_panel_pair_goal import seek_shape_panel_forward_pair_impedances
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument

def line(width, gap):
    section = asymmetric_coupled_microstrip(
        left_width=width, right_width=.5e-3, gap=gap,
        substrate_height=.5e-3, eps_r=4., tan_delta=.02,
        left_thickness=35e-6, right_thickness=50e-6,
        box_width=24e-3, air_height=10e-3)
    def surface(conductivity, rms):
        return dict(conductivity=conductivity, relative_permeability=1.,
                    roughness=dict(kind='hammerstad', rms_m=rms))
    conductor = dict(kind='surface-boundaries',
        conductors={'positive': surface(58e6, .5e-6),
                    'negative': surface(35e6, 1e-6)},
        reference=surface(58e6, 0.), ground_thickness=35e-6)
    return TransmissionLineDocument(
        CrossSectionDocument(section, mesh=dict(
            edge_size=2.5e-6, far_size=.25e-3, grade=.075)),
        [1e9], materials={}, conductor=conductor, length=0.,
        schema='sipi.transmission-line/6')

goal = seek_shape_panel_forward_pair_impedances(
    lambda width, gap: ShapePanelTransmissionLineDocument(
        PanelTransmissionLineDocument(line(width, gap))), [[.4e-3, .9e-3], [.2e-3, .6e-3]], [110., 40.],
    tolerances=[.25, .125],
    initial=[.7e-3, .35e-3],
    max_evaluations=64)
assert np.all(abs(np.array(goal.residuals)) <= goal.tolerances)
for refinement in goal.refinements:
    assert np.all(abs(np.array(refinement.evaluation.impedances)-goal.targets) <= goal.tolerances)
assert 4 < len(goal.history) <= 64
assert len(goal.to_dict()['current_solver']['samples']) == 13
```

Finite panel/volume agreement does not establish outer-domain sufficiency, absolute accuracy, uniqueness or a global optimum. The bottom-ground/open-wall convex geometry scope remains unchanged. Selected finite outer-domain checks are separate; small mutual loss entries need their own resolution assessment.

[한국어](../../locales/ko/pages/packages/sipi/shape_panel_pair_goal.md)

[Saved requests and execution receipts](shape_panel_pair_goal_document.md).
