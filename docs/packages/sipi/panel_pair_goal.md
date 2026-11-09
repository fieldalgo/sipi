# Explicit panel-current pair impedance goals

[한국어](../../locales/ko/pages/packages/sipi/panel_pair_goal.md) · [Panel lines](panel_line.md) · [Existing forward goals](pair_line_goal.md)

`seek_panel_forward_pair_impedances` is an explicit two-parameter goal for
`PanelTransmissionLineDocument`. Existing line goals retain their original
method. The factory must return a two-signal line with one positive frequency
and zero length. Ordered signal names, frequency, panels per edge, ground modes
and interpolation degree remain fixed during the search.

Targets are `(Re(Zdd), Re(Zcc))` in ohms, using the full complex forward
characteristic matrix and the power-dual definitions Vd=V1−V2,
Id=(I1−I2)/2, Vc=(V1+V2)/2, Ic=I1+I2. Differential and common launches
are separate Ic=0 and Id=0 constraints; off-diagonal coupling remains.
These are not modal magnitudes or finite-terminal input impedances.

## Search and acceptance

Bounds, targets and tolerances are finite positive pairs. Bounds are strictly
increasing, initial parameters lie inside the closed bounds, and the default
initial point is the midpoint. Parameters retain the factory's units; target
tolerances are absolute ohms. The existing normalized bounded least-squares
helper uses 1%-range probes, xtol=ftol=1e-4 and gtol=1e-3.

`max_evaluations` is an integer from 4 through 10000. Every uncached attempt
counts, including failed factory, validation, extraction and diagnostic calls
and optimizer probes. Cached evaluations return residual copies. This budget
does not limit internal field solves, memory or time; full results are cached.

Three attempts are reserved to verify the frozen chosen physical input:

| Stage | Volume mesh | Boundary panels |
|---|---|---|
| `volume-refinement` | Halve edge size, far size and grading | Unchanged |
| `panel-refinement` | Unchanged | Double panels per edge |
| `joint-refinement` | Halve all three controls | Double panels per edge |

Ground modes and interpolation degree remain unchanged in all checks. The
factory is never called for a refinement. Before each search field solve,
the corresponding refined input documents must pass normalization, including
the existing panel limits. This does not predict whether mesh generation,
skin-depth admission or the field solve will succeed.

The nominal input and all three refinements must meet both original absolute
target tolerances. Each refined value must differ from the nominal value by
at most 0.5%, and the joint values must differ from each single-axis refinement
by at most 0.5%. An initial target match still requires four evaluations.
An optimizer success flag alone never accepts a missed target.

The returned immutable report preserves parameters, targets, tolerances,
nominal and refined input snapshots, full results, and completed evaluation
history. Document accessors return fresh documents. `to_dict()` is serializable
report data, not a new saved request schema or a serialized Python factory.

`ForwardPairGoalError` preserves history, actual attempts, stage, failed
parameters, available input JSON, cause type and the original exception.
Refinement target or convergence failures retain the failed completed row;
there is no partial success result. Correct the input or resolution and rerun
rather than interpreting an exception's history as a qualified design.

No uniqueness, global optimum, general feasibility, continuous response,
outer-domain error bound, measured accuracy or full-wave accuracy is certified.
Outer-domain checks are separate from the three automatic refinement checks.

## Example

This example begins at a qualified point and still performs all four evaluations.
For a search from a mismatching point use `initial=[.7e-3,.35e-3]` and
`max_evaluations=64`. Lengths are metres, conductivities S/m and tolerances ohms.

```python
import numpy as np
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_pair_goal import seek_panel_forward_pair_impedances
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

goal = seek_panel_forward_pair_impedances(
    lambda width, gap: PanelTransmissionLineDocument(line(width, gap)), [[.4e-3, .9e-3], [.2e-3, .6e-3]], [110., 40.],
    tolerances=[.25, .125],
    initial=[0.000603169086210573, 0.00040941866189257275],
    max_evaluations=4)
assert np.all(abs(np.array(goal.residuals)) <= goal.tolerances)
for refinement in goal.refinements:
    assert np.all(abs(np.array(refinement.evaluation.impedances)-goal.targets) <= goal.tolerances)
assert len(goal.history) == 4
```

## Validation and limits

Known coupled modal circuits verify the two-parameter root, lossless behavior
and parameter-unit rescaling. Test-only scikit-rf 2.2.0 independently supplies
the modal characteristic impedances. Error tests retain original causes and
attempt counts, including each refinement and stationary missed targets.

The heterogeneous asymmetric example is searched from (.7,.35) mm toward
(110,40) ohms with (.25,.125) ohm tolerances. All three independent refinement
checks are required. A balanced 2N voltage/current eigenspace independently
checks each selected/refined full characteristic matrix within 1e-10; it
reuses extracted RLGC and is not independent geometry extraction.

A separate pre-registered finite-domain study uses the selected parameters
and joint-refined controls at .5, 1 and 2 GHz with box/air sizes 24/10, 36/15
and 48/20 mm. Each value meets (110,40) ohms within (.5,.25) ohms; relative
changes stay below 0.5%, and successive absolute outer changes decrease for
both quantities at each frequency. These finite cases do not establish
monotonic convergence for arbitrary inputs, a continuous frequency band or
an infinite-domain error bound. They are not automatic outer checks in the
API. Previous saved schemas and calculation defaults are unchanged.
