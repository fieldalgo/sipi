# Joint acceptance across finite frequencies and resolutions

`assess_sampled_panel_pair_resolution_yield` compares 2–8 already calculated
`SampledPanelForwardPairStudy` results. The explicit study version, physical
inputs, fixed coatings, ordered frequency grid, sampling distribution, seed,
variable order and constraints must agree. Only volume mesh and panel controls
may differ; duplicate controls are refused. Both study versions 1 and 2 are
supported, but a comparison cannot mix them. No field calculation occurs inside
the assessment. Manually assembled records are checked for structure and sample
correspondence; they are not authenticated field solutions or measurements.

Within a resolution, both forward-impedance limits must hold at every supplied
frequency. Across resolutions a sample passes only when all resolutions pass,
fails when all fail, and otherwise remains unresolved. Any original failed batch
also leaves the sample unresolved, even if another resolution fails a limit.
All original rows, inputs, error phases and individual assessments are retained.

A manufactured row is one trial: the denominator is not multiplied by the
frequency count or resolution count. The Clopper–Pearson unresolved envelope
describes the stated iid distribution evaluated by these finite models. It does
not bound discretization error, detect shared systematic error, prove acceptance
between frequency samples or establish measured production yield. Unresolved
means disagreement or failed calculation, not an estimate of the true answer.

The small example explicitly performs the study calculations before comparing
them. Two samples demonstrate usage; they cannot certify a high yield.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.sampled_panel_resolution_yield import assess_sampled_panel_pair_resolution_yield

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
studies = [base.analyze(max_evaluations=2),
           SampledPanelForwardPairStudyDocument.from_dict(fine).analyze(max_evaluations=2)]
comparison = assess_sampled_panel_pair_resolution_yield(studies, acceptance={
    'differential_forward_impedance_real': dict(minimum=[90.]*3, maximum=[130.]*3),
    'common_forward_impedance_real': dict(minimum=[20.]*3, maximum=[60.]*3)},
    confidence=.95, minimum_yield=.9)
assert comparison.to_dict()['count'] == 2
assert comparison.to_dict()['resolution_count'] == 2
assert sum((comparison.passed, comparison.failed, comparison.unresolved)) == 2
assert comparison.frequencies == (1e9, 2e9, 4e9)
```

`frequencies`, `classifications`, `confidence_interval` and the nested acceptance
arrays are immutable. `to_dict()` retains the original study input and joint
assessment for each resolution, labels for each manufactured row, the single
denominator and an explicit finite-frequency/resolution scope. Modifying an
exported dictionary does not modify the assessment. `minimum_yield` uses the
confidence envelope and may remain `undetermined` despite complete calculations.

In the retained eight-sample coated example at 1, 2 and 4 GHz, the four supplied
resolutions each accept five samples and reject three against the fixed joint
limits. The comparison therefore has no unresolved rows in that finite set;
this agreement is not proof of physical accuracy or agreement over all possible
manufactured geometries. Independent binomial-tail tests include all unresolved
completions, while live coated calculations verify the full-frequency fields
at two samples and four resolutions against independent network references.

This direct API adds no saved-request version and does not automatically refine
meshes or replace existing nominal yield results.

[Coated finite-grid studies](layered_sampled_panel_study.md) ·
[Single-frequency resolution comparison](panel_resolution_yield.md) ·
[한국어](../../locales/ko/pages/packages/sipi/sampled_panel_resolution_yield.md)

[Save and execute the complete comparison](sampled_panel_resolution_yield_document.md).
