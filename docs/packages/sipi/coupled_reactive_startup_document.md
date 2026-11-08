# Saved coupled startup with explicit C and RL loads

`ReactiveRLGCLadderDocument` stores **sipi.coupled-rlgc-startup/4** for the
[external series RL branch API](coupled_reactive_startup.md). It reuses the
physical validator and preserves the exact matrix, time-grid and boundary inputs.

```python
import numpy as np
from sipi import ReactiveRLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((np.minimum(t/2e-9, 1.), -.4*np.minimum(t/3e-9, 1.)))
document = ReactiveRLGCLadderDocument(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_resistance=[0., 37.], load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12,
    load_branch_resistance=[[13., 1.], [1., 9.]],
    load_branch_inductance=np.array([[12., 2.], [2., 8.]])*1e-9)
text = document.dumps()
assert normalize_saved(text) == text and document.samples == 121
out = execute_saved(text, max_evaluations=121)
assert out['input']['schema'] == 'sipi.coupled-rlgc-startup/4'
assert out['status'] == 'complete' and not out['result']['states_included']
response = document.analyze(max_evaluations=121)
assert np.array_equal(response.total_energy,
    response.energy + response.load_capacitor_energy + response.load_branch_energy)
assert response.total_power_balance_relative_error <= 1e-10
```

## Fourteen required keys

The required keys are `schema`, `time_s`, `source_voltages_v`, `R_ohm_per_m`,
`L_h_per_m`, `G_s_per_m`, `C_f_per_m`, `length_m`, `cells`,
`source_resistance_ohm`, `load_resistance_ohm`, `load_capacitance_f`,
`load_branch_resistance_ohm`, `load_branch_inductance_h`. Unknown/duplicate keys,
nonfinite JSON numbers and unsupported versions reject. No matrix is inferred.

Line, waveform, mixed source/load and external C controls match
[capacitive saved v3](coupled_capacitive_startup_document.md). The added branch
R[ohm] is real exactly symmetric finite PSD2x2, allowing zero/rank-one without
negative-eigenvalue repair. Branch L[H] is real exactly symmetric finite SPD2x2
with eigenvalue ratio>1e-12. Singular/zero L, scalar broadcasting, bool/complex
numbers and asymmetry reject. The branch is series R/L in parallel with the
external C and per-conductor loads, with zero initial current; it is not an
arbitrary RLC netlist. Lumped C[F]/L[H] remain separate from line C[F/m]/L[H/m].

Versions1–3 retain their validators and output scopes and reject either added
branch key. They are never upgraded implicitly. This v4 class rejects older
payloads, and explicit zero C/Rbranch remains v4 with required positive Lbranch.

## Validation, budgets and response

Parsing/canonical normalization copy nested inputs and validate without state
propagation. `samples` counts actual time rows. The integer `max_evaluations`
budget (2..10000, default128) is independent of saved1..128 cells, the two
conductors and added current states. Three rows/128 cells fit budget3;
three rows/one cell fail budget2 before propagation. No time horizon or cell
count is changed. Runtime finite-scale errors remain original exceptions.

Analysis checks full input/time/drive identity, node/segment/four-port shapes,
and capacitor/branch current and energy/power/loss shapes. The Python response
retains all copied read-only states. Common execution omits internal line states
by default, while retaining the separated internal-line, external-capacitor and
branch energy/loss terms and combined balance. Byte/diagnostic restrictions
remain unchanged; a failed numerical solve does not become partial success.

Checks cover six matrix/ramp/pulse and six mixed-boundary exact full-state
replays, zero/rank-one load terms, nested copies, no-solve loading, budgets,
malformed outputs and earlier-version preservation. Physical L-C-L, modal
refinement, independent KCL and power criteria are unchanged. This saved format
adds no physical topology, dispersion, measured-board accuracy, browser or
Windows integration beyond the qualified API.

[Reactive API](coupled_reactive_startup.md) · [Capacitive v3](coupled_capacitive_startup_document.md) ·
[Common execution](execution.md) · [한국어](../../locales/ko/pages/packages/sipi/coupled_reactive_startup_document.md)
