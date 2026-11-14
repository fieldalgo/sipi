# Fixed coated candidates and yield-based selection

Explicit `sipi.yield-design/4` accepts the fixed-coating study/4 contract.
Declare all candidates, their costs in a common unit and their distributions
before solving. The existing simultaneous confidence method and selection rule
remain unchanged; earlier selection versions keep their accepted study versions.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.yield_design import YieldDesignDocument
from sipi.execution import normalize_saved

metal = dict(kind='layered', conductivity=58e6, relative_permeability=1.,
    coatings=[dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.)])
candidates = []
for name, cost, low, high in [('first', 2., .45e-3, .55e-3),
                               ('second', 1., .5e-3, .6e-3)]:
    source = ImpedanceStudyDocument('stripline',
        dict(width=.5e-3, plane_spacing=1e-3, thickness=50e-6,
             eps_r=4., tan_delta=.02, box_width=4e-3),
        quantity='z0', frequency=1e9, materials={},
        sampling=dict(kind='uniform', count=4, seed=123,
            variables=[dict(name='width', lower=low, upper=high)]))
    study = LineQuantityStudyDocument(source, quantity='impedance_real',
        conductor=dict(kind='surface-boundaries', conductors={'signal': metal},
                       reference=metal, ground_thickness=35e-6),
        schema='sipi.line-quantity-study/4')
    candidates.append(dict(name=name, cost=cost, study=study.to_dict()))
design = YieldDesignDocument(candidates, cost_unit='relative',
    minimum=40., maximum=60., minimum_yield=.9, confidence=.95,
    schema='sipi.yield-design/4')
assert normalize_saved(design.dumps()) == design.dumps()
```

Call `design.analyze(max_evaluations=8)` to attempt all eight samples in this
example. Four samples are only a small demonstration and need not certify the
requested yield. The total sample budget is checked before the first field solve.
Candidates must share the same quantity and positive frequency. Coating
parameters are fixed within each candidate; candidate materials may differ.

Every unresolved sample remains in its original row and denominator. A cheaper
candidate with unresolved yield is retained even if another candidate passes.
The result selects the lowest-cost certified member, breaking equal-cost ties
by input order. It does not claim the selected member is cheaper than every
potentially feasible unresolved member. Common execution reports `incomplete`
when sample failures remain, including when the selection itself is `selected`.

Bonferroni-adjusted Clopper–Pearson intervals cover the fixed family under the
stated iid sampling assumptions; candidates need not be independent. The
intervals do not account for field discretization, uncertain input distributions
or model error. This is finite candidate enumeration, not continuous/global
optimization, measured manufacturing yield or an automatic coating fit.

Validation retains real skin/core failures in scalar impedance, attenuation and
paired forward differential/common candidates, compares direct assessments and
independent finite-binomial interval bounds, and checks unchanged prior candidate
ordering/units. [Coating model limits](layered_metal.md) and separate mesh/outer
validation still apply.

[한국어](../../locales/ko/pages/packages/sipi/layered_selection.md)
