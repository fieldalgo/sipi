# Saved finite RLGC startup inputs

`RLGCLadderDocument` stores `sipi.rlgc-startup/1` and connects the
[finite passive circuit API](rlgc_startup.md) to common execution. It preserves
explicit cells, uniform time samples, PWL source and initially zero stored
energy. Its constant scalar RLGC model and physical acceptance gates are unchanged.

```python
import numpy as np
from sipi import RLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

t = np.linspace(0., 12e-9, 121)
document = RLGCLadderDocument(t, np.minimum(t/2e-9, 1.),
    R=20., L=500e-9, G=.002, C=200e-12, length=.1, cells=128,
    source_resistance=25., load_resistance=100.)
text = document.dumps()
assert normalize_saved(text) == text and document.samples == 121
out = execute_saved(text, max_evaluations=121)
assert out['status'] == 'complete' and out['input']['cells'] == 128
assert out['result']['power_balance_relative_error'] <= 1e-10
assert not out['result']['states_included']
assert 'node_voltage_v' not in out['result']
response = document.analyze(max_evaluations=121)
assert response.node_voltage.shape == (121, 129)
```

## Strict saved contract

All eleven fields are required: `schema`, `time_s`, `source_voltages_v`,
`R_ohm_per_m`, `L_h_per_m`, `G_s_per_m`, `C_f_per_m`, `length_m`, `cells`,
`source_resistance_ohm`, `load_resistance_ohm`. The schema is exactly
`sipi.rlgc-startup/1`. Unknown/duplicate keys, unsupported versions, nonfinite
numbers and booleans in numeric fields are rejected. Explicit null load is
open; zero is short. Zero source resistance is an ideal source.

Shared API control validation runs while loading, without state propagation,
waveforms, meshing or fields. Time has 2..10000 samples, starts at zero and is
strictly increasing and uniformly spaced within relative 1e-10. The source has
the same shape, starts at zero, interpolates linearly and holds its last value.
R/G are nonnegative, L/C/length positive, and resistances nonnegative finite
SI scalars. Canonical strings and dictionary access are detached from caller
arrays. Preflight does not prove that extreme cell scales, matrix coefficients
or later states remain representable; runtime finite-scale/energy guards remain.

## Sample budget and unchanged cells

`samples` is the actual output-time count. `analyze(max_evaluations=128)` and
`execute_saved` require this count to fit the caller's integer 2..10000 budget
**before any state propagation**. `cells` remains an independent explicit
integer 1..256. The example requires 121 evaluations while preserving 128 cells;
three samples with 256 cells need budget three, while three samples with one
cell still fail budget two. Neither time nor cells are clamped or resampled.
The budget is not the number of states, time steps internal to a reference
integrator, elapsed time or memory. It does not establish convergence.

`analyze()` returns the full immutable API response and verifies saved inputs,
time/source arrays and node/segment cell dimensions. Common execution returns
`sipi.execution/1` with the default API dictionary: input, ports, energy and
power diagnostics, without internal state arrays. Python callers can explicitly
serialize those arrays with `response.to_dict(include_states=True)`.
Both port currents enter the line; segment current points from source to load.

Existing byte limits and diagnostic restrictions apply: characteristic/mode
diagnostics require a top-level transmission/volume line. Malformed input,
exceeded budget and ordinary numerical failures raise their original exceptions,
without a partial-success envelope. A saved document with extreme underflowing
cell scales may normalize successfully yet correctly fail during analysis.

Acceptance covers strict parsing, detached copies, no-propagation loading,
actual-sample budgets with preserved cells, runtime failure and result identity.
Twelve lossy ramp/pulse cases across ideal/resistive sources and short/open/
resistive loads reproduce raw API states and common output exactly. Existing
independent RL/LC, DOP853, distributed-line and spatial-refinement gates stay
unchanged, including the documented ideal/open 128-cell failure and 256-cell
acceptance. The real validator is included in the common schema registry.

This does not extend the physical model to dispersive/coupled lines, reactive
external loads, general TDR/eye/BER or measured-board accuracy. A saved schema
does not supply an application form or verify browser/Windows integration.

[Finite circuit API](rlgc_startup.md) · [Common execution](execution.md) ·
[한국어](../../locales/ko/pages/packages/sipi/rlgc_startup_document.md)
