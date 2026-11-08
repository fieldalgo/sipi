# Saved coupled Debye startup inputs

`CoupledDebyeRLGCLadderDocument` stores the explicit
[two-signal Debye circuit](coupled_debye_startup.md) as
`sipi.coupled-debye-rlgc-startup/1`. It validates through the physical input
contract without propagating a state or changing any matrix or pole.

```python
import numpy as np
from sipi import CoupledDebyeRLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

d = CoupledDebyeRLGCLadderDocument([0., 1e-9, 2e-9], [[0., 0.], [1., 0.], [1., 0.]],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -25.], [-25., 150.]]])*1e-12, relaxation_hz=[1e9],
    length=.1, cells=8, source_resistance=[25., 25.], load_resistance=[100., 100.])
text = normalize_saved(d.dumps())
r = CoupledDebyeRLGCLadderDocument.loads(text).analyze(max_evaluations=3)
out = execute_saved(text, max_evaluations=3)
assert out['result'] == r.to_dict()
assert out['input'] == d.to_dict() and out['status'] == 'complete'
assert r.polarization_charge.shape == (3, 9, 1, 2)
```

The exact thirteen required root keys are `schema`, `time_s`, `source_voltages_v`,
`R_ohm_per_m`, `L_h_per_m`, `G_s_per_m`, `C_inf_f_per_m`, `length_m`, `cells`,
`source_resistance_ohm`, `load_resistance_ohm`, `delta_C_f_per_m` and
`relaxation_hz`. Unlike the scalar schema, R/L/G/C_inf are 2x2 matrices,
strengths have shape (poles,2,2), drive (times,2) and each resistance vector (2,).
Unknown keys/versions, duplicate keys, wrong units, nonfinite values and
implicit scalar-to-matrix conversions are rejected.

Exactly symmetric R/G PSD and L/C_inf SPD checks remain in force. Each of
1–2 strength matrices must be SPD with normalized eigenvalue ratio above
1e-12, or exactly zero. Pole order, zero strengths and repeated positive
frequencies are retained. Generic singular strengths and ideal/open/short
end conditions are not enabled by saving a document.

The original 1–128 cells and 2–10000 uniform time samples starting at zero
remain unchanged. `max_evaluations` is an integer 2–10000, default 128, and
bounds actual time rows before propagation; it does not count cells or poles,
resample the drive or extend its horizon. Byte and diagnostic limits of the
[common executor](execution.md) are checked before solving. Normalization does
not certify numerical propagation conditioning or physical convergence.

Replay checks exact response class, complete canonical inputs, time and drive,
node (times,cells+1,2), segment (times,cells,2), four-terminal arrays,
all three polarization arrays (times,cells+1,poles,2) and every energy/rate/loss
vector. Failure preserves the original exception rather than partial success.
Inputs and results are detached; ordinary execution omits internal states,
while `analyze().to_dict(include_states=True)` includes them.

Diagonal, exchange-symmetric and noncommuting ramp/pulse replays match the
complete physical response. One/two/zero/repeated/reordered poles, strict keys,
budget failures, corrupted shapes and original runtime failures are tested.
Scalar Debye documents and wave schemas v1/v2/v3/v4 reject this distinct kind.
This saved engine contract does not establish browser/Windows integration,
general material extraction or measured-board accuracy.

[Physical API](coupled_debye_startup.md) · [Scalar saved inputs](debye_startup_document.md) ·
[한국어](../../locales/ko/pages/packages/sipi/coupled_debye_startup_document.md)

[Explicit saved version5](startup_waves_document.md) adds coupled Debye inputs.
