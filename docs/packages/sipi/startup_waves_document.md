# Saved startup inputs with port-wave references

`StartupPortWavesDocument` stores **sipi.startup-port-waves/1**, combining a
complete supported startup document with explicit real port references for
[wave diagnostics](startup_waves.md). Its constructor takes a supported document
object and `z_ref`; it copies canonical inputs, not an already computed response.

```python
import numpy as np
from sipi import LosslessStartupDocument, StartupPortWavesDocument
from sipi.execution import normalize_saved, execute_saved

startup = LosslessStartupDocument(np.linspace(0., 8e-9, 801),
    source_times=[0., 1e-9], source_voltages=[0., 1.], z0_ohm=50., delay_s=1e-9,
    source_resistance=50., load_resistance=None, max_terms=100)
document = StartupPortWavesDocument(startup, z_ref=[35., 75.])
text = document.dumps()
assert normalize_saved(text) == text
# Matched source requires one forward delay term, despite 801 output rows.
out = execute_saved(text, max_evaluations=2)
assert out['status'] == 'complete' and out['input']['startup'] == startup.to_dict()
assert out['input']['startup']['max_terms'] == 100
assert len(out['result']['time_s']) == 801
waves = document.analyze(max_evaluations=2)
assert waves.power_balance_relative_error <= 1e-10
np.testing.assert_array_equal(waves.z_ref, [35., 75.])
```

## Three required root keys

The root keys are exactly `schema`, `startup`, `z_ref_ohm`. Nested `startup` is
one complete original payload: `sipi.lossless-startup/1`, `sipi.rlgc-startup/1`,
or `sipi.coupled-rlgc-startup/1`, `/2`, `/3`, `/4`. Original validators and versions
are retained. Other schemas, unsupported versions and recursively nested wave
documents reject. There is no implicit upgrade or inferred physical input.

`z_ref_ohm` has two positive finite real entries for scalar documents and four
for coupled documents. Scalars, complex/bool/nonfinite or nonpositive entries,
wrong lengths/shapes, missing/unknown keys and duplicate keys at any JSON depth
reject. Parsing validates the complete nested document and references without
propagation or wave conversion. Canonical nested arrays and references are copied.

## Preserve the original budget meaning

The caller's integer `max_evaluations` (2..10000, default128) is passed unchanged
to the original document. Lossless startup counts actual required forward delay
terms, independently of its saved `max_terms` cap and output row count. Finite
RLGC startup counts actual time rows, independently of explicit cells, conductors
and wave arrays. A matched lossless source with1001 rows fits budget2; three
RLGC rows with128 cells fit budget3 but fail budget2. Nothing is clamped or
multiplied by the port count. These limits do not certify runtime or convergence.

Original document checks verify physical response identity before wave conversion.
The wrapper then checks wave result type, exact time/V/I/reference/name/source-kind
identity and incident/reflected/power shapes. Python returns copied read-only
`StartupPortWaves`. Common execution keeps the complete nested input and finite
wave output, with the same byte and diagnostic restrictions as other saved inputs.
Original propagation, scale and wave-cancellation failures remain exceptions;
there is no partial-success output or automatic clipping.

Twelve direct/loaded/common replays cover all six supported nested versions with
ramp and pulse inputs. Other checks cover old normalization preservation,
no-propagation parsing, nested copies/keys, reference validation, both original
budget meanings, malformed result identity and numerical failure propagation.
The independent delayed-reflection/phasor/power criteria remain those of the
wave API. This is a saved diagnostic contract, not an added physical solver,
modal extraction, general TDR inversion or browser/Windows integration.

[Port waves](startup_waves.md) · [Lossless storage](startup_document.md) ·
[Reactive storage](coupled_reactive_startup_document.md) · [Common execution](execution.md) ·
[한국어](../../locales/ko/pages/packages/sipi/startup_waves_document.md)
