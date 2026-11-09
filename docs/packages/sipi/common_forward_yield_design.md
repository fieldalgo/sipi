# Fixed common-current candidates with simultaneous bounds

**English** | [한국어](../../locales/ko/pages/packages/sipi/common_forward_yield_design.md)

Explicit `sipi.yield-design/3` admits fixed `line-quantity-study/3` candidates,
including common-current forward Re(Zcc). Every candidate must use the same
quantity and positive frequency. Versions 1 and 2 retain their previous input
contracts, and the constructor default remains version 1. The
[sampling](common_forward_line_study.md) and [iid interval](common_forward_line_yield.md)
contracts define the physical quantity and unresolved-row interpretation.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.yield_design import YieldDesignDocument
from sipi.execution import normalize_saved, execute_saved

def metal(conductivity, rms):
    return dict(conductivity=conductivity, relative_permeability=1.,
                roughness=dict(kind='hammerstad', rms_m=rms))

def candidate(name, cost, low, high):
    nominal = (low+high)/2
    source = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
        dict(left_width=nominal, right_width=.5e-3, gap=.95e-3-(nominal+.5e-3)/2,
            substrate_height=.5e-3, eps_r=4., tan_delta=.02,
            left_thickness=35e-6, right_thickness=50e-6,
            box_width=24e-3, air_height=10e-3),
        quantity='z_diff_forward', frequency=1e9, materials={}, fixed_pitch_m=.95e-3,
        mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
        sampling=dict(kind='uniform', count=2, seed=17,
            variables=[dict(name='left_width', lower=low, upper=high)]))
    study = LineQuantityStudyDocument(source, schema='sipi.line-quantity-study/3',
        quantity='common_forward_impedance_real',
        conductor=dict(kind='surface-boundaries',
            conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
            reference=metal(58e6, 0.), ground_thickness=35e-6))
    return dict(name=name, cost=cost, study=study.to_dict())

doc = YieldDesignDocument([
    candidate('narrower', 2., .6e-3, .7e-3),
    candidate('wider', 1., .7e-3, .8e-3)],
    schema='sipi.yield-design/3', cost_unit='relative fabrication cost',
    minimum=38., maximum=41., confidence=.9, minimum_yield=.1)
assert normalize_saved(doc.dumps()) == doc.dumps()
result = doc.analyze(max_evaluations=4)
assert result.status == 'selected' and result.selected_index == 1
assert result.unresolved == 0
```

The seven root keys are `schema`, `candidates`, `cost_unit`, `minimum`,
`maximum`, `confidence` and `minimum_yield`. Supply 1–32 candidates, each
containing exactly `name`, `cost` and `study`. Names are unique; costs are
finite and nonnegative in one caller-supplied unit. Costs are not inferred
from geometry or manufacturing. All candidates are fixed before sampling.

The requested family confidence is divided conservatively using Bonferroni.
Each candidate receives the existing Clopper–Pearson unresolved-label
envelope. Rounding must not exceed the exact family failure budget. Within
each candidate, rows must be iid under its stated uniform/normal distribution;
different candidates may use the same seed and need not be independent.

```python
from fractions import Fraction
import json
import numpy as np
assert (1-Fraction(result.candidate_confidence))*2 <= 1-Fraction(.9)
for item in result.candidates:
    assert item.assessment.passed == 2
    low = ((1-result.candidate_confidence)/2)**.5
    np.testing.assert_allclose(item.assessment.confidence_interval, [low, 1.], rtol=0., atol=1e-12)
    assert [row.index for row in item.assessment.study.rows] == [0, 1]
report = execute_saved(doc.dumps(), max_evaluations=4)
assert report['status'] == 'complete' and report['result'] == result.to_dict()
assert report['result']['unit'] == 'ohm'
assert report['result']['evaluations'] == 4
assert report['result']['selected'] == dict(index=1, name='wider', cost=1.)
json.dumps(report, allow_nan=False)
```

Every candidate and original row remains visible. Unknown rows retain the
denominator, phase and available input. A cheaper unknown candidate is not
treated as infeasible. Selection chooses the cheapest certified candidate;
equal costs use input order. With no certified candidate, the result is
`none-certified` only if every candidate is certified below the threshold;
otherwise it is `undetermined`. An outer execution report can be incomplete
because of unknown rows even when a candidate is selected.

The total planned sample count is checked before any field solve. Invalid
sampling generation raises without returning a partial selection; ordinary
per-row solver failures remain unresolved. Limits on counts are not memory
or elapsed-time limits. This is neither adaptive optimization nor a proof of
a continuous/global optimum. The confidence statement assumes the supplied
distribution and excludes numerical, material-fit and model error.

Validation checks exact rational family budgets for 1/2/3/7/32 candidates at
five confidence levels, independent finite-binomial inversion within 1e-12,
unknown/tie/no-selection cases, prior-version outputs and strict admission.
Two physical asymmetric candidates, each with two width samples, replay
direct assessments and saved reports exactly, with full RLGC within 1e-10.
All 96 prior canonical inputs remain unchanged. The earlier three-width
mesh/finite-domain qualification is preserved; it does not establish
convergence for every possible random sample. No measured production yield,
new platform or deployment acceptance follows from these bounds.
