# IID yield of lossy line quantities

[한국어](../../locales/ko/pages/packages/sipi/line_yield.md) · [Scalar samples](line_study.md) · [Paired samples](differential_line_study.md) · [Quasi-static impedance yield](yield.md)

`sipi.line-quantity-yield/1` assesses inclusive acceptance limits for one fixed
`LineQuantityStudyDocument` (/1 or /2). Limits use that study's quantity and unit:
Re(Zc) or forward Re(Zdd) in ohms, scalar attenuation in Np/m. Completed
attenuation may be zero. Existing quasi-static `impedance-yield/1` is unchanged.
The paired quantity retains its explicit [Ic=0 forward launch](differential_line_goal.md),
not an independent eigenmode or finite-terminal input impedance.

Only iid uniform and normal source samples are accepted. Normal correlation
between variables within a row is allowed; rows still follow the stated iid
sampling model. Sweep/corners are not population-yield experiments and reject
before fields. The original order, seed, vectors, geometry/material constraints,
line inputs and failed rows remain. No resampling, clipping or removal occurs.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.line_yield import LineQuantityYieldDocument
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
    sampling=dict(kind='uniform', count=3, seed=123,
        variables=[dict(name='left_width', lower=.6e-3, upper=.8e-3)]))
line_study = LineQuantityStudyDocument(source, schema='sipi.line-quantity-study/2',
    quantity='differential_forward_impedance_real',
    conductor=dict(kind='surface-boundaries',
        conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
        reference=metal(58e6, 0.), ground_thickness=35e-6))
request = LineQuantityYieldDocument(line_study, minimum=95., maximum=105.,
                                    confidence=.95, minimum_yield=.9)
assert normalize_saved(request.dumps()) == request.dumps()
report = execute_saved(request.dumps(), max_evaluations=3)
assert report['status'] == 'complete'
assert report['result']['count'] == 3 and report['result']['unresolved'] == 0
assert report['result']['unit'] == 'ohm'
assert report['result']['goal_status'] == 'undetermined'
assert len(report['result']['rows']) == 3
```

The saved object has exactly schema, study, minimum, maximum, confidence and
minimum_yield. At least one nonnegative finite limit is required; null means
unbounded on that side. If both are present minimum <= maximum, with equality
accepted. Confidence must be strictly between 0 and 1 at floating-point precision.
The optional minimum_yield is in [0,1]. Unknown/missing fields, duplicate keys
and nonfinite numbers reject. The caller's entire sample-count budget is checked
before field work without clamping. The request does not select or adapt a design.

For N original rows, K within limits, F outside, and U unresolved, N=K+F+U.
Failures, including invalid normal geometry, are unresolved rather than silently
converted to numerical values or definite out-of-limit results. The observed
fraction is bounded by [K/N, (K+U)/N]. The confidence interval is the union of
central equal-tailed exact Clopper–Pearson intervals over all possible unresolved
labels: lower endpoint at K successes and upper endpoint at K+U. Zero/all-success
endpoints are explicit, not clipped numerical estimates. All unresolved gives [0,1].

An optional yield goal passes when the lower confidence bound is at least the
goal, fails when the upper bound is below it, and is otherwise undetermined.
A complete calculation can have an undetermined or failed goal. Shared execution
is `incomplete` if rows are unresolved; all rows and interval bounds remain.
The point sample fraction is never used as a confidence guarantee.

```python
from sipi.dielectric import ConstantDielectric

source = ImpedanceStudyDocument('stripline',
    dict(width=.5e-3, plane_spacing=1e-3, eps_r=1., box_width=4e-3),
    quantity='z0', frequency=1e9, materials={'dielectric': ConstantDielectric(4., 0.)},
    mesh=dict(edge_size=2.5e-6, far_size=.125e-3, grade=.075),
    material_variables={'dk': dict(region='dielectric', path=['eps_r'])},
    sampling=dict(kind='uniform', count=3, seed=12,
        variables=[dict(name='dk', lower=3., upper=5.)]))
line_study = LineQuantityStudyDocument(source, conductor=dict(kind='perfect'),
                                       quantity='attenuation')
assessment = LineQuantityYieldDocument(line_study, minimum=0., maximum=0.,
                                       minimum_yield=.9).analyze(max_evaluations=3)
assert assessment.passed == 3 and assessment.unresolved == 0
assert assessment.to_dict()['unit'] == 'Np/m'
assert assessment.goal_status == 'undetermined'
```

`assess_line_yield(study_result, ...)` also works on an existing completed study
result without rerunning fields. It checks quantity, variable names, full count,
row order and exact regenerated sample vectors, plus complete/failed value and
phase consistency. These structural checks do not authenticate manually
constructed solver results. The returned `LineYieldAssessment` retains the
original study and full Python row results; JSON preserves each row's values,
phase, errors and available input snapshots together with its classification.

The interval covers finite iid sampling and unresolved labels for the supplied
model. It does not cover numerical/mesh error, material-fit error or uncertainty
in the manufacturing distribution. It is not measured production yield. Inspect
field and outer-domain validity across the sampling range. Repeated/adaptive
candidate selection requires a separate multiple-comparison contract; this
single fixed-study interval does not provide one.

Validation requires independent finite binomial-sum inversion and SciPy exact
binomial intervals within 1e-12 absolute endpoint error, all unresolved-label
possibilities, inclusive/one-sided limits and confidence-bound goal decisions.
Actual finite-metal paired random rows replay direct line studies within 1e-10
for RLGC/Zc, with exact vectors and snapshots. Scalar zero-attenuation and
correlated-normal invalid geometry exercise units and unknown preservation.
Existing yield and fixed-candidate selection regression remains included when
shared criteria change. These are related checks, not new measured geometry,
full-regression, application or Windows acceptance.

```sh
python -m pytest -q tests/sipi/test_line_yield.py tests/sipi/test_yield_assessment.py tests/sipi/test_yield_design.py tests/sipi/test_execution.py
```
