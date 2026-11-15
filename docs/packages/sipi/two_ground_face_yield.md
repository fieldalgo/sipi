# IID acceptance with two-ground face metals

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_yield.md)

Two saved contracts assess the original ordered manufacturing rows with fixed
physical-face conductor laws:

| Module / document | Schema | Acceptance event |
|---|---|---|
| two_ground_face_line_yield / TwoGroundFaceLineQuantityYieldDocument | sipi.two-ground-face-line-quantity-yield/1 | Inclusive minimum/maximum for one quantity |
| two_ground_face_pair_yield / TwoGroundFaceForwardPairYieldDocument | sipi.two-ground-face-forward-pair-yield/1 | Both launched-pair impedance limits hold in the same row |

The inputs are a [single-quantity study](two_ground_face_line_study.md) or
[paired study](two_ground_face_pair_study.md). Single quantities retain their
original units: ohms for real characteristic impedances, Np/m for attenuation.
Zero attenuation is valid. Paired quantities use the full forward characteristic
matrix under separate Ic=0/Id=0 launches, not independent modes. Joint acceptance
is counted directly; it is not the product of marginal acceptance fractions.

Only uniform or normal IID rows are accepted. Variables may be correlated within
a normal row; independence is required across rows. Sweep/corner inputs are
refused. Every original sample, including invalid geometry and calculation
failures, remains in order and in the denominator. Unresolved rows are never
dropped, replaced or treated as known failures. If k rows pass and u are unknown
out of n, the observed fraction bounds are [k/n, (k+u)/n]. The conservative
Clopper–Pearson interval envelopes every possible unknown completion using the
existing binomial-tail implementation. No confidence formula or limit changes.

This is conditional on the stated distribution and IID assumptions. It does not
include numerical, material-distribution or measurement error, and it is not
measured production yield. Four draws in the example are an execution example,
not sufficient evidence for a manufacturing yield claim.

The following example only validates and round-trips inputs:

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_face_line_study import TwoGroundFaceLineQuantityStudyDocument
from sipi.two_ground_face_pair_study import TwoGroundFaceForwardPairStudyDocument
from sipi.two_ground_face_line_yield import TwoGroundFaceLineQuantityYieldDocument
from sipi.two_ground_face_pair_yield import TwoGroundFaceForwardPairYieldDocument

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1., roughness=dict(kind="smooth"))

faces = dict(zip(("bottom", "top", "left", "right"),
                 [metal(sigma) for sigma in (58e6, 35e6, 21e6, 45e6)]))

def source(paired):
    parameters = dict(width=.000435 if paired else .0006, plane_spacing=.002,
        eps_r=4., thickness=.00005, tan_delta=.003, box_width=.008)
    variables = [dict(name="width", lower=.00043 if paired else .00055,
                      upper=.00044 if paired else .00065)]
    if paired:
        parameters["gap"] = .00029
        variables.append(dict(name="gap", lower=.00028, upper=.00030))
    else:
        parameters["trace_height"] = .0007
    return ImpedanceStudyDocument("coupled_stripline" if paired else "offset_stripline",
        parameters, quantity="z_diff_forward" if paired else "z0", frequency=2e9,
        materials={}, mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05),
        sampling=dict(kind="uniform", count=4, seed=17, variables=variables))

reference = dict(kind="surfaces", bottom=metal(58e6), top=metal(21e6), sides=None, conductors={})
scalar = TwoGroundFaceLineQuantityStudyDocument(source(False), quantity="impedance_real",
    conductors=dict(signal=faces), reference=reference, ground_thickness=35e-6,
    panels_per_edge=64, ground_modes=128, interpolation_degree=16)
pair = TwoGroundFaceForwardPairStudyDocument(source(True),
    conductors=dict(positive=faces, negative=dict(zip(faces,reversed(list(faces.values()))))),
    reference=dict(reference, top=metal(58e6)), ground_thickness=35e-6,
    panels_per_edge=64, ground_modes=128, interpolation_degree=16)
scalar_acceptance = TwoGroundFaceLineQuantityYieldDocument(scalar, minimum=57., maximum=59., minimum_yield=.8)
pair_acceptance = TwoGroundFaceForwardPairYieldDocument(pair, acceptance={
    "differential_forward_impedance_real": dict(minimum=90., maximum=91.),
    "common_forward_impedance_real": dict(minimum=44.4, maximum=44.6)}, minimum_yield=.8)
for document in (scalar_acceptance, pair_acceptance):
    assert type(document).loads(document.dumps()).dumps() == document.dumps()
# Explicit field work: result = scalar_acceptance.analyze(max_evaluations=4)
```

Construction and normalization perform no field solves. Strict parsing rejects
missing/extra keys, duplicates, nonfinite values and incompatible source schemas.
The entire sample count must fit the caller budget before calculation. Failed
rows retain their original stage, typed cause and available current/mesh records;
later rows still run and interrupts propagate. A numerical limit violation is
an assessed failure, distinct from an unresolved calculation. Saved execution is
incomplete when any row remains unresolved, regardless of the yield goal status.

`assess_two_ground_face_line_yield` and `assess_two_ground_face_pair_yield` in the
respective modules assess an existing correctly typed study without field work.
They verify sample vectors, order, counts, values and failure structure. This
structural validation does not authenticate externally constructed field data.
The prior whole-boundary contracts remain separate. CLI, requests, records and
projects retain all rows; restoration never recomputes fields.

Validation retains independent finite binomial-tail inversion, SciPy exact
interval comparison, inclusive limits, all unknown completions, four single
quantities, correlated invalid geometry, budgets, interrupts and strict input
checks. Actual scalar and paired four-row seed-17 examples use the registered
2 GHz face-metal studies; their classifications are independently recomputed
from the stated limits and binomial intervals. Those cases reuse the documented
study refinement evidence, not a claim of convergence for arbitrary future
samples. Full regression, browser/platform parity and measured agreement remain
separate from the selected source/installed checks.
