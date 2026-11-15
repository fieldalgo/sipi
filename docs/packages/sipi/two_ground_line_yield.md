# Two-ground line-quantity acceptance probabilities

[한국어](../../locales/ko/pages/packages/sipi/two_ground_line_yield.md)

`TwoGroundLineQuantityYieldDocument` stores strict
`sipi.two-ground-line-quantity-yield/1` inputs. Its source is an explicit
[two-ground quantity study](two_ground_line_study.md), with one selected
Re(Zc), scalar attenuation Re(gamma), or paired forward Re(Zdd)/Re(Zcc).
Bounds are inclusive and use the quantity's unit: ohms or Np/m.
Completed attenuation can be zero; completed impedances must be positive.
For a simultaneous pair of limits, use the [joint assessment](two_ground_pair_yield.md).

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_line_study import TwoGroundLineQuantityStudyDocument
source = ImpedanceStudyDocument('offset_stripline',
    dict(width=.0006, plane_spacing=.002, trace_height=.0007, eps_r=4.,
         thickness=.00005, tan_delta=.003, box_width=.008),
    quantity='z0', frequency=2e9, materials={},
    sampling=dict(kind='uniform', count=4, seed=17, variables=[
        dict(name='width', lower=.00055, upper=.00065)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
study = TwoGroundLineQuantityStudyDocument(source, quantity='impedance_real',
    conductors=dict(signal=metal),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=64, ground_modes=128, interpolation_degree=12)
assert TwoGroundLineQuantityStudyDocument.loads(study.dumps()).dumps() == study.dumps()
assert len(study.samples()) == 4

from sipi.two_ground_line_yield import TwoGroundLineQuantityYieldDocument
assessment = TwoGroundLineQuantityYieldDocument(study, minimum=57., maximum=59.,
                                                confidence=.95, minimum_yield=.8)
assert TwoGroundLineQuantityYieldDocument.loads(assessment.dumps()).dumps() == assessment.dumps()
```

Preparation is field-free. `assessment.analyze(max_evaluations=4)` performs
four ordered extractions. Common saved execution uses the same budget.
This four-draw example explains the contract; it is not statistically adequate
production characterization. The selected metal laws, geometry/material samples,
current panels and dielectric mesh remain the explicit source inputs.

Only iid uniform or normal sampling is admitted; within-row variable correlation
is allowed. Sweeps/corners are rejected. At least one bound is required,
confidence must lie strictly between zero and one, and an optional minimum
acceptance probability must lie in [0,1]. No sample is clipped, retried or dropped.

`assess_two_ground_line_yield(study_result, minimum=..., maximum=...)` assesses
existing rows without fields. It checks quantity, variable names, regenerated
sample vectors, order and failure metadata. Such structural validation cannot
authenticate manually constructed numerical results. Completed rows meet both
stated bounds to pass. Unknown rows remain in the original denominator: the
observed fraction lies between passed/count and (passed+unknown)/count.
The exact Clopper-Pearson interval envelopes every possible completion of unknown
labels. All unknowns give [0,1]. A minimum probability passes only when the lower
confidence bound meets it, fails when the upper bound is below it, and is
undetermined otherwise. This interval covers iid sampling uncertainty conditional
on the stated model; it excludes discretization, material/distribution mismatch,
adaptive selection and measurement error. It is not measured production yield.

Partial saved execution is `incomplete`, preserving each sample, original
failure phase/cause and completed current/mesh evidence. Restoring a request,
record or project does not solve. Interrupts propagate. Existing line-yield
calculations retain their original checks and statistical implementation; the
new consumer explicitly supplies its own study/parser/result types.

Validation compares exact intervals with independently inverted finite binomial
tails, checks inclusive endpoints, zero attenuation, unknown completions,
corrupt-row refusal and field-free restoration. The registered finite-domain
2 GHz offset-stripline case uses seed17, four uniform width draws .55–.65mm,
limits57–59ohms, confidence.95 and minimum probability.8. It retains actual
rows and independently classifies them. Source/installed receipts must agree.
These are statistical wiring checks, not a replacement for panel, volume or
outer convergence, measured accuracy or cross-platform qualification.
