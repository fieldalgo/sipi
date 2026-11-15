# Fixed two-ground candidates across frequency samples

[한국어](../../locales/ko/pages/packages/sipi/two_ground_sampled_pair_selection.md)

`TwoGroundSampledForwardPairSelectionDocument` stores
`sipi.two-ground-sampled-forward-pair-selection/1`. Each of 1..32 fixed named
candidates supplies a complete [frequency-grid study](two_ground_sampled_pair_study.md)
and a nonnegative cost in one stated unit. They share the exact ordered frequency
vector and named inclusive acceptance arrays. Geometry, material, metal, panel
and iid sampling choices remain explicit for each candidate.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_sampled_pair_study import TwoGroundSampledForwardPairStudyDocument

source = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00038, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, tan_delta=.003, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9, materials={},
    sampling=dict(kind='uniform', count=4, seed=17, variables=[
        dict(name='width', lower=.00043, upper=.00044),
        dict(name='gap', lower=.00028, upper=.00030)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
study = TwoGroundSampledForwardPairStudyDocument(source, frequencies=[2e9,3.5e9,5e9],
    conductors=dict(positive=metal, negative=metal),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=64, ground_modes=128,
    interpolation_degree=12)
assert TwoGroundSampledForwardPairStudyDocument.loads(study.dumps()).dumps() == study.dumps()
assert len(study.samples()) == 4

from sipi.two_ground_sampled_pair_selection import TwoGroundSampledForwardPairSelectionDocument
other = study.to_dict()
other['study']['parameters']['plane_spacing'] = .0022
other['study']['parameters']['trace_height'] = .001075
acceptance = dict(
    differential_forward_impedance_real=dict(minimum=[89.]*3, maximum=[91.]*3),
    common_forward_impedance_real=dict(minimum=[44.]*3, maximum=[46.]*3))
selection = TwoGroundSampledForwardPairSelectionDocument([
    dict(name='first', cost=1., study=study.to_dict()),
    dict(name='second', cost=1.2, study=other)], cost_unit='relative',
    acceptance=acceptance, minimum_yield=.8, confidence=.95)
assert TwoGroundSampledForwardPairSelectionDocument.loads(selection.dumps()).dumps() == selection.dumps()
```

Preparation and normalization are field-free. `selection.analyze(max_evaluations=8)`
would evaluate all eight planned rows. Four rows per candidate are a small input
example, not a sufficient production estimate. Candidates must be fixed before
observing the results; no adaptive search or resampling is performed. All sample
generation is checked before the first field solve. Every row counts toward the
family budget, even if a prior candidate passes or a solve remains unresolved.
Interrupts propagate instead of returning a prematurely selected design.

Each row is one [joint event](two_ground_sampled_pair_yield.md) across both
impedances and all supplied frequencies. The unchanged conservative exact-float
Bonferroni allocation divides the family error budget by the candidate count,
not by the number of frequencies or quantities. Candidates need not be mutually
independent, but rows within each candidate must follow its stated iid model.
Each candidate retains its exact Clopper–Pearson unresolved envelope.

The lowest-cost certified member is selected, with original order breaking ties.
A cheaper unresolved member remains in the report and may in reality be feasible.
`none-certified` means all members fail the requested probability bound;
`undetermined` retains unresolved statistical decisions. A selected result does
not establish a global or continuous optimum. A zero probability target can
certify an all-unknown candidate; its unknown rows and [0,1] interval stay visible.

Shared execution, saved records and projects retain every candidate, input,
classification, current/mesh observation and typed failure. Any unknown row makes
execution incomplete even when a candidate is selected. No frequency interpolation,
continuous-band guarantee, measured yield or numerical-error coverage is implied.
Physical accuracy and resolution are separate from this selection contract.

Checks cover exact family error allocation at all supported candidate counts,
independent binomial bounds, ties, unknown lower-cost candidates, unequal sample
counts, preflight failures, strict inputs and record/project replay. A registered
2/3.5/5 GHz Debye case evaluates two fixed four-draw width intervals using deliberately
broad [1,1000] ohm limits to check selection and evidence retention. Those broad
limits are not an engineering impedance specification or accuracy test. Existing
physical grid checks remain separate. Source and exact installed artifacts are
checked independently; Linux observations do not qualify other platforms.
