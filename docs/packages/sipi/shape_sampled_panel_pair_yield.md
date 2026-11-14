# Joint acceptance across shape-current frequency grids

[한국어](../../locales/ko/pages/packages/sipi/shape_sampled_panel_pair_yield.md) ·
[Frequency-grid studies](shape_sampled_panel_pair_study.md) · [Original interval contract](sampled_panel_pair_yield.md)

`ShapeSampledPanelForwardPairYieldDocument` saves one joint event per manufactured
row: **all** differential and common forward-impedance limits at **every requested
frequency** must pass. Its strict `sipi.shape-sampled-panel-forward-pair-yield/1`
keys are `schema`, `study`, `acceptance`, `confidence`, `minimum_yield`.
The nested shape-grid study/1 must use iid uniform or normal samples; sweep and
corners are rejected. Bulk/fixed-coated materials and original method choices stay
explicit. Both named quantities require minimum/maximum arrays matching the grid,
with at least one bound per frequency. Scalar broadcasting is rejected.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.shape_sampled_panel_pair_study import ShapeSampledPanelForwardPairStudyDocument
from sipi.execution_request import SavedExecutionRequest

source = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.5e-3, gap=.3e-3, substrate_height=.2e-3, eps_r=1.,
         thickness=35e-6, air_height=3e-3, box_width=8e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='uniform', count=4, seed=123,
        variables=[dict(name='width', lower=.45e-3, upper=.55e-3)]))
panel = SampledPanelForwardPairStudyDocument(source, conductor={'kind':'perfect'},
    frequencies=[1e9, 2e9, 4e9], panels_per_edge=16,
    ground_modes=512, interpolation_degree=16)
document = ShapeSampledPanelForwardPairStudyDocument(panel, step_fraction=1e-3)
from sipi.shape_sampled_panel_pair_yield import ShapeSampledPanelForwardPairYieldDocument

limits = {
    'differential_forward_impedance_real': {'minimum': [65.,65.,65.], 'maximum': [75.,75.,75.]},
    'common_forward_impedance_real': {'minimum': [21.,21.,21.], 'maximum': [26.,26.,26.]},
}
yield_document = ShapeSampledPanelForwardPairYieldDocument(document, acceptance=limits,
    confidence=.95, minimum_yield=.8)
request = SavedExecutionRequest(yield_document.dumps(), max_evaluations=4)
assert ShapeSampledPanelForwardPairYieldDocument.loads(yield_document.dumps()).dumps() == yield_document.dumps()
# receipt = request.run()  # Four original rows, each evaluated on the complete grid.
```

Each original row remains one Bernoulli trial regardless of the number of frequency
points. Within-row variable, frequency and quantity correlations are preserved;
the joint probability is not a product of marginal pass fractions. An atomic grid
failure remains one unresolved row in the original denominator. The existing exact
Clopper–Pearson interval envelopes every possible assignment of unknown labels.
Inclusive and one-sided bounds and pass/fail/undetermined target decisions retain
the original statistical contract.

`assess_shape_sampled_panel_pair_yield` performs no field solves and retains the
original study object. A statistical view reuses the existing row/grid validator
without converting or recomputing its current method. Reports preserve complete
current records and partial failure details. Manually assembled rows are not
independently authenticated fields. Common execution returns `incomplete` when
any row is unresolved; saved requests, records and projects restore without fields.
Whole-row budgets are checked before extraction and interrupts propagate.

Independent binomial-tail inversion and SciPy exact intervals check counts,
unknown completions and bounds. Tests distinguish the full joint event from its
marginals and verify that 9 or 64 frequencies do not inflate the manufacturing
sample count. Actual four-row bulk/coated iid studies on a three-point Debye grid
add independent material/network checks and complete/partial receipt replay.

The result describes only the stated finite grid and distribution. It does not
bound values between frequency points, outer-domain or mesh error, fitted material
uncertainty, adaptive selection or measured production yield. The previously
unqualified small-domain examples remain unqualified even when their statistics
complete successfully. No existing yield schema implicitly selects this method.
