# Manufacturing samples with explicit shape currents

[Finite frequency grids](shape_sampled_panel_pair_study.md) preserve one manufactured sample across all requested frequencies.

[Explicit joint acceptance](shape_panel_pair_yield.md) retains the same sampled current evidence.

[한국어](../../locales/ko/pages/packages/sipi/shape_panel_pair_study.md) ·
[Current method](shape_panel_line.md) · [Original sampling contract](panel_pair_study.md)

`ShapePanelForwardPairStudyDocument` explicitly selects capacitance-shape currents
for paired manufacturing samples. The strict `sipi.shape-panel-forward-pair-study/1`
JSON has exactly `schema`, `study`, `step_fraction`. Its nested
`PanelForwardPairStudyDocument` is version 1 or 2 (fixed coated boundaries).
Existing documents keep their original method. This wrapper preserves ordered
geometry/material variables, correlation, fixed pitch, sampling seeds and nominal
mesh controls. It returns real differential and common forward impedances at one
positive frequency, with separate launch definitions and all asymmetric cross terms.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.shape_panel_pair_study import ShapePanelForwardPairStudyDocument
from sipi.execution_request import SavedExecutionRequest

source = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.5e-3, gap=.3e-3, substrate_height=.2e-3, eps_r=1.,
         thickness=35e-6, air_height=3e-3, box_width=8e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='width', lower=.45e-3, upper=.55e-3)]))
panel = PanelForwardPairStudyDocument(source, conductor={'kind':'perfect'},
    panels_per_edge=16, ground_modes=512, interpolation_degree=16)
document = ShapePanelForwardPairStudyDocument(panel, step_fraction=1e-3)
request = SavedExecutionRequest(document.dumps(), max_evaluations=3)
assert ShapePanelForwardPairStudyDocument.loads(document.dumps()).dumps() == document.dumps()
assert len(document.samples()) == 3
# receipt = request.run()  # Runs all three field extractions.
```

Normalization checks the nominal offset geometry without fields. It does not
validate every sampled geometry. Each original sample, including duplicates, is
attempted once in order. Invalid geometry/materials/offsets become failed rows;
later rows continue. The entire sample count must fit `max_evaluations` (integer
2..10000) before any field solve. Each sample includes multiple internal current
solves; this budget counts whole line extractions, not individual panel solves.

Every successful extraction retains its full `current_solver` record. A diagnostic
failure retains that extracted record too. A shape-line failure preserves its
staged partial evidence in `cause_details`; ordinary errors retain phase, type and
message. Unavailable evidence is null. Failed rows remain in the denominator and
make the complete descriptive summary null. Samples are never dropped or resampled.
Common execution returns `incomplete` with all rows when any sample fails; saved
requests, records and projects preserve this result without recalculating it.

This is descriptive sampling, not a production-yield claim. Existing saved paired
yield documents do not implicitly accept this schema. Resolved nominal mesh,
panel controls and the relative offset step remain fixed across samples; geometric
meshes are rebuilt. No per-row resolution qualification is automatic. The current
method's bottom-ground/open-wall and offset-admission restrictions still apply.

## Validation scope

Independent modal construction and statistics test ordering, correlated/duplicate
samples, fixed pitch, failures and budgets. Actual four-corner uniform-vacuum
samples for bulk and fixed-coated conductors check C=C0, G=0, external LC, independent
metal transfer and a full four-port matrix exponential. Two selected corners also
retain separate panel, volume, joint and finite outer-domain observations. Their
whole-matrix comparisons do not bound small mutual entries or absolute error, and
do not certify every sample, material, geometry or frequency.

The initial 8/16/32 mm boxes do **not** satisfy the stated 0.1% resistance
change criterion: the first changes are about 0.55% and 0.60%. They remain
rejected counterexamples. Separate current-only 32/64/128 mm comparisons meet
the same whole-matrix threshold, with independent mode and panel refinements at
128 mm. This larger-domain check does not compute a dielectric volume mesh or
qualify all entries of the original small-domain line. The descriptive study
returns its requested finite-domain results; it does not relabel them converged.
