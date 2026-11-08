# Saved coupled startup with load capacitance

`CapacitiveRLGCLadderDocument` stores explicit **sipi.coupled-rlgc-startup/3**
for the [passive capacitive-load API](coupled_capacitive_startup.md).
It preserves the constant RLGC matrices, mixed per-conductor resistive boundaries,
zero-state PWL drives and external capacitance without changing the physical API.

```python
import numpy as np
from sipi import CapacitiveRLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((np.minimum(t/2e-9, 1.), -.4*np.minimum(t/3e-9, 1.)))
document = CapacitiveRLGCLadderDocument(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_resistance=[0., 37.], load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12)
text = document.dumps()
assert normalize_saved(text) == text and document.samples == 121
out = execute_saved(text, max_evaluations=121)
assert out['input']['schema'] == 'sipi.coupled-rlgc-startup/3'
assert out['input']['load_resistance_ohm'] == [91., None]
assert out['status'] == 'complete' and not out['result']['states_included']
response = document.analyze(max_evaluations=121)
assert np.all(response.load_capacitor_energy >= 0)
assert np.array_equal(response.total_energy, response.energy + response.load_capacitor_energy)
assert response.total_power_balance_relative_error <= 1e-10
```

## Twelve required fields and explicit v3

The fields are `schema`, `time_s`, `source_voltages_v`, `R_ohm_per_m`,
`L_h_per_m`, `G_s_per_m`, `C_f_per_m`, `length_m`, `cells`,
`source_resistance_ohm`, `load_resistance_ohm`, `load_capacitance_f`.
All fields are required, with no additional keys. The last field is an exactly
symmetric, real, finite PSD 2x2 matrix in **F**, separate from the line matrix
in **F/m**. Zero and rank-one matrices are accepted; negative eigenvalues are
rejected without repair. Scalar broadcasting, booleans, complex values and
asymmetric matrices are rejected.

The other controls follow [mixed saved v2](coupled_boundary_startup_document.md):
explicit 1..128 cells, 2..10000 uniform time rows starting at zero, two zero-first
PWL source columns, conditioned SPD L/C, PSD R/G, finite nonnegative source
resistances and nonnegative/null load entries. Zero means ideal source or short;
null means the resistive load is absent, while the explicit capacitor remains.

The version must be exactly v3. Even a zero-capacitance v3 stays v3. Existing
positive-only v1 and mixed v2 retain their original validators and output scopes;
neither accepts an extra capacitance key or upgrades automatically. Duplicate
keys, unknown versions, nonfinite JSON numbers and malformed nested inputs fail.

## Budget, output and validation

Loading copies inputs and validates controls without propagation. The caller's
integer `max_evaluations` (2..10000, default128) counts actual time rows, separately
from saved cells. Three rows/128 cells fit budget3; three rows/one cell fail
budget2 before propagation. No saved cell count or horizon is changed. Runtime
finite-scale errors remain exceptions; preflight does not certify solvability.

Analysis checks result type, input/time/drive identity, node/segment/four-port
shapes and external capacitor current/energy/power shapes. Python retains all
copied read-only states. Default common execution omits interior states but
includes separate internal-line, external-capacitor and combined energy/power.
Existing byte limits and diagnostic restrictions still apply. A failed solve
is not returned as partial success.

Tests replay six matrix/ramp/pulse cases and six mixed-end cases exactly through
direct API, loaded analysis and common execution, plus zero/rank-one capacitance.
They check copied inputs, no-propagation parsing, budgets, identity guards,
original exceptions and v1/v2 preservation. The API's independent LC, modal
refinement, asymmetric KCL and DC settling checks remain unchanged. This storage
contract adds no arbitrary RLC network, frequency dispersion, Maxwell time-domain
solver, measured-board accuracy or browser/Windows integration.

[Capacitive API](coupled_capacitive_startup.md) · [Mixed v2](coupled_boundary_startup_document.md) ·
[Common execution](execution.md) · [한국어](../../locales/ko/pages/packages/sipi/coupled_capacitive_startup_document.md)

[Saved reactive v4](coupled_reactive_startup_document.md)
