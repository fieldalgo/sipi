# Saved acceptance comparison across numerical resolutions

`PanelResolutionYieldDocument` stores an explicit
`sipi.panel-resolution-yield/1` request. The five keys are `schema`, `studies`,
`acceptance`, `confidence` and `minimum_yield`. Supply 2–8 paired study documents
with the same version/current method, physical inputs and iid uniform/normal
sampling. Only the volume mesh and panel controls may differ; duplicated
controls, outer-box changes and changed seeds or sample order are refused.

The comparison retains the [direct finite-resolution meaning](panel_resolution_yield.md):
all passes give pass, all failures give fail, and differing labels or original
failed rows remain unresolved. It does not infer a continuum solution or
bound a shared systematic error. Coated studies use their explicit version 2;
existing versions and nominal yield results retain their original meanings.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.panel_resolution_yield_document import PanelResolutionYieldDocument
from sipi.execution import execute_saved, normalize_saved

source = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.3e-3, gap=.2e-3, substrate_height=.5e-3, eps_r=4.,
         thickness=35e-6, box_width=6e-3, air_height=2e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='uniform', count=2, seed=3, variables=[
        dict(name='width', lower=.28e-3, upper=.32e-3)]))
base = PanelForwardPairStudyDocument(source, conductor={'kind': 'perfect'})
fine = base.to_dict()
for key in ('edge_size', 'far_size', 'grade'):
    fine['study']['mesh'][key] /= 2
fine['panel']['panels_per_edge'] *= 2
request = PanelResolutionYieldDocument(
    [base, PanelForwardPairStudyDocument.from_dict(fine)], acceptance={
    'differential_forward_impedance_real': dict(minimum=90., maximum=130.),
    'common_forward_impedance_real': dict(minimum=20., maximum=60.)},
    confidence=.95, minimum_yield=.9)
assert request.required_evaluations == 4
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=4)
assert output['status'] in ('complete', 'incomplete') and output['error'] is None
assert output['result']['count'] == 2 and output['result']['resolution_count'] == 2
```

`required_evaluations` is samples times resolutions. The full plan must be at
most 10000 whole-line row attempts. Analysis and common execution reject a
smaller caller budget before any field work; failed rows still consume their
planned position. The limit does not bound internal field solves, memory or
time. The common sampling plan is checked for generation failures before the
first field, and every source then keeps its original row order and failure
handling. KeyboardInterrupt propagates.

`studies` returns fresh document snapshots; `dumps`/`loads` preserve the exact
request. Parsing is field-free and accepts no extra keys, ambiguous duplicate
JSON keys, nonfinite numbers or implicit conversion to another current method.
Common execution accepts no characteristic/mode diagnostic override here.

A common result with any unresolved sample has `status='incomplete'` and a
complete retained comparison in `result`; `error` is null because individual
errors remain in their original rows. All planned rows may have been attempted
while classification remains unresolved. With no unresolved rows, status is
`complete`, even if the statistical interval leaves `goal_status='undetermined'`.
Calculation status, classification and a requested yield target are distinct.

Validation checks strict normalization, all source identities, whole-plan
budgets before fields, original row failures at every resolution, interruption,
and exact direct/common replay. The actual coated boundary example regenerates
two samples at four resolutions, retaining one unresolved label and one pass.
Separate coating-transfer, full-characteristic and nonzero-network references
remain active. Prior canonical saved inputs and direct comparison records are
preserved. This request does not automatically select or refine a mesh.

[Coated tolerances](layered_panel_study.md) · [한국어](../../locales/ko/pages/packages/sipi/panel_resolution_yield_document.md)
