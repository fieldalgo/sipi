# Two-variable forward impedance targets

[한국어](../../locales/ko/pages/packages/sipi/pair_line_goal.md) ·
[One-variable common-current goals](common_forward_line_goal.md) ·
[Transmission lines](line_model.md)

`sipi.pair_line_goal.seek_forward_pair_impedances` varies two positive bounded
parameters to match **(Re(Zdd), Re(Zcc))**, in that order, for a full complex
two-signal line. The factory returns a `TransmissionLineDocument` with one
positive frequency and zero length. Frequency and ordered signal names must
stay fixed. Geometry, materials and explicit conductor laws may vary; their
physical validity remains the caller's responsibility.

Use Vd=V1−V2, Id=(I1−I2)/2, Vc=(V1+V2)/2, Ic=I1+I2.
Zdd is the forward launch with Ic=0; Zcc is the separate launch with Id=0.
Asymmetric off-diagonal coupling is retained. Neither launch condition is
imposed everywhere downstream. Targets are real parts, not magnitudes,
decoupled modal impedances or finite-line terminal input impedances.

## Example and replay

Lengths below are metres, conductivities S/m and target tolerances ohms.
The example starts at a previously qualified point and uses two evaluations:
the requested mesh and the required refinement. To exercise the search,
use `initial=[.7e-3, .35e-3]` and `max_evaluations=64` instead. That search
and both finite outer-domain checks are included in the numerical tests.

```python
import numpy as np
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.pair_line_goal import seek_forward_pair_impedances

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

goal = seek_forward_pair_impedances(
    line, [[.4e-3, .9e-3], [.2e-3, .6e-3]], [110., 40.],
    tolerances=[.25, .125],
    initial=[.6013576047896128e-3, .4103854246303812e-3],
    max_evaluations=2)
assert np.all(abs(np.array(goal.residuals)) <= goal.tolerances)
assert np.all(abs(np.array(goal.refined_residuals)) <= goal.tolerances)
assert len(goal.history) == 2
```

Input snapshots preserve the exact chosen and refined physical models.
Accessors reconstruct fresh documents; changing one does not change the
saved input. The report is JSON serializable, but it is not a new saved-input
schema or a serializable factory. Existing input schema versions stay unchanged.

```python
import json
report = goal.to_dict()
json.dumps(report, allow_nan=False)
assert report['quantities'] == [
    'differential_forward_impedance_real', 'common_forward_impedance_real']
coarse = goal.document.to_dict()
fine = goal.refined_document.to_dict()
for key in ['edge_size', 'far_size', 'grade']:
    coarse['cross_section']['mesh'][key] /= 2
assert coarse == fine
assert goal.history[-1].stage == 'refinement'
```

## Search and failure contract

Bounds are two increasing finite positive pairs; both targets and absolute
tolerances are positive finite pairs. The initial point lies in the closed
bounds, defaulting to their midpoint. Boolean controls are rejected. The
attempt budget is an integer from 2 through 10000.

The existing bounded least-squares helper normalizes each parameter to [0,1]
and each residual by its tolerance. It uses 1%-range central/one-sided
Jacobian probes and xtol=ftol=1e-4, gtol=1e-3. A cached parameter tuple costs
no new attempt. Every uncached factory, validation, extraction or diagnostic
attempt counts, including failed attempts and Jacobian probes. One attempt
is reserved for the final refinement. The budget does not bound internal
solves, memory or execution time; the cache retains full results.

The final evaluation halves edge size, far size and grading in the frozen
chosen input without calling the factory again. Both targets must meet their
original absolute tolerances on both meshes. An initial match still refines;
an optimizer success flag alone cannot accept a missed target.

`ForwardPairGoalError` retains completed `history`, `attempts`, `stage`,
`failed_parameters`, available `input_json`, `cause_type` and the original
exception cause. Control errors occur before the factory. No uniqueness,
feasibility, continuous response or global optimum is certified; a rank-deficient
but feasible point may pass. Inspect the report and the physical validity of
the whole search domain before using a result.

## Validation and limits

Independent power-dual modal circuits supply closed-form impedances and a
known two-parameter root, including lossless and rescaled-parameter limits.
Test-only scikit-rf 2.2.0 compares the modal characteristic impedances within
1e-10. Independent balanced 2N voltage/current eigenspaces compare the full
physical characteristic matrix and both targets within 1e-10; this reuses
the extracted RLGC and is not an independent geometry extraction.

The 1 GHz asymmetric section above is searched from (.7,.35) mm toward
(110,40) ohms with tolerances (.25,.125) ohms. Requested and halved meshes
must satisfy both targets and change each target by at most 0.5%. On the
refined mesh, box/air dimensions 24/10, 36/15 and 48/20 mm must stay within
the same target tolerances, within 0.5% of the smallest-domain result, and
have decreasing successive absolute changes for each target. These are
separate finite-case checks, not automatic outer-domain checks in the API,
monotonic convergence or an infinite-domain error bound.

Strict controls, fixed identities, cache/budget accounting, original errors,
stationary misses, refinement misses and saved-input replay are regression
tested. No measured or full-wave accuracy, production yield, new platform
or global optimizer certification follows from these tests.
