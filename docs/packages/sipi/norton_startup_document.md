# Saved current-driven startup inputs

`NortonReactiveRLGCLadderDocument` stores **sipi.norton-rlgc-startup/1** for the
[current-source reactive startup API](norton_startup.md). Current samples have
explicit ampere units; source shunt resistances are separate from voltage-source
series resistances. Parsing validates without propagating the circuit.

```python
import numpy as np
from sipi import NortonReactiveRLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((.02*np.minimum(t/2e-9, 1.), -.01*np.minimum(t/3e-9, 1.)))
document = NortonReactiveRLGCLadderDocument(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_shunt_resistance=[None, 37.], load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12,
    load_branch_resistance=[[13., 1.], [1., 9.]],
    load_branch_inductance=np.array([[12., 2.], [2., 8.]])*1e-9)
text = document.dumps()
assert normalize_saved(text) == text and document.samples == 121
out = execute_saved(text, max_evaluations=121)
assert out['input']['schema'] == 'sipi.norton-rlgc-startup/1'
assert out['status'] == 'complete' and not out['result']['states_included']
response = document.analyze(max_evaluations=121)
assert np.array_equal(response.total_energy,
    response.energy + response.load_capacitor_energy + response.load_branch_energy)
assert response.total_power_balance_relative_error <= 1e-10
```

## Fourteen required keys and units

The keys are `schema`, `time_s`, `source_currents_a`, `R_ohm_per_m`, `L_h_per_m`,
`G_s_per_m`, `C_f_per_m`, `length_m`, `cells`, `source_shunt_resistance_ohm`,
`load_resistance_ohm`, `load_capacitance_f`, `load_branch_resistance_ohm`,
`load_branch_inductance_h`. Duplicate/unknown keys, nonfinite numbers and
unsupported versions reject. No missing matrix or unit is inferred.

The physical API's strict validators apply: zero-first-row PWL currents on
2..10000 uniform time rows starting at0, explicit1..128 cells, two conductors,
real exactly symmetric PSD line R/G and conditioned SPD line L/C. External
C[F]/branch R[ohm] allow zero and rank-one PSD matrices; branch L[H] must be
conditioned SPD (eigenvalue ratio>1e-12). Lumped and per-length units stay distinct.

Each source shunt is finite>=0 or null: null is an ideal current source without
a shunt;0 shorts the near node. Per-load resistances retain open/short/finite
semantics. The common output preserves `source_currents_a`, source power
`Vnear*Iinj` and `source_shunt_resistor_loss`; it does not substitute voltage
samples or Thevenin series loss. Line, capacitor and branch energy remain separate.

## Replay and budgets

Construction and loading copy nested inputs. `samples` counts actual time rows.
`max_evaluations` is an integer2..10000 (default128), independent of saved cells
and state count. Three rows/128 cells fit budget3; three rows/one cell fail budget2
before propagation. Time horizon and cell count are never automatically changed.
Byte limits, diagnostics restrictions and original runtime errors are retained.

Analysis checks exact inputs, time and source currents plus node/segment/four-port
and capacitor/branch array shapes. Direct analysis keeps copied read-only internal
states; common execution omits them by default and retains the separate energy,
loss and balance terms. A failed calculation is not partial success.

[Voltage-source saved v4](coupled_reactive_startup_document.md) retains its original
schema and scope. Current/voltage source keys and schemas reject cross-loading;
there is no implicit unit conversion or version upgrade. Existing
[startup-port-waves/1](startup_waves_document.md) still accepts only its six original
nested physical schemas and rejects this Norton schema. [Direct wave analysis](startup_waves.md) is available on the analyzed response;
saved wave adaptation requires explicit `version=2` in
[StartupPortWavesDocument](startup_waves_document.md).

Checks replay six matrix/ramp/pulse and six mixed-boundary cases exactly against
the physical API, plus zero/rank-one loads, no-solve parsing, independent row
budgets, strict inputs, immutable states, output identity and runtime failures.
The underlying independent LC/KCL/modal/settling tests remain required. Saved
replay adds no physical model, measured accuracy or browser/Windows integration.

[Current-source API](norton_startup.md) · [Common execution](execution.md) ·
[한국어](../../locales/ko/pages/packages/sipi/norton_startup_document.md)
