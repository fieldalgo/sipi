# Saved typed mixed-source startup

`MixedSourceRLGCLadderDocument` saves **sipi.mixed-rlgc-startup/1** for the
[mixed voltage/current API](mixed_startup.md). Each source retains its kind,
waveform unit and series/shunt resistance meaning. Parsing validates without
propagating the circuit; no older homogeneous schema is repurposed.

```python
import numpy as np
from sipi import MixedSourceRLGCLadderDocument

time = np.linspace(0., 12e-9, 121)
sources = [dict(kind='voltage', voltage_v=np.minimum(time/2e-9, 1.),
                series_resistance_ohm=0.),
           dict(kind='current', current_a=-.008*np.minimum(time/3e-9, 1.),
                shunt_resistance_ohm=None)]
document = MixedSourceRLGCLadderDocument(time, sources,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]], C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=16, load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12,
    load_branch_resistance=[[13., 1.], [1., 9.]],
    load_branch_inductance=np.array([[12., 2.], [2., 8.]])*1e-9)
from sipi.execution import normalize_saved, execute_saved
text = document.dumps()
assert normalize_saved(text) == text and document.samples == 121
out = execute_saved(text, max_evaluations=121)
assert out['status'] == 'complete'
assert out['input']['schema'] == 'sipi.mixed-rlgc-startup/1'
assert out['result']['source_units'] == ['V', 'A']
response = document.analyze(max_evaluations=121)
assert response.source_kinds == ('voltage', 'current')
assert response.source_units == ('V', 'A')
np.testing.assert_array_equal(response.voltage[:, 0], sources[0]['voltage_v'])
np.testing.assert_array_equal(response.current[:, 1], sources[1]['current_a'])
assert response.total_power_balance_relative_error <= 1e-10
assert not response.to_dict()['states_included']
assert np.all(response.source_series_resistor_loss == 0.)
assert np.all(response.source_shunt_resistor_loss == 0.)
```

## Thirteen root keys and typed sources

Required keys are `schema`, `time_s`, `sources`, `R_ohm_per_m`, `L_h_per_m`,
`G_s_per_m`, `C_f_per_m`, `length_m`, `cells`, `load_resistance_ohm`,
`load_capacitance_f`, `load_branch_resistance_ohm`, `load_branch_inductance_h`.
Unknown/missing/duplicate keys, unsupported versions and nonfinite JSON numbers
reject. `sources` contains exactly two explicit dictionaries:

| kind | Required waveform | Required resistance |
|---|---|---|
| voltage | `voltage_v` in V | `series_resistance_ohm`, finite>=0 |
| current | `current_a` in A | `shunt_resistance_ohm`, finite>=0 or null |

These three per-source keys are exact. A wrong-kind key is rejected, not converted.
Voltage0ohm prescribes near V; current0ohm shorts the near node; current null
removes the shunt. Both homogeneous and mixed orders are preserved in this schema.

All physical validators are shared: zero-first one-dimensional waveforms matching
2..10000 uniform time rows starting0, explicit1..128 cells, positive length,
exactly symmetric PSD line R/G and conditioned SPD line L/C, PSD external C/Rbranch
and conditioned SPD Lbranch. Zero/rank-one load C/R is preserved without repair.
Lumped F/H and line F/m/H/m remain separate; no matrix is inferred.

## Replay, result and budgets

Construction/loading copy nested typed inputs. `samples` counts actual time rows.
Integer `max_evaluations` (2..10000,default128) remains independent of cells,
source kind and state count. Three rows/128cells fit budget3; three rows/onecell
fail budget2 before propagation. No horizon,grid,source kind or version changes.
The original byte/diagnostic limits and runtime numerical exceptions remain.

Analysis checks response type,complete canonical inputs,time,source_values/kinds/
units,node/segment/four-port shapes,source-series/shunt loss shapes and external
capacitor/branch current/energy/rate/loss shapes. Direct results keep copied
read-only internal states. Common execution omits internal line states by default,
retaining typed inputs,V/A unit metadata,separate source losses and all original
line/external energy diagnostics. A failed solve is not a partial success.

Original voltage and Norton schemas keep their own scopes and reject cross-loading.
The [saved wave wrappers](startup_waves_document.md),both version1 and2,continue
rejecting this new mixed schema. [Direct wave diagnostics](startup_waves.md) accept the analyzed mixed response;
saved wave adaptation still requires an explicit subsequent version.

Checks cover six matrix/ramp/pulse full-state replays,eight source/boundary cases,
all required keys,strict nested units,duplicates,no-solve parsing,copies,budgets,
output corruption,zero/rank-one loads,readonly results and original runtime errors.
The physical analytic/KCL/continuous-line criteria remain those of the API.
This adapter adds no physical model,measurement validation or browser/Windows
integration beyond the qualified explicit constant finite circuit.

[Mixed-source API](mixed_startup.md) · [Common execution](execution.md) ·
[한국어](../../locales/ko/pages/packages/sipi/mixed_startup_document.md)
