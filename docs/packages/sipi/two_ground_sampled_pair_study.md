# Two-ground manufacturing samples on a finite frequency grid

[한국어](../../locales/ko/pages/packages/sipi/two_ground_sampled_pair_study.md)

`TwoGroundSampledForwardPairStudyDocument` stores
`sipi.two-ground-sampled-forward-pair-study/1`. It connects the same ordered
geometry/material samples to the [two-ground line](two_ground_panel_line.md)
at 2..64 explicitly increasing positive frequencies. Each row uses one current
extraction and one dielectric mesh across the grid. Its two values at each
frequency are Re(Zdd) and Re(Zcc) under separate Ic=0 and Id=0 forward launches;
they are not independent propagation-mode impedances.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import DebyeDielectric
from sipi.two_ground_sampled_pair_study import TwoGroundSampledForwardPairStudyDocument

source = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00043, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9,
    materials={'dielectric': DebyeDielectric(3., (.7,), (1e9,))},
    sampling=dict(kind='corners', variables=[
        dict(name='width', lower=.00043, upper=.00044)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
study = TwoGroundSampledForwardPairStudyDocument(source,
    frequencies=[2e9, 3.5e9, 5e9],
    conductors=dict(positive=metal, negative=metal),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=64, ground_modes=128,
    interpolation_degree=12)
assert TwoGroundSampledForwardPairStudyDocument.loads(study.dumps()).dumps() == study.dumps()
assert len(study.samples()) == 2
```

This example prepares inputs without solving. Call `study.analyze(max_evaluations=2)`
or the common `execute_saved` API to calculate. Lengths are metres, frequencies
Hz and results ohms. The source study frequency must equal the first requested
frequency. Original study/3 and /4 geometry, material-leaf sampling, fixed geometry
constraints and correlation contracts apply. Sampled material models retain
their dispersion rather than being frozen to their first-frequency value.
Whole-surface signal and reference metal laws are fixed across samples.

The evaluation budget counts manufactured rows, including failures, rather than
individual frequencies. It accepts 2..10000 and rejects an insufficient budget
before a solve. The grid cap separately limits per-row work. There are no automatic
retries or refinements. Normalization validates the nominal full grid without
fields; it does not certify every sampled input or numerical solve. Duplicate,
unknown, missing and nonfinite JSON fields are rejected.

One failed frequency makes the entire row unknown. Rows stay in their original
order, including invalid, duplicate and correlated samples. The result retains
resolved materials, exact line inputs, phase, typed failure details and available
current/mesh evidence. Later rows still run; interrupts propagate. All summaries
are suppressed if any row fails. Saved execution is then `incomplete`; requests,
records and projects preserve the result without solving on reopen. Summaries
are descriptive, not production yield, confidence bounds or a continuous-band
guarantee. Existing single-frequency inputs and methods remain unchanged.

The registered physical check uses the two width endpoints above and a uniform
Debye material at 2, 3.5 and 5 GHz, with the existing coated-signal/reference
fixture. It compares each complete grid with separate single-frequency solves,
independent complex-matrix forward impedances and uniform-material identities.
A separate finite assessment on the first row halves the volume mesh, increases
64 to 128 panels and 128 to 256 ground modes, and expands the box from 8 to 16
and 32 mm with 512 and 1024 ground modes. All six R, internal/external L, C, G
and C0 matrix-entry comparisons retain relative 0.01 and absolute zero criteria.
Passing these registered comparisons would establish finite agreement for these
inputs, not measured accuracy, arbitrary-frequency convergence or qualification
of every manufacturing section. For this uniform material, the existing analytic
C0 scaling makes volume-only differences zero; that equality is not independent
evidence of heterogeneous dielectric mesh convergence.

The explicit shared development capability in `dependencies.json` is required;
there is no fallback current method. Linux source and installed checks, browser
Worker, macOS and Windows acceptance are separate evidence.

[Joint acceptance across all sampled frequencies](two_ground_sampled_pair_yield.md).

Manufacturing requests also have independent temporary scopes; see [study reuse](two_ground_study_reuse.md).
