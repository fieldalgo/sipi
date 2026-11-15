# Joint acceptance across two-ground frequency samples

[한국어](../../locales/ko/pages/packages/sipi/two_ground_sampled_pair_yield.md)

`TwoGroundSampledForwardPairYieldDocument` stores
`sipi.two-ground-sampled-forward-pair-yield/1`. It applies explicit inclusive
bounds to both real forward impedances at every frequency of a
[two-ground manufacturing grid](two_ground_sampled_pair_study.md).
One manufactured row is one trial: every named limit at every sampled frequency
must hold. Frequency points do not multiply the sample count. Multiplying
marginal acceptance fractions does not compute this joint event.

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

from sipi.two_ground_sampled_pair_yield import TwoGroundSampledForwardPairYieldDocument
acceptance = dict(
    differential_forward_impedance_real=dict(minimum=[89.]*3, maximum=[91.]*3),
    common_forward_impedance_real=dict(minimum=[44.]*3, maximum=[46.]*3))
assessment = TwoGroundSampledForwardPairYieldDocument(study, acceptance=acceptance,
                                             confidence=.95, minimum_yield=.8)
assert TwoGroundSampledForwardPairYieldDocument.loads(assessment.dumps()).dumps() == assessment.dumps()
```

Preparation and normalization do not solve fields. Calling
`assessment.analyze(max_evaluations=4)` evaluates four manufactured rows, each
at all three frequencies. The source must contain 2..64 increasing positive
frequencies. Each quantity has an explicit minimum/maximum array of the same
length; at least one finite inclusive bound is required at every position.
No scalar broadcasting or interpolation is performed. Four draws illustrate
the contract; they are not adequate production characterization.

Only seeded iid uniform or normal draws under the stated distribution are
admitted. Variables may correlate within a row. Corners and sweeps are rejected.
One failed grid is one unresolved row, retained in the original denominator.
The existing exact Clopper–Pearson unresolved envelope covers every possible
completion of unknown labels. All unknown gives [0,1]. A requested minimum
probability passes only when the lower bound meets it, fails when the upper
bound is below it, and otherwise remains undetermined.

`assess_two_ground_sampled_pair_yield(result, acceptance=..., confidence=.95)`
checks an existing study without field solves. It retains the original study,
ordered frequency vector, samples, current/mesh observations and typed failures.
The validator checks exact planned rows and completed/failed structure; it
cannot authenticate manually constructed field results. No alternate current
method or geometry is substituted. Saved execution is incomplete if any row is
unresolved; saved records and projects retain every row. Interrupts propagate.

The interval describes sampling uncertainty conditional on the stated model.
It does not cover numerical error, unmodeled frequencies, distribution error,
adaptive acceptance selection or measured production yield. Numerical accuracy
and panel/volume/outer convergence are separate gates. Existing physical grid
validation is documented with the source study; this statistical adapter makes
no additional convergence claim. Checks include independent binomial tail
inversion, all unknown completions, opposing frequency failures, unchanged
original event validation, strict stored input, execution/record/project replay,
and a fixed four-draw Debye grid at 2, 3.5 and 5 GHz. Source and exact installed
artifacts are checked separately. Linux evidence does not qualify other platforms.
