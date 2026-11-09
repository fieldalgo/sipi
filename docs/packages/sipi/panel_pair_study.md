# Paired forward-impedance sampling with explicit panel currents

[한국어](../../locales/ko/pages/packages/sipi/panel_pair_study.md) ·
[Panel lines](panel_line.md) · [Saved pair goals](panel_pair_goal_document.md) ·
[Joint acceptance](panel_pair_yield.md)

`PanelForwardPairStudyDocument` calculates two quantities from **one extraction
per sample**: `differential_forward_impedance_real` and
`common_forward_impedance_real`, in that order, in ohms. They are Re(Zdd) for
the Ic=0 launch and Re(Zcc) for the Id=0 launch of the complete complex forward
characteristic matrix in power-dual mixed coordinates. Asymmetric cross terms
remain present; these launches are not asserted to be independent modes.

The strict `sipi.panel-forward-pair-study/1` request has exactly four root keys:
`schema`, `study`, `conductor`, `panel`. The nested paired impedance study/3 or
/4 supplies a fixed positive frequency, ordered geometry/material variables,
sampling and constraints. Its `z_diff_forward` label selects source inputs;
the old quasi-static study is not executed. Fixed pitch, material leaves,
seeds and existing sweep/corners/uniform/correlated-normal rules retain their
meaning. Existing study schemas keep their calculation method.

`panel` contains exactly `panels_per_edge`, `ground_modes` and
`interpolation_degree`. The [panel line restrictions](panel_line.md) apply,
including positive-thickness rectangles, bottom ground with open top/sides,
and supported conductor laws. Unsupported input is rejected without switching
methods. Sampling does not require admission for an unrequested refinement.

## Example

All lengths are metres. This small perfect-conductor example samples width at
three points through the common saved engine entry point.

```python
import json
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.execution import normalize_saved, execute_saved

study = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.3e-3, gap=.2e-3, substrate_height=.5e-3, eps_r=4.,
         thickness=35e-6, air_height=2e-3, box_width=6e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='width', lower=.28e-3, upper=.32e-3)]))
document = PanelForwardPairStudyDocument(study, conductor={'kind': 'perfect'},
    panels_per_edge=32, ground_modes=512, interpolation_degree=10)
text = document.dumps()
assert normalize_saved(text) == text
assert PanelForwardPairStudyDocument.loads(text).dumps() == text
output = execute_saved(text, max_evaluations=3)
assert output['status'] == 'complete'
assert output['input'] == document.to_dict()
assert output['result']['count'] == 3 and output['result']['failed'] == 0
assert output['result']['quantities'] == [
    'differential_forward_impedance_real', 'common_forward_impedance_real']
assert all(len(row['values_ohm']) == 2 for row in output['result']['rows'])
json.dumps(output, allow_nan=False)
```

## Attempts, failures and summaries

Parsing normalizes a deep copy and checks nominal input without field work.
It does not prove every sample valid. `samples()` returns the original ordered
samples. `analyze(max_evaluations=128)` generates all samples and checks their
count against an integer budget of 2..10000 before solving. Invalid/overflowing
generation or insufficient budget raises before fields. Each row is then
attempted once, including duplicates and all rows following a failure. No
samples are clipped, resampled, dropped or reweighted.

Rows retain index, sample values, resolved parameters, material evaluation
and complete panel-line input when available. Failures retain the original
exception type/message and phase: `parameters`, `materials`, `input`,
`extraction` or `diagnostic`. An extracted result remains on the Python row
even if its diagnostic fails. Both impedances succeed or fail together;
failed pairs have `values_ohm=null`.

The Python result exposes `rows`, `failed`, `variable_names`, `input_json` and
immutable nested `summary` mappings. `to_dict()` returns a JSON-compatible
report without raw field/matrix objects. If every row succeeds, each quantity
has minimum, maximum, mean, sample standard deviation and linearly interpolated
5th/95th percentiles. **Any failed row makes the whole summary null.** These
are descriptive statistics, not yield confidence bounds or guaranteed extrema.
Older single-quantity yield inputs do not implicitly accept this paired request.

Common execution keeps the entire request and returns `status='incomplete'`
when any row fails. Original row errors remain in `result`; the top-level
`error` is null. Malformed requests raise, rather than becoming incomplete
sample sets. Input-size, unsupported diagnostic and evaluation controls apply
before solving. Callers own cancellation, process isolation and time/memory
budgets.

## Numerical scope and validation

Resolved nominal mesh and panel settings stay fixed across rows. This is not
a reused geometric mesh or automatic per-row convergence. The same frequency,
ordered signal names and diagnostic coordinates must survive extraction.
Nonfinite, wrong-shaped or nonpositive impedance results fail the whole pair.
Original geometry, resource and skin-depth gates remain unchanged.

Tests use independent coupled modal formulas and descriptive statistics,
including correlated invalid samples, duplicates, material leaves and fixed
pitch. Four heterogeneous asymmetric geometry corners are compared against
balanced 2N eigenspaces within relative 1e-10; this reuses extracted RLGC and
is not an independent geometry solve. Four perfectly correlated uniform
complex-dielectric samples satisfy C=eps*C0, R=0 and the analytic full matrix
`sqrt(mu0*epsilon0/complex_eps)*inverse(C0)` within relative 1e-10.

A separate recorded study qualifies the first and last geometry corners with
joint mesh/panel refinement and three outer domains: relative changes at most
.005 and decreasing successive absolute outer changes for both quantities.
This finite check does not cover every sample or the continuous parameter
box. Continuous-band acceptance, production yield, global optimization,
measured accuracy, browser/Worker integration and Windows qualification remain
separate.
