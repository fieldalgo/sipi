# Saved Debye startup inputs

`DebyeRLGCLadderDocument` saves the explicit scalar
[Debye startup circuit](debye_startup.md) as `sipi.debye-rlgc-startup/1`.
Normalization validates and copies inputs without propagating states.

```python
from sipi import DebyeRLGCLadderDocument
from sipi.execution import execute_saved, normalize_saved

d = DebyeRLGCLadderDocument([0., 1e-9, 2e-9], [0., 1., 1.],
    R=20., L=500e-9, G=.002, C_inf=200e-12,
    delta_C=[150e-12, 50e-12], relaxation_hz=[1e9, 1e8],
    length=.1, cells=8, source_resistance=25., load_resistance=100.)
text = normalize_saved(d.dumps())
r = DebyeRLGCLadderDocument.loads(text).analyze(max_evaluations=3)
out = execute_saved(text, max_evaluations=3)
assert out['result'] == r.to_dict()
assert out['input'] == d.to_dict()
assert out['status'] == 'complete'
```

The exact thirteen root keys are `schema`, `time_s`, `source_voltages_v`,
`R_ohm_per_m`, `L_h_per_m`, `G_s_per_m`, `C_inf_f_per_m`, `length_m`, `cells`,
`source_resistance_ohm`, `load_resistance_ohm`, `delta_C_f_per_m` and
`relaxation_hz`. Every key is required; unknown keys, versions, duplicate JSON
keys and nonfinite numbers are rejected. Pole strengths remain F/m, not
relative permittivity. No legacy `C_f_per_m`, untyped material conversion,
implicit pole fit or version upgrade is accepted.

The physical API's 1–4 declared poles, zero strengths, repeated frequencies,
input order, 1–128 cells and 2–10000 uniform time rows are preserved exactly.
Source zero is an ideal voltage source; load zero is a short and JSON `null`
an open. Arrays and dictionaries are copied. Validation does not check actual
propagation conditioning or spatial/time convergence; runtime finite-scale
and physical failures retain their original exceptions.

`max_evaluations` bounds actual time rows before propagation, independently
of cells and pole counts. It defaults to 128 and accepts integers 2–10000.
It never resamples the drive, reduces cells, removes declared poles or extends
the horizon. The common executor also checks input byte limits and rejects
inapplicable diagnostics before solving.

Replay checks the exact response type, canonical physical inputs, time and
drive, node/segment/two-terminal shapes, all three polarization state shapes,
and each energy/rate/loss vector. A changed input or shape cannot produce a
successful saved response. Ordinary execution omits internal arrays; direct
`analyze().to_dict(include_states=True)` includes them. Six boundaries with
ramp/pulse drives reproduce the physical API's complete states and diagnostics;
one/two/four-pole, repeated-pole and zero-strength requests are tested too.

Existing constant-RLGC documents and wave schemas v1/v2/v3 do not implicitly
accept this model. This engine-level saved contract does not establish
browser/Windows integration, general dielectric extraction or measured accuracy.

[Common execution](execution.md) · [Physical API](debye_startup.md) ·
[한국어](../../locales/ko/pages/packages/sipi/debye_startup_document.md)

[Saved waves version4](startup_waves_document.md) explicitly wraps this request.
