# Joint acceptance of shape-current manufacturing samples

[한국어](../../locales/ko/pages/packages/sipi/shape_panel_pair_yield.md) ·
[Shape-current studies](shape_panel_pair_study.md) · [Statistical contract](panel_pair_yield.md)

`ShapePanelForwardPairYieldDocument` saves the joint event that both differential
and common forward-impedance real parts meet their inclusive limits. The strict
`sipi.shape-panel-forward-pair-yield/1` keys are `schema`, `study`, `acceptance`,
`confidence`, `minimum_yield`. `study` must be an explicit shape-current study/1,
using iid uniform or normal samples; sweep and corners are rejected. The nested
bulk/fixed-coated conductor selection remains unchanged. Existing yield documents
do not silently select this current method.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.shape_panel_pair_study import ShapePanelForwardPairStudyDocument
from sipi.execution_request import SavedExecutionRequest

source = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.5e-3, gap=.3e-3, substrate_height=.2e-3, eps_r=1.,
         thickness=35e-6, air_height=3e-3, box_width=8e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='uniform', count=4, seed=123,
        variables=[dict(name='width', lower=.45e-3, upper=.55e-3)]))
panel = PanelForwardPairStudyDocument(source, conductor={'kind':'perfect'},
    panels_per_edge=16, ground_modes=512, interpolation_degree=16)
document = ShapePanelForwardPairStudyDocument(panel, step_fraction=1e-3)
from sipi.shape_panel_pair_yield import ShapePanelForwardPairYieldDocument

limits = {
    'differential_forward_impedance_real': {'minimum': 124., 'maximum': 130.},
    'common_forward_impedance_real': {'minimum': 41., 'maximum': 43.},
}
yield_document = ShapePanelForwardPairYieldDocument(document, acceptance=limits,
    confidence=.95, minimum_yield=.8)
request = SavedExecutionRequest(yield_document.dumps(), max_evaluations=4)
assert ShapePanelForwardPairYieldDocument.loads(yield_document.dumps()).dumps() == yield_document.dumps()
# receipt = request.run()  # Runs the four requested field extractions.
```

One original row is one joint event, preserving within-row variable correlation.
The joint pass fraction is not the product of two marginal pass fractions. Every
failed extraction or diagnostic remains unresolved in the original denominator.
The sample fraction is bounded by passed/count and (passed+unresolved)/count.
The existing Clopper–Pearson interval envelopes all assignments of unknown labels;
confidence and goal decisions have the same meaning as the original paired-yield
contract. Bounds may be one-sided. A goal is pass only when its lower confidence
bound reaches the target, fail when its upper bound is below the target, and
undetermined otherwise. A missing target is not requested.

`assess_shape_panel_pair_yield(study, acceptance=limits)` performs no field work.
It retains the original Python study object and checks original sample vectors,
order, count, iid source and row status through the existing statistical validator.
The internal statistical view shares the original rows and does not recompute or
convert their current method. Manually built rows are not authenticated numerical
evidence. Reports retain every complete current record and partial `cause_details`.

Common execution returns `incomplete` when any row is unresolved, without dropping
its input, error or current evidence. Saved records/projects restore without fields.
The complete sample count must fit the caller budget before solving. Interrupts
propagate. Parsing and criteria admission are field-free; source and acceptance
snapshots are independent of later mutable caller dictionaries.

## Limits and validation

This interval describes the stated iid distribution of finite-domain calculations.
It excludes discretization, outer-domain, material-model and manufacturing-model
error, measurement uncertainty, parameter fitting and adaptive design selection.
In particular, the small-domain counterexamples documented in the shape study
remain unqualified; successful statistics do not make their fields converged.
The result is not measured production yield.

Checks include independent finite binomial-tail inversion, SciPy exact intervals,
all unknown completions, inclusive joint truth tables, malformed/reordered rows,
budgets and receipt restoration. Four actual iid geometry samples each for bulk
and coated conductors additionally check uniform dielectric identities, independent
metal transfer and four-port networks; complete and injected partial-failure
receipts retain their original current evidence. These selected cases do not
establish numerical accuracy for every allowed input or another platform.
