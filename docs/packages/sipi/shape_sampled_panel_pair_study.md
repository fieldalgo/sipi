# Shape-current manufacturing samples across a finite frequency grid

[한국어](../../locales/ko/pages/packages/sipi/shape_sampled_panel_pair_study.md) ·
[Single-frequency studies](shape_panel_pair_study.md) · [Original frequency-grid contract](sampled_panel_pair_study.md)

`ShapeSampledPanelForwardPairStudyDocument` explicitly uses capacitance-shape
currents while keeping one manufactured geometry and material sample across the
entire frequency grid. Its strict `sipi.shape-sampled-panel-forward-pair-study/1`
keys are `schema`, `study`, `step_fraction`. The nested sampled-panel study/1 or
/2 retains bulk or fixed-coated boundaries. Original schemas retain their method.

The grid contains 2..64 strictly increasing positive frequencies and starts at
the source study's material-evaluation frequency. Correlation, sample order,
duplicates, fixed pitch and material leaves remain unchanged. The single current
batch for a geometry is reused across frequencies; dielectric and metal laws are
evaluated at every requested point. This does not assume frequency-independent
RLGC or that differential/common launches are independent modes.

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
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='width', lower=.45e-3, upper=.55e-3)]))
panel = SampledPanelForwardPairStudyDocument(source, conductor={'kind':'perfect'},
    frequencies=[1e9, 2e9, 4e9], panels_per_edge=16,
    ground_modes=512, interpolation_degree=16)
document = ShapeSampledPanelForwardPairStudyDocument(panel, step_fraction=1e-3)
request = SavedExecutionRequest(document.dumps(), max_evaluations=3)
assert ShapeSampledPanelForwardPairStudyDocument.loads(document.dumps()).dumps() == document.dumps()
# receipt = request.run()  # Three manufactured rows, each with all three frequencies.
```

A budget counts full line batches, one per original manufacturing row; it does
not count each frequency as an independent manufactured sample or each internal
panel solve. The entire row count must fit the integer 2..10000 budget before
fields. Mesh/panel controls and relative shape step remain fixed. Neither a
frequency interpolation guarantee nor automatic numerical qualification is implied.

Nominal geometry and full-grid material admission are field-free. Invalid sampled
geometry/materials/offsets and failed extraction/diagnostics remain atomic failed
rows. Failure at one frequency invalidates that entire row; later rows still run.
No rows or frequency entries are silently dropped. Per-frequency descriptive
summaries exist only when all rows complete. Every available complete current
record is retained, including after a diagnostic failure. Shape-line errors retain
the original staged partial evidence in `cause_details`.

Common execution preserves complete/incomplete results, exact input and all rows.
Saved records and projects restore without field work. Existing single-frequency
and paired-yield schemas do not implicitly adopt this grid or method. The finite
grid cannot establish extrema between points, continuous-band compliance, production
yield or measured material accuracy.

## Validation scope

Independent modal grids/statistics, duplicated/correlated samples, fixed pitch,
material leaves, atomic failures, offsets, budgets, strict JSON and receipts are
checked alongside original sampled studies and yield consumers. Actual four-corner
bulk and coated studies at 1/2/4 GHz use a uniform scalar Debye law: complex C scales
with its independently evaluated permittivity, G follows dielectric loss, and
external LC, metal transfer and full four-port networks match independent identities.
A selected row in each material is also solved separately at all three frequencies.
Current records are unchanged by the dielectric metadata and frequency grid.

These finite-domain cases retain the small-domain limitation documented in the
single-frequency study. Their material/network identities and transport checks do
not qualify the original outer domain, small mutual entries or absolute accuracy.
