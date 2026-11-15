# Joint IID acceptance of face-metal frequency grids

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_sampled_pair_yield.md)

`TwoGroundFaceSampledForwardPairYieldDocument` stores
`sipi.two-ground-face-sampled-forward-pair-yield/1`. It assesses explicit inclusive
limits on both real forward impedances at every frequency of a
[face-metal manufacturing grid](two_ground_face_sampled_pair_study.md).
One manufactured row is one trial. Every frequency/quantity limit must hold;
frequency points do not increase the sample count, and marginal acceptance
fractions are not multiplied.

This example prepares and validates input without solving:

```python
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import DebyeDielectric
from sipi.two_ground_face_sampled_pair_study import TwoGroundFaceSampledForwardPairStudyDocument

source = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00043, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9,
    materials={'dielectric': DebyeDielectric(3., (.7,), (1e9,))},
    sampling=dict(kind='uniform', count=4, seed=19, variables=[
        dict(name='width', lower=.00043, upper=.00044)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
study = TwoGroundFaceSampledForwardPairStudyDocument(source,
    frequencies=[2e9, 3.5e9, 5e9],
    conductors=dict(
        positive=dict(zip(('bottom','top','left','right'),
            [dict(metal,conductivity=s) for s in (58e6,35e6,21e6,45e6)])),
        negative=dict(zip(('bottom','top','left','right'),
            [dict(metal,conductivity=s) for s in (45e6,21e6,35e6,58e6)]))),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=64, ground_modes=128,
    interpolation_degree=16)
assert TwoGroundFaceSampledForwardPairStudyDocument.loads(study.dumps()).dumps() == study.dumps()
assert len(study.samples()) == 4

from sipi.two_ground_face_sampled_pair_yield import TwoGroundFaceSampledForwardPairYieldDocument
acceptance = dict(
    differential_forward_impedance_real=dict(minimum=[100.]*3, maximum=[103.]*3),
    common_forward_impedance_real=dict(minimum=[50.]*3, maximum=[52.]*3))
assessment = TwoGroundFaceSampledForwardPairYieldDocument(study,
    acceptance=acceptance, confidence=.95, minimum_yield=.8)
assert TwoGroundFaceSampledForwardPairYieldDocument.loads(assessment.dumps()).dumps() == assessment.dumps()
```

`assessment.analyze(max_evaluations=4)` executes four manufactured rows across
all three frequencies. Bounds are in ohms and must provide explicit minimum and
maximum arrays for each quantity. At least one finite bound is required at every
position; `None` represents one absent bound. There is no scalar broadcasting,
frequency interpolation or relaxation of numerical solver criteria. These
acceptance limits are a specified joint event, separate from field accuracy.

Only IID uniform or normal draws under the stated model are admitted; seeded
variables may correlate within a row. Corners, sweeps and other methods are
refused. A failed grid is one unresolved trial in the original denominator.
The existing exact Clopper–Pearson envelope covers all possible completions of
unknown labels. All unknown yields [0,1]. A minimum probability passes only
when the lower confidence limit meets it, fails when the upper limit is below
it and otherwise remains undetermined. Four draws illustrate transport, not
production characterization.

`assess_two_ground_face_sampled_pair_yield(result, acceptance=..., confidence=.95)`
checks an existing face study without field solves. It validates source/grid,
row order, sample values, quantities and complete/failed structure; other study
methods and row types are refused. It cannot authenticate manually constructed
field values. Original rows, typed causes, resolved materials and current/mesh
evidence remain in the result. Caller budgets and failures follow the source
study, and interrupts propagate. Saved execution is incomplete if any trial is
unresolved; complete statistical execution does not imply a passing minimum
probability. CLI/request/record/project restoration retains that distinction
without another calculation.

The registered physical example uses the preceding study's Debye model,
0.43–0.44 mm width, 0.28 mm gap and 2/3.5/5 GHz. Before testing, the joint event
was fixed to Zdd100–103 ohms and Zcc50–52 ohms at every frequency, with four
uniform draws, seed19, confidence0.95 and requested probability0.8. Independent
entrywise classification and exact binomial intervals check the output. Earlier
endpoint mesh/panel/outer and independent field checks remain separate evidence;
the classification does not estimate numerical uncertainty at every random row.
Synthetic checks cover inclusive and one-sided limits, arbitrary within-row
correlation, all unknown-label completions, malformed rows, IID admission,
minimum-probability decisions and failed CLI restoration.

The interval is conditional on IID draws from the stated model. It does not
cover wrong distributions, field/model error, continuous frequencies, selection
bias, measured production yield or browser/platform qualification.

[Fixed-family selection](two_ground_face_sampled_pair_selection.md)

[Acceptance across numerical resolutions](two_ground_face_sampled_resolution_yield.md)
