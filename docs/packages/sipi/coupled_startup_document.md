# Saved two-signal RLGC startup inputs

[Explicit mixed-boundary v2](coupled_boundary_startup_document.md) separately supports ideal/open/short ends; v1 stays positive-only.

`CoupledRLGCLadderDocument` stores `sipi.coupled-rlgc-startup/1` for the
[constant two-signal finite circuit](coupled_startup.md). It replays the same
zero-state PWL propagation with explicit passive matrices and positive resistive
ends. Saving does not infer a dispersive model or change the physical solver.

```python
import numpy as np
from sipi import CoupledRLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((np.minimum(t/2e-9, 1.), -.4*np.minimum(t/3e-9, 1.)))
document = CoupledRLGCLadderDocument(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_resistance=[23., 37.], load_resistance=[91., 113.])
text = document.dumps()
assert normalize_saved(text) == text and document.samples == 121
out = execute_saved(text, max_evaluations=121)
assert out['status'] == 'complete' and out['input']['cells'] == 32
assert out['result']['port_names'] == ['near_0', 'near_1', 'far_0', 'far_1']
assert not out['result']['states_included']
response = document.analyze(max_evaluations=121)
assert response.node_voltage.shape == (121, 33, 2)
```

## Strict matrix contract

All eleven fields are required: `schema`, `time_s`, `source_voltages_v`,
`R_ohm_per_m`, `L_h_per_m`, `G_s_per_m`, `C_f_per_m`, `length_m`, `cells`,
`source_resistance_ohm`, `load_resistance_ohm`. The version is exactly
`sipi.coupled-rlgc-startup/1`; the scalar schema is not interchangeable.

RLGC are finite real exactly symmetric 2x2 matrices in SI units. R/G must be
positive semidefinite without negative-eigenvalue repair. L/C must be positive
definite with normalized eigenvalue ratio above 1e-12. Source voltage has shape
`(samples,2)` and a zero first row; the two source and two load resistances are
finite positive vectors. Zero, null, infinity and scalar broadcasting are not
supported termination shortcuts. Time starts at zero, is strictly increasing
and uniformly spaced within relative 1e-10; 2..10000 samples and 1..128 cells
are explicit. PWL interpolation/final hold and zero stored energy follow the API.

Loading uses shared control validation without state propagation, waveform,
mesh or field work. Unknown/duplicate keys, unsupported versions, nonfinite
values, numeric booleans and invalid matrix/boundary shapes are rejected.
Canonical JSON/dictionary access is detached, including nested matrices and
source arrays. Valid controls do not certify representable later cell scales;
extreme underflow can normalize and then correctly fail during propagation.

## Budget and output identity

`samples` is the number of time rows. `analyze(max_evaluations=128)` and
`execute_saved` check that count against the caller's integer 2..10000 budget
before the solver. The count is not twice the rows because there are two drives,
nor cells or dynamic states. Three samples/128 cells need budget three;
three samples/one cell still fail budget two. The saved cell count is preserved
without clamping or resampling. Limits do not establish convergence, runtime
or memory requirements.

The analysis validates response type, original unit-labelled input, time/drive
arrays, node/segment dimensions and four-column port shapes. Python gets the
full copied/read-only API response. Common execution uses `sipi.execution/1`
and the default finite result dictionary with ports/energy/power, omitting
internal states; request those explicitly from the Python result serializer.
All four currents enter the line. Existing byte limits and characteristic/mode
diagnostic restrictions remain: diagnostics require a top-level line document.

Malformed inputs, budgets and ordinary numerical failures raise their original
exceptions without a partial-success result. Tests replay full internal states
and common output for six actual exchange-symmetric/asymmetric/decoupled
ramp/pulse cases with both sources active and unequal resistive ends where
specified. Strict inputs, nested copies, no-propagation parsing, actual-row
budgets, identity rejection and finite-scale failures are covered. The real
validator participates in the shared saved-schema registry.

Underlying independent modal continuum, distributed ABCD, asymmetric DOP853,
scalar limits and energy gates remain unchanged. This does not support arbitrary
dispersion, extra conductors, ideal/open/short/reactive ends, general TDR/eye/BER
or measured-board accuracy. Application forms and browser/Windows validation
remain separate from engine JSON support.

[Coupled circuit API](coupled_startup.md) · [Common execution](execution.md) ·
[한국어](../../locales/ko/pages/packages/sipi/coupled_startup_document.md)
