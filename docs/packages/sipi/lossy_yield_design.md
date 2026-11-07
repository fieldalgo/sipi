# Fixed lossy-line candidates with simultaneous yield bounds

[한국어](../../locales/ko/pages/packages/sipi/lossy_yield_design.md) · [Single-study yield](line_yield.md) · [Original selection contract](yield_design.md) · [Shared execution](execution.md)

Explicit `sipi.yield-design/2` applies the existing fixed-candidate selection
rules to `line-quantity-study/1` or `/2` inputs. The constructor still defaults
to `/1`, which takes quasi-static impedance studies and retains its output shape.
Version 2 candidates must all use the same explicit lossy quantity and the same
positive frequency. Re(Zc)/forward Re(Zdd) use ohms; scalar attenuation uses Np/m
and may be zero. Mixing these objectives or frequencies rejects before fields.

Every candidate is exactly name, cost and study. Names are unique, costs finite
and nonnegative, and cost_unit is one explicit caller-defined unit. Enumerate
1–32 candidates and their iid uniform/normal distributions before evaluating
any samples. No geometry objective, adaptive search or cost model is inferred.
The source's pitch, height, material, conductor and forward-launch definitions
remain unchanged. The example uses broad limits and a deliberately low 0.1 yield
goal to demonstrate transport with only two samples per candidate; these are
not recommended manufacturing acceptance criteria.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.yield_design import YieldDesignDocument
from sipi.execution import normalize_saved, execute_saved

def metal(sigma, rms):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness=dict(kind='hammerstad', rms_m=rms))

def candidate_study(lower, upper):
    nominal = (lower+upper)/2
    source = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
        dict(left_width=nominal, right_width=.5e-3, gap=.95e-3-(nominal+.5e-3)/2,
            substrate_height=.5e-3, eps_r=4., tan_delta=.02,
            left_thickness=35e-6, right_thickness=50e-6, air_height=5e-3, box_width=12e-3),
        quantity='z_diff_forward', frequency=1e9, materials={}, fixed_pitch_m=.95e-3,
        mesh=dict(edge_size=2.5e-6, far_size=.125e-3, grade=.075),
        sampling=dict(kind='uniform', count=2, seed=123,
            variables=[dict(name='left_width', lower=lower, upper=upper)]))
    return LineQuantityStudyDocument(source, schema='sipi.line-quantity-study/2',
        quantity='differential_forward_impedance_real',
        conductor=dict(kind='surface-boundaries',
            conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
            reference=metal(58e6, 0.), ground_thickness=35e-6)).to_dict()

request = YieldDesignDocument([
    dict(name='narrow', cost=2., study=candidate_study(.6e-3, .7e-3)),
    dict(name='wide', cost=1., study=candidate_study(.7e-3, .8e-3))],
    schema='sipi.yield-design/2', cost_unit='relative cost',
    minimum=1., maximum=1000., confidence=.9, minimum_yield=.1)
assert normalize_saved(request.dumps()) == request.dumps()
report = execute_saved(request.dumps(), max_evaluations=4)
assert report['status'] == 'complete'
assert report['result']['status'] == 'selected'
assert report['result']['selected'] == dict(index=1, name='wide', cost=1.)
assert report['result']['unit'] == 'ohm' and report['result']['evaluations'] == 4
assert len(report['result']['candidates']) == 2
```

The total sample count of every candidate must fit the caller's budget before
any field solve. All candidates with valid generated sample vectors are evaluated,
and each source study and assessment is retained. Field failures become unresolved
rows under the [line-yield contract](line_yield.md). Invalid sampling generation,
including overflow, raises without resampling or returning a partial selection.

For m fixed candidates and family confidence c, allocate candidate confidence
at least 1−(1−c)/m. The binary64 value is rounded toward greater confidence when
necessary so exact rational arithmetic on the stored values still satisfies
m*(1−candidate_confidence) <= 1−c. Reject an unrepresentable allocation instead
of weakening the family confidence. Each candidate uses the exact binomial
unresolved-label envelope at its allocated level. Candidate independence is
not required, so shared seeds are allowed; the within-candidate iid assumption
still applies. This is a Bonferroni simultaneous bound for a fixed set, not an
adaptive or continuous optimization guarantee.

Among candidates whose lower confidence bound meets minimum_yield, select the
lowest supplied cost, breaking ties by original input order. `selected` means
that a certified member exists. `none-certified` means every candidate's upper
bound is below the goal; otherwise the result is `undetermined`. A cheaper
unresolved candidate may actually be feasible. Keep its full assessment rather
than treating the chosen member as a proven physical/global optimum.

Shared execution separately reports `incomplete` when any row is unresolved,
even if a candidate is selected. All candidates, rows, units and exact source
inputs remain. Version 2 includes the quantity's unit in the selection report;
version 1 output is unchanged. Confidence covers stated sampling and unknown
labels, not field/mesh/material-fit or manufacturing-distribution error. No
measured production yield or physical accuracy follows from selecting a member.

Validation checks the family failure budget using exact fractions for 1–32
candidates, and candidate intervals by independent finite-binomial inversion
within 1e-12 absolute endpoint error. Tests retain cheaper unknown candidates,
ties, all rejected/undetermined results, zero scalar attenuation, shared normal
seeds, complete/incomplete distinction and pre-field total budgets. Actual
finite-metal paired candidates replay their individual assessments with exact
row/source snapshots and RLGC/Zc agreement within 1e-10. Legacy selection and
line-yield regressions remain included. These are related checks, not a new
full regression, application or Windows acceptance.

```sh
python -m pytest -q tests/sipi/test_lossy_yield_design.py tests/sipi/test_yield_design.py tests/sipi/test_line_yield.py tests/sipi/test_execution.py
```
