# Joint acceptance across fixed numerical resolutions

`assess_panel_pair_resolution_yield` compares 2–8 already calculated
`PanelForwardPairStudy` results without performing fields. All inputs must
retain the same version/current method, physical geometry, fixed metals,
dielectric models, frequency, constraints and iid sampling specification.
Only the explicit volume mesh and panel controls may differ. Repeated control
configurations are refused; resolution ordering is not assumed to be refinement.
Outer-box changes, different physical designs and different random samples
are outside this comparison contract.

For each manufactured sample, the existing paired limits are evaluated at
every supplied resolution. All passes give `pass`, all failures give `fail`,
and mixed labels or any original failed calculation give `unresolved`.
These labels summarize finite agreement; they do not identify a proven
continuum solution. The original results, phases, errors and individual
resolution assessments remain available and unchanged.

The denominator is the number of samples, not samples times resolutions.
The fraction bounds are unanimous passes/n and (passes+unresolved)/n. The
existing Clopper–Pearson unresolved envelope supplies the confidence limits
for these fixed evaluated models. It does not include a proven discretization
error bound. Agreement cannot detect shared systematic error. Neither this
comparison nor a nominal iid interval establishes measured production yield.

The example uses two samples only to demonstrate the workflow. The comparison
itself runs no fields; the two study analyses explicitly do so first.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.panel_resolution_yield import assess_panel_pair_resolution_yield

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
studies = [base.analyze(max_evaluations=2),
           PanelForwardPairStudyDocument.from_dict(fine).analyze(max_evaluations=2)]
comparison = assess_panel_pair_resolution_yield(studies, acceptance={
    'differential_forward_impedance_real': dict(minimum=90., maximum=130.),
    'common_forward_impedance_real': dict(minimum=20., maximum=60.)},
    confidence=.95, minimum_yield=.9)
assert comparison.to_dict()['count'] == 2
assert comparison.to_dict()['resolution_count'] == 2
assert sum((comparison.passed, comparison.failed, comparison.unresolved)) == 2
```

`assessments` retains each original paired assessment. `classifications`,
`confidence_interval` and the outer tuple are immutable. `to_dict()` includes
each original input and assessment, per-sample labels across resolutions,
the single denominator and an explicit finite-resolution scope. The optional
`minimum_yield` uses this conservative interval and can remain `undetermined`.
No existing study or yield result is automatically replaced.

In the retained eight-sample coated case, the four resolutions accept 6, 7,
6 and 7 samples. One sample crosses the 109-ohm differential lower limit.
The comparison reports six passes, one failure and one unresolved sample:
fraction bounds [.75, .875], with a 95% confidence envelope of approximately
[.3491, .9968]. The original nominal result remains six of eight and retains
its original interval. These are observations of the stated model and finite
resolutions, not physical error or production-acceptance certificates.

Validation includes complete joint truth tables, independent finite-binomial
tail inversion, all possible unresolved completion counts, physical/input
identity checks and actual coated fields at a specification boundary. The
32 retained qualification fields are replayed with exact input hashes; a
small live regression independently regenerates two samples at four resolutions.
This direct API does not add a saved request or automatically choose a mesh.

[Coated tolerances](layered_panel_study.md) · [Joint iid acceptance](panel_pair_yield.md) ·
[한국어](../../locales/ko/pages/packages/sipi/panel_resolution_yield.md)
