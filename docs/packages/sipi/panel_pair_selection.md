# Fixed candidates for paired-impedance yield

[한국어](../../locales/ko/pages/packages/sipi/panel_pair_selection.md) ·
[Joint acceptance](panel_pair_yield.md) · [Paired sampling](panel_pair_study.md)

`PanelForwardPairSelectionDocument` compares a **predeclared finite set** of
designs. It selects the lowest-cost candidate whose joint yield lower bound
certifies the requested target. Both impedance limits must hold on the same
row, using [joint acceptance](panel_pair_yield.md). Candidate outcomes may be
correlated; no independence between candidates or between impedances is assumed.

The strict `sipi.panel-forward-pair-selection/1` root has `schema`, `candidates`,
`cost_unit`, `acceptance`, `confidence`, `minimum_yield`. The last four describe
one common cost unit, the two named inclusive ohm limits, family confidence and
a mandatory yield target. Limits and probabilities follow the joint-yield
contract. A zero target is allowed and is a trivial probability requirement.

`candidates` is a list of 1..32 entries, each exactly `{name, cost, study}`.
Names are unique, printable single-line text of 1..128 characters, without
outer whitespace. Costs are finite nonnegative numbers supplied by the caller;
no cost model or currency conversion runs. `study` is a canonical
`sipi.panel-forward-pair-study/1` request with iid uniform or normal sampling.
All candidates must have the same positive frequency. Their other explicit
geometry, material, distribution and panel settings may differ and are retained.
Different candidates or identical studies with different names are never
deduplicated, and still count toward the family confidence allocation.

## Example

This small perfect-conductor example compares two fixed substrate heights with
four width samples each. Costs and broad limits are illustrative. A .3 target
demonstrates the interface; four samples per candidate do not establish a 90%
lower yield bound at 95% family confidence. Lengths are metres and limits ohms.

```python
import json
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.panel_pair_selection import PanelForwardPairSelectionDocument
from sipi.execution import normalize_saved, execute_saved

study = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.3e-3, gap=.2e-3, substrate_height=.5e-3, eps_r=4.,
         thickness=35e-6, air_height=2e-3, box_width=6e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='uniform', count=4, seed=123,
        variables=[dict(name='width', lower=.28e-3, upper=.32e-3)]))
first = PanelForwardPairStudyDocument(study, conductor={'kind': 'perfect'}).to_dict()
second = json.loads(json.dumps(first))
second['study']['parameters']['substrate_height'] = .52e-3
document = PanelForwardPairSelectionDocument([
    dict(name='first', cost=1., study=first),
    dict(name='second', cost=.8, study=second)], cost_unit='relative-cost',
    acceptance={
        'differential_forward_impedance_real': dict(minimum=90., maximum=140.),
        'common_forward_impedance_real': dict(minimum=40., maximum=80.)},
    confidence=.95, minimum_yield=.3)
text = document.dumps()
assert normalize_saved(text) == text
assert PanelForwardPairSelectionDocument.loads(text).dumps() == text
output = execute_saved(text, max_evaluations=8)
assert output['status'] == 'complete'
assert output['input'] == document.to_dict()
assert output['result']['evaluations'] == 8
assert len(output['result']['candidates']) == 2
assert output['result']['status'] in ('selected', 'none-certified', 'undetermined')
json.dumps(output, allow_nan=False)
```

## Simultaneous inference and selection

For K fixed candidates and family confidence c, each joint event uses at least
`1-(1-c)/K` confidence. Exact rational arithmetic and conservative float rounding
ensure that the sum of candidate error budgets does not exceed `1-c`. An
unrepresentable confidence near one is rejected. There is no additional factor
of two for the two quantities: each row already represents one AND event.
The existing unresolved-label Clopper–Pearson envelope is applied per candidate.

Every candidate and row is retained. Among candidates with `goal_status='pass'`,
selection minimizes supplied cost, resolving ties by original index. The result
is `selected` if a certified member exists, `none-certified` if every candidate
has `goal_status='fail'`, and `undetermined` otherwise. A cheaper unresolved
candidate might actually be feasible; selecting a certified member does not
exclude that possibility or prove a global/continuous optimum.

Common execution returns `incomplete` if any row in any candidate is unresolved,
even when the result has selected a certified member. This also holds for the
trivial zero target. Successful evaluations that miss the limits can produce a
complete execution with `none-certified`. Row errors stay in their candidate
assessments and top-level `error` is null. Malformed controls and inputs raise.

The direct result exposes `input_json`, a `candidates` tuple,
`candidate_confidence`, `selected_index`, `status` and `unresolved`. Each candidate
retains its name, cost and complete joint assessment. `to_dict()` includes both
quantities, unit, common limits, supplied cost unit, family/candidate confidence,
target, selected member, every candidate input and every original row.

## Budget, numerical scope and validation

`analyze(max_evaluations=128)` checks the sum of all declared sample counts against
an integer budget of 2..10000 before field work. It also generates and validates
every candidate's samples before starting the first field calculation. A later
sampling overflow therefore cannot erase already computed earlier candidates.
Invalid but finite geometries remain ordinary unresolved rows when attempted.

All candidates and rows are then attempted in order, including failures,
duplicates and candidates after an already certified member. There is no
resampling, early stopping, adaptive candidate generation or hidden optimizer.
`evaluations` counts original attempted rows, including those that fail before
extraction; it is not a count of successful field solves. Each study uses its
explicit settings. Its geometry/skin-depth/resource gates and limited convergence
qualification remain unchanged. Callers own cancellation, isolation and elapsed
time/memory limits; input-size and unsupported diagnostics are checked before work.

Tests check the exact family error budget for all supported candidate counts,
independent finite-binomial bounds, ties, cheaper unknown candidates, unequal
sample counts, preflight overflow, total budget and failures followed by later
candidates. A separate two-candidate physical case uses eight uniform rows,
independent balanced 2N matrices within relative 1e-10, independently derived
joint labels and exact-binomial intervals within absolute 1e-12. It selects the
lower-cost certified member at the explicitly illustrative .3 target.

These are bounds for fixed stated iid models. They exclude measured production
yield, field/model/distribution error, inference after adaptive selection,
continuous-band guarantees, browser/Worker integration and Windows qualification.
