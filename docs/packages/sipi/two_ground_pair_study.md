# Two-ground paired manufacturing studies

[한국어](../../locales/ko/pages/packages/sipi/two_ground_pair_study.md)

`TwoGroundForwardPairStudyDocument` stores `sipi.two-ground-forward-pair-study/1`.
It connects ordered study/3 or /4 geometry/material samples to the explicit
[two-ground line](two_ground_panel_line.md). Each solve supplies the real
differential and common forward characteristic diagonals, under separate Ic=0
and Id=0 launches. These are not independent propagation-mode impedances.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_pair_study import TwoGroundForwardPairStudyDocument

source = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00038, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, tan_delta=.003, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9, materials={},
    sampling=dict(kind='corners', variables=[
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
```

This example prepares inputs without field solves. `study.analyze(max_evaluations=4)`
or `execute_saved(study.dumps(), max_evaluations=4)` performs the work. The budget
is checked before field work. Lengths are metres and frequency Hz. Separate metal
laws for each whole signal surface and each ground are fixed across samples.
All panel controls are required in saved JSON; unknown, duplicate, missing and
nonfinite fields are refused. Nominal validation does not prove all samples valid.

The existing ordered sampler supplies corners, sweeps, seeded uniform or normal
samples, including material bindings, correlations and fixed geometry constraints.
No row is clipped, dropped, deduplicated or resampled. Each row retains its exact
sample, resolved parameters/materials, line input, both values or the failing
phase and original cause. Completed field evidence survives a later diagnostic
failure. Interrupts propagate; ordinary failures allow subsequent rows to run.
Statistics are available only when every row succeeds. A partial execution is
`incomplete`; saved requests, records and projects retain and reopen it without
solving. Descriptive summaries are not a production-yield or confidence claim.

The registered physical check uses four width/gap corners at 2 GHz and 64, 128,
256 panels per edge. Both adjacent R, L and C0 changes must satisfy relative 0.01
with zero absolute tolerance. Each level independently reconstructs the forward
launch values from complex RLGC matrices. This checks the stated finite-domain
case; it does not establish outer-boundary convergence, empirical accuracy or
universal template/frequency coverage. Original criteria remain unchanged.

The explicit shared `galerkin.laplace_two_ground` capability is required. This
uses the exact shared development revision in `dependencies.json`. Missing
capability fails explicitly; no other current method is substituted. Browser,
macOS and Windows qualification are separate from these Linux checks.
