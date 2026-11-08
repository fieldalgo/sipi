# Saved mixed-boundary two-signal startup

`MixedBoundaryRLGCLadderDocument` stores **sipi.coupled-rlgc-startup/2** for
[explicit mixed ends](coupled_boundary_startup.md). Version2 supports per-conductor
ideal/resistive sources and short/open/resistive loads. The existing
[version1 document](coupled_startup_document.md) remains positive-resistance only;
normalization never changes versions or substitutes one physical API for another.

```python
import numpy as np
from sipi import MixedBoundaryRLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((np.minimum(t/2e-9, 1.), -.4*np.minimum(t/3e-9, 1.)))
document = MixedBoundaryRLGCLadderDocument(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_resistance=[0., 37.], load_resistance=[0., None])
text = document.dumps()
assert normalize_saved(text) == text and document.samples == 121
out = execute_saved(text, max_evaluations=121)
assert out['input']['schema'] == 'sipi.coupled-rlgc-startup/2'
assert out['input']['load_resistance_ohm'] == [0., None]
assert out['status'] == 'complete' and not out['result']['states_included']
response = document.analyze(max_evaluations=121)
assert np.all(response.voltage[:, 2] == 0) and np.all(response.current[:, 3] == 0)
```

## Eleven required fields and explicit v2

The fields are `schema`, `time_s`, `source_voltages_v`, `R_ohm_per_m`,
`L_h_per_m`, `G_s_per_m`, `C_f_per_m`, `length_m`, `cells`,
`source_resistance_ohm`, `load_resistance_ohm`. Every field is required and the
version must be exactly `sipi.coupled-rlgc-startup/2` for this class.

Core controls match the API: real exactly symmetric2x2 PSD R/G, conditioned
SPD L/C with eigenvalue ratio above1e-12, positive length, explicit1..128 cells,
uniform2..10000 time samples starting0 and a `(samples,2)` PWL drive whose
first row is0. No initial energy or impulse is inferred. Both boundary vectors
have two explicit entries. Source resistances are finite>=0, zero=ideal. Each
load entry is finite>=0, zero=short, or JSON null=open. Infinity, scalar
broadcasting, booleans in numeric fields, unknown/duplicate keys, unsupported
versions and invalid shapes/matrices are rejected. SI units and right-slope/
final-hold current conventions follow the mixed API.

A positive-only input may be explicitly saved as v2, retaining the mixed API's
scope; this does not convert existing v1 inputs. Feeding a v1 payload to the
v2 class rejects its version, while common normalization still accepts a valid
v1 through its original validator. Adding zero/null ends to v1 is rejected.
Null and zero load values are preserved and never interchanged.

## Parsing, budget and execution

Loading calls shared mixed-boundary control validation without state propagation,
meshing or waveform work. Canonical strings and nested arrays/matrices are
copied. This preflight does not guarantee representable runtime mass matrices;
extreme underflow remains an ordinary numerical failure during analysis.

`samples` counts actual time rows. `analyze(max_evaluations=128)` and common
execution reject a count above the caller's integer2..10000 budget before
propagation. It is neither doubled for two drives nor replaced by cells/states.
Three rows/128 cells fit budget3; three rows/one cell fail budget2. No cell
count, waveform or time horizon is clamped. These controls do not certify
accuracy, runtime or memory.

Analysis verifies response type, original input, time/drive arrays and
node/segment/four-port dimensions. Python retains the full copied/read-only
response. Common `sipi.execution/1` output contains input, ports and energy/power,
omitting interior states unless serialized explicitly from the Python response.
Existing byte/diagnostic restrictions and original numerical exceptions remain;
there is no partial-success envelope for failed propagation.

Checks cover strict nested parsing, no-solve loading, budgets, identity guards,
finite-scale failures, v1 preservation, six matrix/ramp/pulse full-state replays
and six explicit per-conductor termination combinations. Direct API, loaded
analysis and default common output agree exactly. Underlying coupled RL/Schur
capacitance formulas, modal refinement and independent KCL/DOP853 gates are
unchanged. This saved version adds no reactive loads, arbitrary dispersion,
extra conductors, general TDR/eye/BER, measured-board accuracy or automatic
browser/Windows integration.

[Mixed-boundary API](coupled_boundary_startup.md) · [Positive-only v1](coupled_startup_document.md) ·
[Common execution](execution.md) · [한국어](../../locales/ko/pages/packages/sipi/coupled_boundary_startup_document.md)
