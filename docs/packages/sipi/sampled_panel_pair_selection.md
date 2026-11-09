# Fixed paired candidates over finite frequencies

[한국어](../../locales/ko/pages/packages/sipi/sampled_panel_pair_selection.md) ·
[Joint acceptance](sampled_panel_pair_yield.md) · [Single-frequency candidates](panel_pair_selection.md)

`SampledPanelForwardPairSelectionDocument` compares 1..32 predeclared candidates
under common frequency-specific limits. Each candidate supplies a unique name,
finite nonnegative cost, and a complete `SampledPanelForwardPairStudyDocument`
with iid uniform or normal sampling. All candidates must use exactly the same
ordered positive frequency grid. Sampling counts, explicit geometry/materials,
mesh and panel settings can differ and remain visible. No interpolation or
limit broadcasting is performed. Costs use one explicit caller-provided unit.

The strict saved schema `sipi.sampled-panel-forward-pair-selection/1` has exactly
`schema`, `candidates`, `cost_unit`, `acceptance`, `confidence`, and
`minimum_yield`. Candidate entries have exactly `name`, `cost`, and `study`.
Acceptance uses the two named minimum/maximum arrays from joint acceptance;
each quantity/frequency needs at least one inclusive bound. A target probability
in [0,1] is required. Candidates, criteria and distributions must be fixed before
observing the assessed data. This is not an adaptive search or a certificate
for a candidate family chosen after viewing these samples.

Each manufactured row is one Bernoulli trial: both impedances must meet every
supplied frequency's limits. Frequencies never multiply the specimen count.
For a family of K candidates, the existing conservative exact-float Bonferroni
allocation gives each candidate confidence at least 1-(1-confidence)/K. The
allocation is by candidate count only, with no extra frequency or quantity
factor. Candidates may share seeds, samples or arbitrary dependence. Within
each candidate the original rows must be iid from its stated distribution.
An unrepresentable near-one confidence allocation is rejected.

Every original failed frequency batch remains unresolved. Its candidate's
Clopper-Pearson interval envelopes all completions of unknown labels. A candidate
is certified only when its lower bound reaches the target; upper bound below
the target means fail, otherwise undetermined. Among certified candidates the
lowest cost wins, with original order resolving exact ties. A cheaper unresolved
candidate may actually be feasible. The result is a certified member of a fixed
set, not a global or continuous optimum. With no certified candidate the result
distinguishes `none-certified` (all fail) from `undetermined`.

The caller's 2..10000 evaluation budget counts all planned manufactured rows
across the family, including duplicates and failures. Budget rejection and
every candidate's sample generation occur before any field solve. Then all rows
and candidates are attempted, without early selection or resampling. Full
candidate inputs, common grid, original rows/causes, intervals, costs and
selection remain in the result. Execution is `incomplete` when any row failed,
even if another candidate is selected; a zero target never hides failed rows.
Successful fields can give complete execution with no candidate certified.

## Reproducible example

The identical studies below deliberately demonstrate dependent candidates.
Four all-pass rows give a lower bound about 0.334370 at candidate confidence
0.975, exceeding the illustrative 0.3 target. Duplicating a candidate does not
create eight specimens for its interval. The smaller cost selects the second.

```python
from sipi.dielectric import DebyeDielectric
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.sampled_panel_pair_selection import SampledPanelForwardPairSelectionDocument
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
request = SampledPanelForwardPairSelectionDocument(
    [dict(name="first", cost=2.0, study=study.to_dict()),
     dict(name="second", cost=1.0, study=study.to_dict())],
    cost_unit="relative-cost",
    acceptance={q: dict(minimum=[0.0] * 3, maximum=[1000.0] * 3) for q in quantities},
    confidence=0.95, minimum_yield=0.3)
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=8)
assert output["status"] == "complete"
assert output["result"]["evaluations"] == 8
assert output["result"]["candidate_confidence"] == 0.975
assert output["result"]["selected"] == dict(index=1, name="second", cost=1.0)
assert all(c["assessment"]["passed"] == 4 for c in output["result"]["candidates"])
```

## Validation and scope

Tests check exact family error allocation for 1..32 candidates, independent
binomial tails, correlated duplicate candidates, frequency-grid invariance of
trial counts/intervals, opposing frequency failures, complete family preflight,
cost ties, unknown cheaper candidates and original failed stages in execution.
Existing single-frequency schemas retain their contracts.

A fixed actual two-candidate family uses four heterogeneous geometric samples
and four correlated uniform Debye samples at 0.5/1/2 GHz. For this separate
selection example both quantities have fixed 0..1000 ohm limits, costs 2 and 1,
confidence 0.95 and target 0.3. Both candidates pass their simultaneous bounds;
the material candidate is selected. Balanced 2N and analytic material matrices
agree within 1e-10, and independent binomial intervals within 1e-12. The analytic
material check shares C0 and is not an independent geometry solution. This broad
example does not change the failed narrow-limit case in joint acceptance.

This wrapper adds no new field convergence certificate, continuous-band
guarantee, measured production-yield evidence or model-error coverage. Existing
qualified field/sample cases remain bounded in scope. Browser/Worker/EXE
integration and other-platform qualification remain separate.
