# Saved finite-grid resolution acceptance

`SampledPanelResolutionYieldDocument` saves an explicit comparison using
`sipi.sampled-panel-resolution-yield/1`. The five required keys are `schema`,
`studies`, `acceptance`, `confidence` and `minimum_yield`. The 2–8 nested studies
must be explicit sampled panel pair study version 1 or 2, all of the same version.
Geometry, fixed metal laws, materials, ordered frequency grid, constraints and
sampling must agree; only distinct mesh and panel settings may differ.

Each quantity requires minimum/maximum arrays with one entry per frequency.
Each frequency needs at least one finite bound. Only iid uniform/normal sampling
is accepted. Normalization validates nested inputs without fields. No old saved
input is implicitly upgraded or given new statistical meaning.

`required_evaluations` is the number of manufacturing samples times the number
of supplied resolutions, capped at 10000. Each attempted row is a whole-frequency
batch, including a failed batch. This is not a count of internal field solves or
a time bound. An insufficient caller budget or a failure generating the sample
plan rejects before any field calculation. Interrupts propagate.

The example uses two samples and two resolutions. The shared executor explicitly
performs the four planned batches and returns the original request with the
comparison. A small demonstration sample does not establish a high yield.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.sampled_panel_resolution_yield_document import SampledPanelResolutionYieldDocument
from sipi.execution import execute_saved, normalize_saved

source = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.3e-3, gap=.2e-3, substrate_height=.5e-3, eps_r=4.,
         thickness=35e-6, box_width=6e-3, air_height=2e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='uniform', count=2, seed=3, variables=[
        dict(name='width', lower=.28e-3, upper=.32e-3)]))
base = SampledPanelForwardPairStudyDocument(source, conductor={'kind': 'perfect'}, frequencies=[1e9, 2e9, 4e9])
fine = base.to_dict()
for key in ('edge_size', 'far_size', 'grade'):
    fine['study']['mesh'][key] /= 2
fine['panel']['panels_per_edge'] *= 2
documents = [base, SampledPanelForwardPairStudyDocument.from_dict(fine)]
request = SampledPanelResolutionYieldDocument(documents, acceptance={
    'differential_forward_impedance_real': dict(minimum=[90.]*3, maximum=[130.]*3),
    'common_forward_impedance_real': dict(minimum=[20.]*3, maximum=[60.]*3)},
    confidence=.95, minimum_yield=.9)
assert request.required_evaluations == 4
saved = request.dumps()
assert normalize_saved(saved) == saved
output = execute_saved(saved, max_evaluations=4)
assert output['input'] == request.to_dict()
assert output['result']['count'] == 2
assert output['result']['resolution_count'] == 2
assert output['result']['frequencies_hz'] == [1e9, 2e9, 4e9]
assert output['error'] is None
```

Every planned original row is retained, including its error and phase. The direct
[finite-grid resolution assessment](sampled_panel_resolution_yield.md) determines
the result: all resolutions pass gives `pass`, all fail gives `fail`, and other
combinations give `unresolved`. Each manufactured row remains one statistical
trial across all frequencies and resolutions.

The common execution status is `incomplete` if any row remains unresolved,
including numerical-label disagreement without an exception. In that case the
complete comparison is retained and the top-level `error` is null; original
errors remain on the corresponding rows. With no unresolved rows, execution is
`complete`, even if the separate yield goal is `undetermined` or fails.
The confidence envelope describes the finite evaluated models, not numerical
error, continuous-band acceptance or measured production yield. This request
does not automatically refine a mesh or certify the manufacturing distribution.

Validation includes strict versions and nested keys, duplicate/nonfinite input
rejection, whole-plan admission, ordered-grid and fixed-coating identity,
failed-row continuation, caller transport limits and actual coated calculations.
The live two-sample base/joint comparison preserves the independently qualified
fields; direct and common execution reproduce the same result.

[Coated finite-grid studies](layered_sampled_panel_study.md) ·
[한국어](../../locales/ko/pages/packages/sipi/sampled_panel_resolution_yield_document.md)
