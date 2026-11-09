# Paired manufacturing samples across finite frequencies

[Joint finite-frequency acceptance](sampled_panel_pair_yield.md) treats every manufactured row as one joint event.

[한국어](../../locales/ko/pages/packages/sipi/sampled_panel_pair_study.md) ·
[Single-frequency paired sampling](panel_pair_study.md) · [Finite-frequency goals](sampled_panel_pair_goal_document.md)

`SampledPanelForwardPairStudyDocument` evaluates the same manufactured geometry
and material sample at every supplied frequency. One row produces both real
mixed characteristic diagonals, `Re(Zdd)` and `Re(Zcc)`, from the full complex
panel-current line. Frequency points are not new independent manufacturing
specimens and are not independently resampled.

The strict `sipi.sampled-panel-forward-pair-study/1` keys are `schema`, `study`,
`conductor`, `panel` and `frequency_hz`. The nested paired `z_diff_forward`
study/3 or /4 retains existing geometry/material variables, sweep/corners/uniform/
correlated-normal sampling and fixed-pitch/plane-spacing rules. Its material
frequency must equal the first requested frequency exactly. The requested grid
contains 2..64 strictly increasing positive Hz samples. Panel controls and all
geometry, material, resource and skin-depth restrictions remain explicit.

Nominal full-grid normalization performs no fields. Before analysis, all sample
vectors are generated and their count checked against `max_evaluations`
(integer 2..10000). Each original sample is then attempted once as a full-frequency
line batch. This counts rows, including failed rows, rather than frequency points
or internal field solves; it does not bound elapsed time or memory. Duplicates
remain in order and later rows still run after failures. There is no clipping,
dropping, resampling or reweighting.

Each immutable row contains its index, ordered sample values, available resolved
parameters, anchored material input, full-grid line input and extracted result.
Successful `values` have shape `(N, 2)`, frequency first and differential/common
second. Signal names, frequency coordinates, single-ended/mixed bases, full
finite complex matrices and positive real diagonals are checked. Failure at
any frequency makes the entire row unresolved, with no partial value array.
The original phase, exception type and message remain, including empty messages.

Only an entirely successful study has descriptive summaries. Each named quantity
maps to one scalar summary per frequency: minimum, maximum, mean, sample standard
deviation, and interpolated p05/p95 of the original rows. Nested summaries are
immutable and share the same sample count. These are not confidence intervals or
production-yield estimates. Resolved nominal mesh and panel settings stay fixed;
the geometric mesh is rebuilt when needed, and no automatic per-row refinement
or outer convergence certificate is issued.

`execute_saved()` returns `complete` for all successful rows and `incomplete`
otherwise, preserving every row and suppressing summaries when unresolved rows
exist. Malformed input and whole-study generation/budget failures raise before
field work. Diagnostic options remain restricted to top-level line requests.
Previous saved schemas and single-frequency methods are unchanged.

## Reproducible correlated material example

This illustrative four-row distribution keeps the two regional Debye strengths
equal within each manufactured sample while evaluating that sample at all three
frequencies. It is not an inferred manufacturing distribution or yield claim.

```python
from sipi.dielectric import DebyeDielectric
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.execution import normalize_saved, execute_saved

frequencies = [0.5e9, 1e9, 2e9]
material = DebyeDielectric(3.0, (0.7,), (1e9,))
study = ImpedanceStudyDocument("coupled_microstrip",
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
request = SampledPanelForwardPairStudyDocument(study,
    conductor=dict(kind="perfect"), frequencies=frequencies)
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=4)
assert output["status"] == "complete"
assert output["result"]["count"] == 4
assert output["result"]["frequencies_hz"] == frequencies
assert len(output["result"]["summary"]["differential_forward_impedance_real"]) == 3
```

## Validation and limits

Independent frequency-dependent modal roots, live scikit-rf modal lines and
scalar statistics check every frequency and row. Tests cover 64 frequencies
within a four-row budget, duplicate/correlated samples, complete failure phases,
invalid middle-frequency diagnostics, immutable snapshots, strict transport
limits and preserved later rows. Actual heterogeneous four-corner geometry is
checked against balanced 2N characteristic eigenspaces within 1e-10. The first
and last corners separately pass volume/panel/joint refinement, relative changes
at most 0.005 and three-domain outer checks with decreasing successive absolute
changes in all six sampled quantities. These representative checks do not cover
every point of the tolerance box or automatically qualify every request.

Uniform correlated Debye samples match the complex material formula within
1e-10 and C/G/statistics within 1e-12, with zero R. That invariant shares geometric
vacuum capacitance and is not independent geometry or measurement evidence.
Finite frequency samples do not certify a continuous band. This adds no
Worker, browser, desktop packaging, timeout/cancellation or platform guarantee.
