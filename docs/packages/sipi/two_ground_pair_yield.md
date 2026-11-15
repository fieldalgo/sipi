# Joint acceptance of two-ground manufacturing samples

[한국어](../../locales/ko/pages/packages/sipi/two_ground_pair_yield.md)

`TwoGroundForwardPairYieldDocument` stores strict
`sipi.two-ground-forward-pair-yield/1` inputs. It combines the explicit
[two-ground manufacturing study](two_ground_pair_study.md) with inclusive
minimum/maximum limits on both real forward impedance quantities. One complete
sample is one AND event; multiplying marginal acceptance fractions is incorrect
when the quantities depend on the same geometry/material sample.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_pair_study import TwoGroundForwardPairStudyDocument

source = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00038, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, tan_delta=.003, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9, materials={},
    sampling=dict(kind='uniform', count=4, seed=17, variables=[
        dict(name='width', lower=.00043, upper=.00044),
        dict(name='gap', lower=.00028, upper=.00030)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
study = TwoGroundForwardPairStudyDocument(source,
    conductors=dict(positive=metal, negative=metal),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=64, ground_modes=128,
    interpolation_degree=12)
assert TwoGroundForwardPairStudyDocument.loads(study.dumps()).dumps() == study.dumps()
assert len(study.samples()) == 4

from sipi.two_ground_pair_yield import TwoGroundForwardPairYieldDocument
acceptance = dict(
    differential_forward_impedance_real=dict(minimum=90., maximum=91.),
    common_forward_impedance_real=dict(minimum=44.4, maximum=44.6))
assessment = TwoGroundForwardPairYieldDocument(study, acceptance=acceptance,
                                             confidence=.95, minimum_yield=.8)
assert TwoGroundForwardPairYieldDocument.loads(assessment.dumps()).dumps() == assessment.dumps()
```

Preparation is field-free. `assessment.analyze(max_evaluations=4)` performs four
ordered extractions; the common saved execution API uses the same budget and
returns every row. This four-sample example illustrates the contract, not a
statistically adequate production characterization. Values and limits are ohms.

Only seeded uniform or normal sampling is admitted. Draws must be iid under the
stated input model; within-row variable correlation is allowed. Corners and
sweeps do not establish an iid acceptance probability and are rejected before
fields. The source retains separate metal laws and panel settings; no alternative
current method is used. At least one bound per quantity is required, confidence
is strictly between zero and one, and an optional minimum probability is in [0,1].

`assess_two_ground_pair_yield(study_result, acceptance=..., confidence=.95)`
assesses existing rows without solving. It checks the exact planned samples,
row order, variable names and completed/failed metadata. Every unknown row stays
in the original denominator. The sample fraction lies between passed/count and
(passed+unknown)/count. The confidence interval is the existing exact
Clopper-Pearson envelope over every possible completion of unknown labels.
All-unknown rows give [0,1]. A requested minimum probability is pass when the
lower confidence bound meets it, fail when the upper bound is below it, and
undetermined otherwise. It does not convert an unresolved solve into a failure
or a pass. Structural checks cannot authenticate manually constructed field rows.

Saved execution is `incomplete` if any row is unresolved. Original failures,
current/mesh observations, samples and classifications are preserved in saved
records and projects. Interrupts propagate; restoring a record does not solve.
The interval covers sampling uncertainty conditional on the stated model; it
excludes numerical error, model mismatch, adaptive selection and measurement
error. It is not measured production yield.

Validation includes independent finite binomial-tail inversion, exact endpoint
inclusion, joint truth tables, all unknown completions, corrupt-row refusal,
source/installed receipts and a registered four-draw 2 GHz finite-domain case.
Physical accuracy and panel/volume/outer convergence remain separate gates.
No new browser, macOS or Windows qualification follows from Linux checks.
