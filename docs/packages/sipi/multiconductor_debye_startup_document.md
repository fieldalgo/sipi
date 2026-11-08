# Saved multiconductor Debye startup

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_debye_startup_document.md)

`MulticonductorDebyeRLGCLadderDocument` saves the explicit
[three/four-signal Debye circuit](multiconductor_debye_startup.md) as
`sipi.multiconductor-debye-rlgc-startup/1`. Construction, loading and
normalization validate inputs without state propagation. No inferred signal
count, material, pole, source, reference or cell count is introduced.

```python
import numpy as np
from sipi import MulticonductorDebyeRLGCLadderDocument
from sipi.execution import normalize_saved

t = np.linspace(0., 4e-9, 41)
arguments = dict(time=t,
    source_voltages=np.minimum(t/1e-9, 1.)[:, None]*[1., -.4, .2],
    signals=3, R=np.diag([20., 23., 26.]),
    L=np.diag([450., 480., 510.])*1e-9,
    G=np.diag([.002, .0022, .0024]),
    C_inf=np.diag([210., 220., 230.])*1e-12,
    delta_C=np.array([np.diag([130., 143., 156.]), np.zeros((3, 3))])*1e-12,
    relaxation_hz=[8e7, 7e8], length=.1, cells=4,
    source_resistance=[25.]*3, load_resistance=[100.]*3)
document = MulticonductorDebyeRLGCLadderDocument(**arguments)
text = document.dumps()
assert document.to_dict()['schema'] == 'sipi.multiconductor-debye-rlgc-startup/1'
assert normalize_saved(text) == text
assert MulticonductorDebyeRLGCLadderDocument.loads(text).dumps() == text
```

Exactly14 keys are required: `schema`, `signals`, `time_s`, `source_voltages_v`,
`R_ohm_per_m`, `L_h_per_m`, `G_s_per_m`, `C_inf_f_per_m`, `delta_C_f_per_m`,
`relaxation_hz`, `length_m`, `cells`, `source_resistance_ohm`,
`load_resistance_ohm`. Unknown/missing keys, alternate units, duplicate JSON keys,
nonfinite numbers and unsupported versions are rejected. Scalar/list dimensions,
exact symmetry, SPD-or-zero restrictions, zero first drive row and positive
finite pole/resistance conditions remain those of the direct API.

`signals` is explicitly3 or4; cells1..64; one/two declared poles; uniform
2..10000 time samples starting0. `analyze(max_evaluations=...)` counts actual
time rows, separately from cells, signal count and active states. The budget
is an integer2..10000 (default128); exceeding it fails before propagation.
Stored cells and time values remain unchanged. The common executor also applies
its existing input-byte limit and rejects unrelated diagnostics before a solve.
These limits do not guarantee convergence, execution time or memory.

```python
from sipi import multiconductor_debye_rlgc_ladder_response
from sipi.execution import execute_saved

direct = multiconductor_debye_rlgc_ladder_response(**arguments)
replayed = document.analyze(max_evaluations=41)
assert replayed.to_dict(include_states=True) == direct.to_dict(include_states=True)
execution = execute_saved(text, max_evaluations=41)
assert execution['status'] == 'complete'
assert execution['result'] == direct.to_dict()
assert execution['input']['cells'] == 4
assert not replayed.polarization_charge[:, :, 1].any()
```

Execution calls the existing engine once. Before returning it checks exact
result type, all normalized input values, time and source samples. Source,
node/segment and terminal arrays must have the declared dimensions; all three
polarization arrays are(time,node,pole,signal), with the declared pole count
even for zero strengths. Every other diagnostic array has one value per time.
The direct result is copied/read-only; normalized/exported dictionaries are
detached. Original numerical/propagation errors are retained. The adapter does
not repair a solver result, infer accuracy or turn a failure into partial success.

[Common saved execution](execution.md) returns the usual `sipi.execution/1`
envelope and the engine's state-free result export. Direct `analyze` allows
the caller to request full states through the result's `to_dict`. Result exports
are distinct from executable saved requests. Existing startup-wave versions1–9
and prior saved circuit kinds do not implicitly accept this new document.

Validation includes full-state direct/saved/common replays for3/4 signals,
coupled/diagonal/zero-RG models and ramp/pulse sources; one/zero/reordered poles;
every required key, strict matrix/pole/count/units and duplicate/nonfinite input;
one engine call, pre-propagation row/byte/diagnostic budgets; all state and
diagnostic shape guards and original runtime errors. The underlying
[independent KCL, modal and convergence evidence](multiconductor_debye_startup.md)
remains the numerical basis. No numerical kernel, tolerance, new runtime
dependency, physical model, application or platform support changes here.
