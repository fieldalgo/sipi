# Saved three/four-signal RLGC startup inputs

`MulticonductorRLGCLadderDocument` stores explicit
[three/four-signal constant RLGC inputs](multiconductor_startup.md) as
`sipi.multiconductor-rlgc-startup/1`. It preserves the declared signal count,
matrices, resistances, cell count, time samples and source order. It does not
upgrade existing scalar/two-signal schemas or infer signal count.

The object has exactly twelve required root keys:
`schema`, `signals`, `time_s`, `source_voltages_v`, `R_ohm_per_m`, `L_h_per_m`,
`G_s_per_m`, `C_f_per_m`, `length_m`, `cells`, `source_resistance_ohm`,
`load_resistance_ohm`. SI per-metre line quantities remain distinct from
terminal resistances in ohms. Unknown/missing/duplicate keys, unsupported
versions, nonfinite JSON, Boolean numbers and wrong matrix/source shapes
are rejected. `signals` must be integer3/4, not a float or inferred dimension.

Physical matrix conditions remain exact real symmetry, SPD L/C and
SPD-or-exact-zero R/G, every nonzero eigenvalue ratio >1e-12. Nonzero singular
PSD losses, dispersion and other terminal types remain outside this contract.
Validation/canonicalization copies inputs and does not propagate states.

```python
import numpy as np
from sipi import MulticonductorRLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

document = MulticonductorRLGCLadderDocument(
    [0., 1e-9, 2e-9], [[0., 0., 0.], [1., -.4, .2], [1., -.4, .2]],
    signals=3, R=np.diag([20., 23., 26.]), L=np.diag([450., 470., 490.])*1e-9,
    G=np.diag([.002, .0022, .0024]), C=np.diag([210., 220., 230.])*1e-12,
    length=.1, cells=16, source_resistance=[25., 25., 25.],
    load_resistance=[100., 100., 100.])
text = document.dumps()
assert normalize_saved(text) == text
assert document.to_dict()['schema'] == 'sipi.multiconductor-rlgc-startup/1'
assert len(document.to_dict()) == 12
```

```python
loaded = MulticonductorRLGCLadderDocument.loads(text)
r = loaded.analyze(max_evaluations=3)
out = execute_saved(text, max_evaluations=3)
assert out['result'] == r.to_dict()
assert r.voltage.shape == (3, 6)
assert out['input']['signals'] == 3 and out['input']['cells'] == 16
assert not out['result']['states_included']
assert r.to_dict(include_states=True)['states_included']
```

`max_evaluations` counts actual time rows (integer2..10000), independently
of N and the physical1..128 cell bound. The default128 accepts up to128 time
rows. Insufficient budget fails before propagation; it does not reduce cell
count, resample or truncate the source. Common execution also checks input
byte budget and rejects unrelated diagnostics before the solve.

Replay requires the exact response class and identical saved inputs, time
and source. Every array shape is checked: source(times,N), node(times,cells+1,N),
segment(times,cells,N), terminals(times,2*N), and all energy/loss/time diagnostics
(times,). Direct replay can include copied read-only interior states; common
execution deliberately returns the ordinary compact result. Propagation,
finite-scale and identity failures remain errors, not partial successes.

Tests cover N3/4 times coupled/diagonal/lossless times ramp/pulse (twelve
exact full-state replays), strict keys/units/matrices/source/counts, independent
cell/time budgets, copying, state/diagnostic corruption and original failures.
The physical API's independent modal/KCL and convergence criteria are retained.
Existing wave versions1..8 reject this new startup kind; a future wave schema
requires its own explicit six/eight-port contract. No new app/platform or
measured-accuracy claim follows from storage support.

[Common execution](execution.md) · [Physical API](multiconductor_startup.md)

[Explicit saved version9](startup_waves_document.md) adds three/four-signal inputs with six/eight references while preserving prior versions.
