# Common-current iid acceptance bounds

**English** | [한국어](../../locales/ko/pages/packages/sipi/common_forward_line_yield.md)

Explicit `sipi.line-quantity-yield/2` accepts a fixed random
`sipi.line-quantity-study/3`, including `common_forward_impedance_real`.
The direct `assess_line_yield` API also accepts this study version.
The saved constructor still defaults to `/1`, which accepts only study `/1`
or `/2`. Fixed-candidate selection `/2` keeps that same previous boundary.

The physical quantity is Re(Zcc) in ohms, with Vc=(V1+V2)/2, Ic=I1+I2
and launch Id=(I1-I2)/2=0. Full asymmetric coupling is retained; neither
downstream Id=0 nor an independent common eigenmode is assumed. See the
[sampling contract](common_forward_line_study.md) for geometry, material,
fixed pitch, mesh and conductor constraints.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.line_yield import LineQuantityYieldDocument
from sipi.execution import normalize_saved, execute_saved

def metal(conductivity, rms):
    return dict(conductivity=conductivity, relative_permeability=1.,
                roughness=dict(kind='hammerstad', rms_m=rms))

source = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3,
        substrate_height=.5e-3, eps_r=4., tan_delta=.02,
        left_thickness=35e-6, right_thickness=50e-6,
        air_height=10e-3, box_width=24e-3),
    quantity='z_diff_forward', frequency=1e9, materials={}, fixed_pitch_m=.95e-3,
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='uniform', count=4, seed=17,
        variables=[dict(name='left_width', lower=.6e-3, upper=.8e-3)]))
study = LineQuantityStudyDocument(source, schema='sipi.line-quantity-study/3',
    quantity='common_forward_impedance_real',
    conductor=dict(kind='surface-boundaries',
        conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
        reference=metal(58e6, 0.), ground_thickness=35e-6))
doc = LineQuantityYieldDocument(study, schema='sipi.line-quantity-yield/2',
    minimum=38., maximum=41., confidence=.95, minimum_yield=.5)
assert normalize_saved(doc.dumps()) == doc.dumps()
result = doc.analyze(max_evaluations=4)
assert result.passed == 4 and result.failed == result.unresolved == 0
assert [row.index for row in result.study.rows] == list(range(4))
assert result.goal_status == 'undetermined'
```

The six root keys are `schema`, `study`, `minimum`, `maximum`, `confidence`
and `minimum_yield`. Limits are inclusive. Uniform or correlated-normal
rows are treated as iid draws from the stated distribution; correlation
between variables within a row is allowed. Sweep and corner samples reject
confidence inference. No distribution is inferred from manufacturing data.

Every original row, its order and exact regenerated sample vector are checked.
Failed rows remain unresolved and stay in the denominator. If p rows pass,
u remain unresolved and n were planned, sample-fraction bounds are
[p/n, (p+u)/n]. The confidence interval uses the lower Clopper–Pearson endpoint
for p successes and the upper endpoint for p+u successes. It therefore covers
every possible assignment of unresolved labels without dropping or resampling.
Structural checks do not authenticate manually constructed solver results.

```python
import json
import numpy as np
np.testing.assert_allclose(result.confidence_interval, [.025**(1/4), 1.], rtol=0., atol=1e-12)
assert result.sample_fraction_bounds == (1., 1.)
report = execute_saved(doc.dumps(), max_evaluations=4)
assert report['status'] == 'complete' and report['result'] == result.to_dict()
assert report['result']['unit'] == 'ohm'
assert report['result']['quantity'] == 'common_forward_impedance_real'
assert report['result']['scope'] == 'iid-stated-distribution-not-measured-production-yield'
json.dumps(report, allow_nan=False)
```

All four samples pass in this example, but four observations cannot certify
the requested 50% population threshold at 95% confidence. A complete analysis
can therefore have an undetermined goal. Neither outcome is a measured
production-yield statement. Mesh, material-fit, model and distribution errors
are outside the interval. The sample budget rejects before field work; it is
not a bound on memory or elapsed time.

Validation compares interval endpoints with independent finite-binomial-sum
inversion within 1e-12, including zero/all successes and every unresolved-label
assignment. Seeded common-current physical rows replay saved/direct full RLGC
within 1e-10 and reports exactly. Correlated invalid geometry retains three
unknown rows out of eight and continues through all later samples. Row-index,
ordering, sample-vector, failure, strict-input and budget invariants are checked.

The numerical extraction and probability formulas are reused. Existing scalar
and differential reports and 95 canonical saved inputs remain unchanged.
Source and exact installed-wheel checks include English/Korean examples.
The earlier three-width mesh and finite-domain qualification remains limited
to those tested conditions; this statistical connection adds no per-random-row
convergence guarantee, measured accuracy, platform or deployment acceptance.
