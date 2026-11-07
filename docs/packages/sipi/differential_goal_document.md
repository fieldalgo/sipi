# Saved differential forward-impedance goals

[한국어](../../locales/ko/pages/packages/sipi/differential_goal_document.md) · [Scalar saved goals](line_goal_document.md) · [Forward launch contract](differential_line_goal.md) · [Shared execution](execution.md)

Explicit `sipi.line-quantity-design/2` adds
`differential_forward_impedance_real` to the two existing scalar quantities.
The constructor still defaults to `/1`; that version rejects the paired quantity.
Version 2 scalar requests behave identically to version 1. Neither version
implicitly accepts future quantity names.

The paired quantity targets the real part of the full lossy Zdd in ohms:
Vd=V1−V2, Id=(I1−I2)/2, launch Ic=I1+I2=0. It retains asymmetric coupling
and common voltage. It is not an independent eigenmode, a finite-terminal
impedance, abs(Zdd), or a promise of downstream Ic=0. See the
[API definition and convergence gates](differential_line_goal.md).

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
        air_height=5e-3, box_width=12e-3), quantity='z_diff_forward',
    frequency=1e9, materials={}, fixed_pitch_m=.95e-3,
    mesh=dict(edge_size=2.5e-6, far_size=.125e-3, grade=.075),
    sampling=dict(kind='sweep', count=2,
        variables=[dict(name='left_width', lower=.2e-3, upper=1e-3)]))
goal = LineQuantityDesignDocument(source, schema='sipi.line-quantity-design/2',
    conductor=dict(kind='surface-boundaries',
        conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
        reference=metal(58e6, 0.), ground_thickness=35e-6),
    quantity='differential_forward_impedance_real', target=100.,
    tolerance=.5, max_evaluations=24)
assert normalize_saved(goal.dumps()) == goal.dumps()
report = execute_saved(goal.dumps(), max_evaluations=24)
assert report['status'] == 'complete'
assert max(abs(report['result']['residual']), abs(report['result']['refined_residual'])) <= .5
assert report['result']['input']['schema'] == 'sipi.transmission-line/6'
assert report['result']['quantity'] == 'differential_forward_impedance_real'
```

The exact top-level fields are unchanged: schema, study, conductor, quantity,
target, tolerance and max_evaluations. For the paired quantity, nested study/3
or /4 must use `z_diff_forward`, two signals, one positive fixed frequency,
a count-2 sweep and exactly one variable with positive increasing bounds.
A `z_diff` modal source is rejected rather than silently reinterpreted. Nested
`z_diff_forward` specifies the source contract; the target uses full complex
lossy RLGC, not the nested study's real quasi-static diagnostic. No preliminary
study analysis is performed.

Existing fixed center pitch and total plane spacing constraints are reused on
their supported templates. A /4 source may bind a single material-model numeric
leaf; its selected material survives in both requested and refined inputs.
Conductor laws are fixed strict line/6 records, including supported face laws.
Parsing retains source endpoint geometry/material preflight and nominal
conductor guards without meshing. Later conductor/candidate failures remain
counted API attempts, with their phase and available input.

The shared execution budget is checked before field solves. Successful reports
retain exact trial history, units and zero-length requested/refined line/6
inputs at a 50-ohm network reference, which does not define Zdd. Errors retain
completed history and failed attempts; no partial successful design is returned.
The Python result retains full matrices, which can also be obtained by replaying
the saved selected lines. Limits on one-dimensional search, physical model
validity and outer-domain convergence remain the API's responsibility split.
Saved `line-quantity-study/1` is still scalar-only; this is a goal schema, not
a paired tolerance or yield schema. Use separate
[study /2](differential_line_study.md) for paired descriptive sampling.

Validation compares the unequal-width/thickness/metal fixed-pitch 100-ohm goal
with the direct API: exact histories/inputs, RLGC/Zc within 1e-10 and both target
residuals within 0.5 ohm. For a homogeneous PEC pair, complex impedance scales
as Zvac/sqrt(eps_r*(1-j*tan_delta)). A material-epsilon goal checks this identity
within 1e-10, the requested epsilon within 1.5%, and both target residuals within
0.5 ohm. This is an analytical material-scaling check using a computed vacuum
geometry reference, not an independent measured geometry benchmark. Fixed
height, tilted-material source preservation, scalar equivalence, strict input,
shared budget and retained failures are also checked. No new full regression,
measured accuracy, app or Windows acceptance follows from these related tests.

A separate balanced voltage/current telegrapher eigenspace also checks the saved selected Zc/Zdd within 1e-10; it does not use the production Schur square root.

```sh
python -m pytest -q tests/sipi/test_differential_goal_document.py tests/sipi/test_line_goal_document.py tests/sipi/test_line_study.py tests/sipi/test_execution.py tests/sipi/test_material_variables.py
```
