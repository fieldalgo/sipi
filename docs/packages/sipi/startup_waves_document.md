# Saved startup inputs with port-wave references

`StartupPortWavesDocument` stores **sipi.startup-port-waves/1** by default, combining a
complete supported startup document with explicit real port references for
[wave diagnostics](startup_waves.md). Its constructor takes a supported document
object, `z_ref` and optional explicit `version=2`; it copies canonical inputs, not an already computed response.

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
one complete original payload. Version1 accepts: `sipi.lossless-startup/1`, `sipi.rlgc-startup/1`,
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

## Explicit version2 for current sources

`version=2` selects **sipi.startup-port-waves/2**, whose closed registry accepts
the same six original schemas plus [sipi.norton-rlgc-startup/1](norton_startup_document.md).
Its root still has exactly three keys. Default/explicit version1 continues
rejecting Norton. There is no automatic version upgrade based on the input;
bool, float, string and unsupported constructor versions reject. Loading and
normalization preserve the root version and every nested physical version.
Version2 containing an older voltage-source document stays version2.

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

from sipi import StartupPortWavesDocument
wrapped = StartupPortWavesDocument(document, z_ref=[35., 45., 55., 65.], version=2)
assert normalize_saved(wrapped.dumps()) == wrapped.dumps()
result = execute_saved(wrapped.dumps(), max_evaluations=121)
assert result['input']['schema'] == 'sipi.startup-port-waves/2'
assert result['input']['startup']['schema'] == 'sipi.norton-rlgc-startup/1'
assert result['result']['source_kind'] == 'NortonReactiveRLGCLadderResponse'
np.testing.assert_allclose(np.array(result['result']['port_power_w'])[:, :2].sum(axis=1),
    response.source_power - response.source_shunt_resistor_loss, rtol=1e-10, atol=1e-12)
```

Norton uses four explicit references and its actual time-row budget. The output
uses terminal currents, not injected source currents, and preserves the Norton
source class name. Near wave power equals supplied power minus source-shunt loss.
Physical propagation/energy and the wave formulas are unchanged; the finite
wave result does not additionally return the physical response's internal states.

Fourteen ramp/pulse replays cover all seven nested schema kinds in version2;
the original six give the same wave output in version1 and2. Six Norton mixed
boundaries, strict version/unit/recursion checks, no-propagation parsing, copied
inputs, original delay-term/time-row budgets, output identity and runtime failures
are checked. Original version1 tests remain unchanged. No extra physical scope,
source convergence, measurement validation or application integration is implied.
