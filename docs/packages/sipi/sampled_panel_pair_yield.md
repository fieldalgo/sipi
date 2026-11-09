# Joint iid acceptance across finite frequencies

[Fixed finite-frequency candidates](sampled_panel_pair_selection.md) adds simultaneous bounds across a predeclared candidate family.

[한국어](../../locales/ko/pages/packages/sipi/sampled_panel_pair_yield.md) ·
[Finite-frequency samples](sampled_panel_pair_study.md) · [Single-frequency joint acceptance](panel_pair_yield.md)

`assess_sampled_panel_pair_yield` treats one manufactured iid sample as one
Bernoulli trial. A completed row passes only when both named forward impedances
meet every supplied frequency's inclusive limits. Any missed limit fails the
row; an atomic failed frequency batch is unresolved. Frequency points and the
two quantities can be correlated. Their count never increases the number of
manufactured specimens, and their marginal pass fractions are not multiplied.

`SampledPanelForwardPairYieldDocument` saves this as
`sipi.sampled-panel-forward-pair-yield/1`, with exactly `schema`, `study`,
`acceptance`, `confidence` and `minimum_yield`. The nested document is one
finite-frequency paired study using iid uniform or normal sampling; sweeps and
corners are rejected. Within-row parameter correlations retain their existing
meaning. The study's positive frequency grid and anchor rules remain unchanged.

Acceptance has exactly `differential_forward_impedance_real` and
`common_forward_impedance_real`. Each has `minimum` and `maximum` arrays with
one entry per frequency, in ohms. An entry is null or a finite nonnegative
number. At every quantity/frequency at least one bound must be present and any
lower bound must not exceed its upper bound. There is no scalar broadcasting.
Criteria and sampling design must be fixed before observing the assessed data.

The equal-tailed Clopper-Pearson interval is computed for this single joint
event. With unresolved rows it envelopes every possible assignment of their
labels, retaining the original denominator. No frequency multiplicity correction
is needed for this one predeclared event. This does not provide simultaneous
coverage for separately reported frequency probabilities or adaptive choice of
criteria, models or designs. The sample-fraction bounds are descriptive and
are reported separately from the confidence interval.

With a requested `minimum_yield`, a lower confidence bound at or above the target
gives `pass`, an upper bound below it gives `fail`, and other cases give
`undetermined`. An omitted target gives `not-requested`. These decisions concern
the stated iid distribution and fixed numerical event. They do not include
solver, material, mesh or distribution-model uncertainty, and do not establish
measured production yield or continuous-band behavior.

Assessment reconstructs the saved source and checks the exact frequency vector,
variable and row order, every planned sample vector, and complete positive finite
`(N, 2)` values or a consistent unresolved row. No fields run during assessment.
These structural checks do not authenticate manually constructed field values.
The immutable result keeps all original rows, named limit arrays, labels,
counts, sample-fraction bounds and interval. Original inputs and failure causes
remain available.

`execute_saved()` uses the caller's row budget. All fields evaluated successfully
means execution `complete`, even when the yield goal fails. Any unresolved row
makes execution `incomplete`, independently of the yield decision; for example,
a zero target can pass while execution remains incomplete. Malformed inputs,
non-iid sampling and whole-study generation/budget errors raise before fields.

## Reproducible material example

The four correlated uniform-material rows below all meet deliberately broad
illustrative limits. Four successes still cannot certify a 0.9 joint probability
at 95% confidence: the lower bound is approximately 0.397635. This is a declared
simulation distribution, not a measured manufacturing population.

```python
from sipi.dielectric import DebyeDielectric
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.sampled_panel_pair_yield import SampledPanelForwardPairYieldDocument
from sipi.execution import normalize_saved, execute_saved

frequencies = [0.5e9, 1e9, 2e9]
material = DebyeDielectric(3.0, (0.7,), (1e9,))
source = ImpedanceStudyDocument("coupled_microstrip",
    dict(width=0.3e-3, gap=0.2e-3, substrate_height=0.5e-3, eps_r=4,
         thickness=35e-6, air_height=2e-3, box_width=6e-3),
    quantity="z_diff_forward", frequency=frequencies[0],
    materials=dict(substrate=material, air=material),
    mesh=dict(edge_size=10e-6, far_size=0.2e-3, grade=0.1),
    material_variables={
        "strength_substrate": dict(region="substrate", path=["strengths", 0]),
        "strength_air": dict(region="air", path=["strengths", 0])},
    sampling=dict(kind="normal", count=4, seed=3,
        correlation=[[1.0, 1.0], [1.0, 1.0]], variables=[
            dict(name="strength_substrate", mean=0.7, std=0.05),
            dict(name="strength_air", mean=0.7, std=0.05)]))
study = SampledPanelForwardPairStudyDocument(source,
    conductor=dict(kind="perfect"), frequencies=frequencies)
quantities = ("differential_forward_impedance_real", "common_forward_impedance_real")
request = SampledPanelForwardPairYieldDocument(study,
    acceptance={q: dict(minimum=[0.0] * 3, maximum=[1000.0] * 3) for q in quantities},
    confidence=0.95, minimum_yield=0.9)
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=4)
assert output["status"] == "complete"
assert output["result"]["count"] == output["result"]["passed"] == 4
assert output["result"]["goal_status"] == "undetermined"
assert output["result"]["confidence_interval"][0] < 0.9
```

## Validation and limits

Independent finite binomial sums and live SciPy exact intervals check ordinary
and extreme counts. Tests enumerate unresolved completions, opposing frequency
marginals, unchanged specimen counts after grid expansion, inclusive/asymmetric/
one-sided limits, malformed manual rows, and execution-versus-goal status.

A fixed four-row uniform geometry case at 0.5/1/2 GHz uses 109.5..110.5 ohm
differential and 39.9..40.1 ohm common limits at every frequency. Independent
balanced 2N characteristic matrices agree within 1e-10 and produce the same
fail/pass/fail/fail labels. Its 95% interval is approximately [0.006309, 0.805880],
so the stated 0.9 goal fails. A four-row correlated uniform Debye case matches its
complex material formula within 1e-10; all four rows pass and the same 0.9 goal
remains undetermined. Independent interval checks use 1e-12 absolute tolerance.

The field cases and sample-stage convergence studies have bounded scopes; this
statistical wrapper adds no new geometry/outer-convergence certificate. It also
adds no browser/Worker/EXE integration or platform guarantee. Existing saved
schemas and single-frequency inference retain their contracts.
