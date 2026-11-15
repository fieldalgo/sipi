# One-parameter two-ground line goals

[한국어](../../locales/ko/pages/packages/sipi/two_ground_line_goal.md)

`seek_two_ground_line_quantity` in `sipi.two_ground_line_goal` bisects one
positive variable. Select `impedance_real` (Re(Zc), ohms), `attenuation`
(Re(gamma), Np/m), `differential_forward_impedance_real` or
`common_forward_impedance_real` (Re(Zdd)/Re(Zcc), ohms). Paired values use the
full characteristic matrix under separate Ic=0/Id=0 launches; they are not
independent modes or finite terminal impedances.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument
from sipi.two_ground_line_goal import seek_two_ground_line_quantity

def metal(conductivity):
    return dict(conductivity=conductivity, relative_permeability=1., roughness=dict(kind='smooth'))

def line(width):
    section = CrossSection([Layer('dielectric', .002, 4., tan_delta=.003)],
        [Trace('signal', 0., width, .0007, .00005)], .008, top='ground')
    return TwoGroundPanelTransmissionLineDocument(
        CrossSectionDocument(section, mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05)),
        [2e9], materials={}, conductors=dict(signal=metal(58e6)),
        reference=dict(kind='surfaces', bottom=metal(58e6), top=metal(21e6), sides=None, conductors={}),
        ground_thickness=35e-6, length=0., panels_per_edge=64,
        ground_modes=128, interpolation_degree=12)

assert line(.0006).to_dict()['length_m'] == 0.
# result = seek_two_ground_line_quantity(line, [.00055, .00065], 58.,
#     quantity='impedance_real', tolerance=.05, max_evaluations=40)
```

The example defines and validates a factory without running the search. The
factory must return an explicit two-ground line with one positive frequency,
zero length and one scalar or two ordered paired signals. Both endpoints must
succeed; a boundary within absolute tolerance is eligible. Otherwise endpoint
residuals must bracket zero. Bisection does not prove continuity, monotonicity,
uniqueness or a global optimum. The factory is not serialized by this API.

Frequency, ordered signal names and all current-panel controls stay fixed.
All three refined inputs are admitted before each search field solve. The
5..10000 attempt budget reserves three evaluations for joint, volume-only and
panel-only refinement. Search uses the original bounded loop with two attempts
reserved outside it. Its existing final refinement is the joint calculation;
volume-only and panel-only follow. History records this actual order. Internal
matrix operations, time and memory are not separately bounded by this budget.

Refinements use the frozen selected input, without recalling the factory.
Halve resolved edge/far/grade for the volume axis, double panels per edge for
the panel axis; joint changes both. Ground modes, interpolation degree, metal,
materials, dimensions and boundaries remain unchanged. Panel doubling must fit
the existing resource limits. Every refinement must satisfy the same original
absolute target. Relative changes from nominal, and joint relative to each
single-axis result, must not exceed0.005. The previous comparison value is the
denominator; zero admits only zero. No averaging, retry, fallback or tolerance
change converts a failed refinement into a result.

The result retains the selected line, joint result, all three refinement inputs,
values, current/mesh observations and complete search history. Every failed
factory/field/diagnostic attempt counts. `TwoGroundLineQuantityGoalError.to_dict()`
retains attempts, stage, failed parameter/input, original typed line cause and
completed fields. Interrupts propagate. A successful bounded numerical search
is not an outer-domain, empirical-accuracy or platform certificate.

The registered physical case is the example's offset scalar line at2GHz,
width .55–.65mm, target58Ω±.05Ω,64→128 panels and40 attempts. Independent complex
sqrt(Z/Y) and sqrt(ZY) check selected and refined fields. Control tests verify
scalar and paired roots, frozen axes, all failed stages, reserved budgets,
zero attenuation and joint-versus-single convergence. Existing scalar/FEM/corner
goal regression and exact source/installed artifacts remain separate checks.
