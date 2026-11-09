# Joint acceptance of paired forward impedances

[한국어](../../locales/ko/pages/packages/sipi/panel_pair_yield.md) ·
[Paired sampling](panel_pair_study.md)

`PanelForwardPairYieldDocument` assesses **both impedance limits on the same
sample**. A completed row passes only if its real differential and common
forward impedances both meet their inclusive limits. Failure of either limit
is one failed joint event. Marginal pass fractions are never multiplied:
correlation between the two responses is retained.

The strict `sipi.panel-forward-pair-yield/1` request has root keys `schema`,
`study`, `acceptance`, `confidence`, `minimum_yield`. `study` is a complete
`sipi.panel-forward-pair-study/1` request. Only iid `uniform` and `normal`
sampling is admitted. Correlation among variables within a normal row is
allowed; sweep/corners cannot be treated as iid yield experiments.

`acceptance` has exactly `differential_forward_impedance_real` and
`common_forward_impedance_real`. Each contains exactly `minimum` and `maximum`
in ohms. One bound may be null; at least one is required for each quantity.
Bounds must be finite nonnegative numbers with minimum no greater than maximum.
The underlying completed impedance values remain strictly positive. Confidence
must be strictly between zero and one at float precision; `minimum_yield` is
null or a probability in [0, 1]. Boolean values are not numeric limits.

## Example

This small perfect-conductor example uses four iid width samples, a fixed seed
and illustrative engineering limits. Four observations cannot establish a
90% lower yield bound at 95% confidence, even if all four meet both limits.
Lengths are metres; limits are ohms.

```python
import json
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.panel_pair_yield import PanelForwardPairYieldDocument
from sipi.execution import normalize_saved, execute_saved

study = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.3e-3, gap=.2e-3, substrate_height=.5e-3, eps_r=4.,
         thickness=35e-6, air_height=2e-3, box_width=6e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='uniform', count=4, seed=123,
        variables=[dict(name='width', lower=.28e-3, upper=.32e-3)]))
paired = PanelForwardPairStudyDocument(study, conductor={'kind': 'perfect'})
document = PanelForwardPairYieldDocument(paired, acceptance={
    'differential_forward_impedance_real': dict(minimum=90., maximum=140.),
    'common_forward_impedance_real': dict(minimum=40., maximum=80.)},
    confidence=.95, minimum_yield=.9)
text = document.dumps()
assert normalize_saved(text) == text
assert PanelForwardPairYieldDocument.loads(text).dumps() == text
output = execute_saved(text, max_evaluations=4)
assert output['status'] == 'complete'
assert output['input'] == document.to_dict()
assert output['result']['count'] == 4 and output['result']['unresolved'] == 0
assert output['result']['goal_status'] in ('fail', 'undetermined')
json.dumps(output, allow_nan=False)
```

## Unresolved rows and confidence

Each generated sample is attempted once by the paired study. An extraction or
diagnostic failure makes the whole pair `unresolved`; failures in parameters,
material evaluation or input construction do the same. Every original row,
sample vector, available input and error remains in the result and denominator.
No failed samples are discarded, replaced or assigned invented responses.

For n planned samples, p definite passes and u unresolved rows, the possible
sample fraction is [p/n, (p+u)/n]. The confidence interval is the conservative
envelope of equal-tailed Clopper–Pearson intervals for all possible unresolved
labels: use p successes for its lower endpoint and p+u for its upper endpoint.
This is one joint Bernoulli event, so there is no assumption of independence
between the two impedance quantities or multiplication of marginal intervals.
All-unresolved rows produce [0, 1].

`goal_status` is `pass` if the lower confidence bound reaches `minimum_yield`,
`fail` if the upper bound is below it, `undetermined` otherwise, or
`not-requested` when no target was supplied. Execution completeness is separate:
common execution returns `incomplete` whenever unresolved rows exist, even if
the trivial requested minimum yield of zero has `goal_status='pass'`.
Row errors are in `result`, with top-level `error=null`. Malformed requests,
unsupported diagnostics, oversized input and insufficient budgets raise before
field work. Callers manage cancellation, isolation and time/memory limits.

The direct `assess_panel_pair_yield(result, acceptance=..., ...)` API can assess
a previously computed paired study without rerunning fields. It validates the
source schema, iid kind, count, variable order, exact regenerated sample
vectors, row indices and complete/unresolved row state. These structural checks
do not authenticate manually constructed field results. The returned assessment
retains its source study and immutable acceptance limits. `to_dict()` preserves
both quantities, the sampling model, classifications, counts, bounds and rows;
raw field objects remain available through the direct Python study.

## Scope and evidence

This is finite iid inference for one fixed stated geometry/material
distribution and fixed limits. It excludes mesh/solver error, uncertainty in
the material model or manufacturing distribution, measured production yield,
continuous-band acceptance and inference after adaptive candidate selection.
The paired study's field restrictions and finite convergence scope still apply.

Independent tests invert finite binomial tails and compare SciPy's exact
binomial intervals, including endpoint counts and every completion of small
unresolved sets. Joint truth tables include equal marginal pass fractions with
different joint counts. Physical uniform geometry samples are checked against
balanced 2N eigenspaces, and correlated uniform complex-material samples against
the analytic characteristic matrix. Joint labels and confidence intervals are
then computed independently. These checks do not establish measured accuracy,
browser/Worker integration or Windows qualification.
