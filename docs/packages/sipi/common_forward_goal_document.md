# Saved common-current forward-impedance goals

**English** | [한국어](../../locales/ko/pages/packages/sipi/common_forward_goal_document.md)

Explicit `sipi.line-quantity-design/3` adds `common_forward_impedance_real`.
It retains both scalar quantities and the differential forward quantity.
The constructor still defaults to `/1`; versions 1 and 2 continue rejecting
common-current goals. Existing scalar and differential requests retain their
previous results. Saved study versions 1 and 2 also reject the new quantity.

The target is Re(Zcc) in ohms, with Vc=(V1+V2)/2, Ic=I1+I2 and launch
Id=(I1-I2)/2=0. Full lossy asymmetric coupling remains: differential voltage
need not vanish, and downstream Id need not stay zero. This is a specified
forward launch, not a decoupled mode, abs(Zcc), or finite-terminal impedance.
See [the API and convergence limits](common_forward_line_goal.md).

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_goal_document import LineQuantityDesignDocument
from sipi.execution import normalize_saved, execute_saved

def metal(sigma, rms):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness=dict(kind='hammerstad', rms_m=rms))
source = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3, substrate_height=.5e-3,
        eps_r=4., tan_delta=.02, left_thickness=35e-6, right_thickness=50e-6,
        air_height=10e-3, box_width=24e-3), quantity='z_diff_forward',
    frequency=1e9, materials={}, fixed_pitch_m=.95e-3,
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='sweep', count=2,
        variables=[dict(name='left_width', lower=.2e-3, upper=1e-3)]))
goal = LineQuantityDesignDocument(source, schema='sipi.line-quantity-design/3',
    conductor=dict(kind='surface-boundaries',
        conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
        reference=metal(58e6, 0.), ground_thickness=35e-6),
    quantity='common_forward_impedance_real', target=40.,
    tolerance=.125, max_evaluations=24)
assert normalize_saved(goal.dumps()) == goal.dumps()
report = execute_saved(goal.dumps(), max_evaluations=24)
assert report['status'] == 'complete'
assert max(abs(report['result']['residual']), abs(report['result']['refined_residual'])) <= .125
assert report['result']['input']['schema'] == 'sipi.transmission-line/6'
assert report['result']['quantity'] == 'common_forward_impedance_real'
```

The exact seven root keys are schema, study, conductor, quantity, target,
tolerance and max_evaluations. Nested study/3 or /4 must specify the existing
`z_diff_forward` paired input contract. That label supplies geometry/material
inputs only; the nested quasi-static study is never analyzed. The outer
`quantity` selects the common-current objective. A modal `z_diff` source is
rejected. One positive fixed frequency, a count-2 sweep, one variable with
positive increasing bounds, and exactly two ordered signals are required.

Fixed pitch and total stack height, material numeric-leaf bindings, strict
fixed line/6 conductor laws, endpoint geometry/material preflight and nominal
conductor checks retain their existing contracts. Parsing does no meshing.
Later factory, field or diagnostic failures preserve the actual attempt,
completed history, phase and available input. Shared execution checks its
budget before solving; a failed search returns no partially accepted design.

```python
import json
from sipi.line_model import TransmissionLineDocument
selected = TransmissionLineDocument.from_dict(report['result']['input'])
assert selected.to_dict()['length_m'] == 0.
assert report['result']['scope'] == 'bounded-single-parameter-common-forward-line-goal'
assert report['result']['history'][-1]['stage'] == 'refinement'
assert report['result']['evaluations'] <= 24
assert report['result']['unit'] == 'ohm'
assert goal.to_dict()['study']['quantity'] == 'z_diff_forward'
json.dumps(report, allow_nan=False)
```

Successful reports retain requested and refined zero-length line/6 inputs
at a 50-ohm network reference, which does not define Zcc. The selected physical
input is frozen while edge/far/grade are halved. Both target residuals must
pass the same tolerance. Outer-domain convergence is a separate caller check;
normalization and successful bounded search do not establish global existence,
uniqueness or manufacturing yield.

The asymmetric 40-ohm fixture is compared with the direct API using exact
history/input equality and full RLGC/Zc relative agreement within 1e-10,
with both residuals <=0.125 ohm. A separate balanced 2N telegrapher eigenspace
checks selected Zc/Zcc within 1e-10 independently of the production Schur root.
For a homogeneous PEC pair, an independent SPD geometric mean gives the
computed vacuum Zc; the analytic material scaling is
Zvac/sqrt(eps_r*(1-j*tan_delta)). The eps_r=3.7,tan_delta=.02 goal requires
relative scaling agreement1e-10, epsilon error<=1.5%, and both residuals<=.05ohm.
This is a material identity using computed geometry, not measured geometry
accuracy. The preceding API's qualified mesh/outer scope remains unchanged.

Old93 canonical saved inputs remain exact in source and installed packages;
strict input, fixed-height/tilted material preservation, old scalar/differential
equivalence, shared budgets and original failures are also checked. This adds
one explicit schema:94schemas/37templates. No new full-suite, measured/full-wave,
app, Windows or deployment acceptance is implied.
