# Saved startup inputs with port-wave references

`StartupPortWavesDocument` stores **sipi.startup-port-waves/1** by default, combining a
complete supported startup document with explicit real port references for
[wave diagnostics](startup_waves.md). Its constructor takes a supported document
object, `z_ref` and an optional explicit integer `version` from2 through9; it copies canonical inputs, not an already computed response.

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

## Explicit version3 for typed mixed sources

`version=3` selects **sipi.startup-port-waves/3**, adding
[sipi.mixed-rlgc-startup/1](mixed_startup_document.md) to the seven version2
schemas. Version1 remains six schemas; version2 remains seven. The constructor
default stays version1, so typed mixed input requires an explicit version3.
Loading preserves the root version and all nested physical/source unit keys;
there is no automatic upgrade or kind conversion. Three root keys,references,
no-recursion rules and original physical budgets remain unchanged.

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

from sipi import StartupPortWavesDocument
wrapped = StartupPortWavesDocument(document, z_ref=[35., 45., 55., 65.], version=3)
assert normalize_saved(wrapped.dumps()) == wrapped.dumps()
result = execute_saved(wrapped.dumps(), max_evaluations=121)
assert result['input']['schema'] == 'sipi.startup-port-waves/3'
assert result['input']['startup']['schema'] == 'sipi.mixed-rlgc-startup/1'
assert result['result']['source_kind'] == 'MixedSourceRLGCLadderResponse'
np.testing.assert_allclose(np.array(result['result']['port_power_w'])[:, :2].sum(axis=1),
    response.source_power - response.source_series_resistor_loss
    - response.source_shunt_resistor_loss, rtol=1e-10, atol=1e-12)
```

Mixed results use four terminal V/I columns and keep the mixed response class
name. Near wave power is supplied source power minus both source series and
shunt losses. Typed V/A drive values are never used as terminal currents.

Sixteen ramp/pulse replays cover all eight version3 source schemas. The original
six match versions1/2/3 and Norton matches versions2/3. Six mixed boundaries and
two homogeneous source-kind limits retain exact waves. Default/v1/v2 rejection
of mixed,strict constructor versions,nested units,recursion,copies,budgets,
result identity and original propagation/cancellation failures are tested.
The former invalid constructor version3 case now tests unsupported999; positive
version3 behavior has its own acceptance. This adds a saved diagnostic contract,
not a new physical propagation model or browser/Windows integration.

## Explicit version 4: scalar Debye inputs

`version=4` selects **sipi.startup-port-waves/4** and accepts the eight version-3
schemas plus **sipi.debye-rlgc-startup/1**. Debye inputs have two explicit real
port references. Pole order, strengths including zero, relaxation frequencies,
C_inf and the entire original time grid remain in the nested document.
Versions 1/2/3 retain their registries and reject Debye; the constructor still
defaults to version1. Recursive wave documents are rejected at every version.

```python
from sipi import DebyeRLGCLadderDocument, StartupPortWavesDocument
from sipi.execution import execute_saved

startup = DebyeRLGCLadderDocument([0., 1e-9, 2e-9], [0., 1., 1.],
    R=20., L=500e-9, G=.002, C_inf=200e-12,
    delta_C=[150e-12, 50e-12], relaxation_hz=[1e9, 1e8],
    length=.1, cells=8, source_resistance=25., load_resistance=100.)
document = StartupPortWavesDocument(startup, z_ref=[35., 75.], version=4)
out = execute_saved(document.dumps(), max_evaluations=3)
assert out['input']['startup'] == startup.to_dict()
assert out['result']['source_kind'] == 'DebyeRLGCLadderResponse'
assert out['result'] == document.analyze(max_evaluations=3).to_dict()
```

Nine kinds with ramp/pulse give eighteen exact replays, including parity with
each eligible prior wave version. Debye six-boundary/one-to-four-pole cases,
actual time-row budgets, nested strict units, corruption guards and physical
exceptions are checked. No implicit extension of time, geometry extraction,
frequency-dependent mode or TDR interpretation is performed.
[Debye saved contract](debye_startup_document.md) defines the underlying limits.

## Explicit version 5: two-signal Debye inputs

`version=5` selects **sipi.startup-port-waves/5** and adds
**sipi.coupled-debye-rlgc-startup/1** to the nine version-4 input kinds.
This kind requires four finite positive real port references, in near_0,
near_1, far_0, far_1 order. Its symmetric matrices, one/two declared poles,
zero strengths, original pole order, finite positive terminal resistances and
PWL time samples remain unchanged. The physical cell/pole limits and actual
time-row budget retain their original meanings. The root still has exactly
schema, startup and z_ref_ohm. No source synthesis, resampling or implicit
nested version upgrade occurs. Default version1 and versions1..4 keep their
original registries and reject coupled Debye inputs.

```python
from sipi import CoupledDebyeRLGCLadderDocument, StartupPortWavesDocument
from sipi.execution import execute_saved
import numpy as np

startup = CoupledDebyeRLGCLadderDocument([0., 1e-9, 2e-9],
    [[0., 0.], [1., -.4], [1., -.4]], R=[[20., 3.], [3., 20.]],
    L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -25.], [-25., 150.]]])*1e-12,
    relaxation_hz=[1e9], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.])
document = StartupPortWavesDocument(startup, z_ref=[35., 45., 55., 65.], version=5)
out = execute_saved(document.dumps(), max_evaluations=3)
assert out['result']['source_kind'] == 'CoupledDebyeRLGCLadderResponse'
assert out['input']['startup'] == startup.to_dict()
assert len(out['result']['incident_sqrt_w'][0]) == 4
```

Twenty ramp/pulse replays cover all ten kinds and each eligible prior version.
Diagonal/exchange/noncommuting matrices with one/zero/repeated/reordered poles,
strict nested units/recursion, copied input, independent time/cell budgets,
output identity and original physical/wave failures are checked. The old v4
unsupported-version5 fixture now uses999; positive v5 has separate coverage.
This is an engine saved contract, not browser/Windows integration or measured
accuracy. [Coupled Debye saved inputs](coupled_debye_startup_document.md) define
physical limits; [terminal waves](startup_waves.md) define reference meaning.

## Explicit version 6: PSD-strength Debye inputs

`version=6` selects **sipi.startup-port-waves/6** and adds
**sipi.psd-coupled-debye-rlgc-startup/1** to the ten version-5 input kinds.
Supply four positive real references in near_0,near_1,far_0,far_1 order.
Singular and nearly singular PSD strengths, declared pole order/zeros/repeats,
finite terminal resistances and original PWL times remain unchanged. There
is no eigenvalue repair, rank clipping, resampling or implicit nested upgrade.
The root retains exactly schema, startup and z_ref_ohm; underlying cell/pole
limits and actual time-row budgets remain distinct. Default version1 and
all versions1..5 retain their registries and reject PSD saved inputs.

```python
from sipi import PSDCoupledDebyeRLGCLadderDocument, StartupPortWavesDocument
from sipi.execution import execute_saved
import numpy as np

startup = PSDCoupledDebyeRLGCLadderDocument([0., 1e-9, 2e-9],
    [[0., 0.], [1., -.4], [1., -.4]], R=[[20., 3.], [3., 20.]],
    L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -150.], [-150., 150.]]])*1e-12,
    relaxation_hz=[1e9], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.])
document = StartupPortWavesDocument(startup, z_ref=[35., 45., 55., 65.], version=6)
out = execute_saved(document.dumps(), max_evaluations=3)
assert out['result']['source_kind'] == 'PSDCoupledDebyeRLGCLadderResponse'
assert out['input']['startup'] == startup.to_dict()
assert len(out['result']['incident_sqrt_w'][0]) == 4
```

Twenty-two ramp/pulse replays cover all eleven kinds and each eligible prior
version. Diagonal rank-one/exchange/noncommuting matrices, one/zero/repeated/
reordered poles, near-singular and null-mode saved inputs are preserved.
Strict units/recursion/copies/budgets/identity and original physical/wave
failures are checked. The old v5 unsupported-version6 fixture uses999; positive
v6 has its own tests. This does not establish app/platform or measured accuracy.
[PSD saved inputs](psd_debye_startup_document.md) define physical validity;
[terminal waves](startup_waves.md) define reference and null-state meaning.

## Explicit version 7: external capacitive Debye inputs

`version=7` selects **sipi.startup-port-waves/7** and adds
**sipi.debye-capacitive-startup/1** to the eleven version-6 input kinds.
Supply four positive real references in near_0,near_1,far_0,far_1 order.
Singular and nearly singular PSD strengths, declared pole order/zeros/repeats,
finite terminal resistances and original PWL times remain unchanged. There
is no eigenvalue repair, rank clipping, resampling or implicit nested upgrade.
The root retains exactly schema, startup and z_ref_ohm; underlying cell/pole
limits and actual time-row budgets remain distinct. Default version1 and
all versions1..6 retain their registries and reject external capacitive Debye inputs.

```python
from sipi import DebyeCapacitiveLadderDocument, StartupPortWavesDocument
from sipi.execution import execute_saved
import numpy as np

startup = DebyeCapacitiveLadderDocument([0., 1e-9, 2e-9],
    [[0., 0.], [1., -.4], [1., -.4]], R=[[20., 3.], [3., 20.]],
    L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -150.], [-150., 150.]]])*1e-12,
    relaxation_hz=[1e9], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.],
    load_capacitance=np.array([[30., -5.], [-5., 30.]])*1e-12)
document = StartupPortWavesDocument(startup, z_ref=[35., 45., 55., 65.], version=7)
out = execute_saved(document.dumps(), max_evaluations=3)
assert out['result']['source_kind'] == 'DebyeCapacitiveLadderResponse'
assert out['input']['startup'] == startup.to_dict()
assert len(out['result']['incident_sqrt_w'][0]) == 4
```

Twenty-four ramp/pulse replays cover all twelve kinds and each eligible prior
version. Diagonal rank-one/exchange/noncommuting matrices, one/zero/repeated/
reordered poles, near-singular and null-mode saved inputs are preserved.
Strict units/recursion/copies/budgets/identity and original physical/wave
failures are checked. The old v6 unsupported-version7 fixture uses999; positive
v7 has its own tests. This does not establish app/platform or measured accuracy.
[External capacitive saved inputs](debye_capacitive_startup_document.md) define physical validity;
[terminal waves](startup_waves.md) define reference and null-state meaning.

External `load_capacitance_f` is in F, distinct from internal F/m material
strengths. Zero/rank-one/full matrices and pulse replays preserve capacitor
current and signed charging/discharging power. Terminal power sums to internal
line energy rate plus losses; total circuit energy additionally includes the
external capacitor. No missing capacitance is inferred or defaulted.

## Explicit version 8: external series RL Debye inputs

`version=8` selects **sipi.startup-port-waves/8** and adds
**sipi.debye-reactive-startup/1** to the twelve version-7 input kinds.
Supply four positive real references in near_0,near_1,far_0,far_1 order.
Singular and nearly singular PSD strengths, declared pole order/zeros/repeats,
finite terminal resistances and original PWL times remain unchanged. There
is no eigenvalue repair, rank clipping, resampling or implicit nested upgrade.
The root retains exactly schema, startup and z_ref_ohm; underlying cell/pole
limits and actual time-row budgets remain distinct. Default version1 and
all versions1..7 retain their registries and reject external series RL Debye inputs.

```python
from sipi import DebyeReactiveLadderDocument, StartupPortWavesDocument
from sipi.execution import execute_saved
import numpy as np

startup = DebyeReactiveLadderDocument([0., 1e-9, 2e-9],
    [[0., 0.], [1., -.4], [1., -.4]], R=[[20., 3.], [3., 20.]],
    L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -150.], [-150., 150.]]])*1e-12,
    relaxation_hz=[1e9], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.],
    load_capacitance=np.array([[30., -5.], [-5., 30.]])*1e-12,
    load_branch_resistance=[[150., 20.], [20., 150.]],
    load_branch_inductance=np.array([[200., 30.], [30., 200.]])*1e-9)
document = StartupPortWavesDocument(startup, z_ref=[35., 45., 55., 65.], version=8)
out = execute_saved(document.dumps(), max_evaluations=3)
assert out['result']['source_kind'] == 'DebyeReactiveLadderResponse'
assert out['input']['startup'] == startup.to_dict()
assert len(out['result']['incident_sqrt_w'][0]) == 4
```

Twenty-six ramp/pulse replays cover all thirteen kinds and each eligible prior
version. Diagonal rank-one/exchange/noncommuting matrices, one/zero/repeated/
reordered poles, near-singular and null-mode saved inputs are preserved.
Strict units/recursion/copies/budgets/identity and original physical/wave
failures are checked. All prior version tests remain unchanged; positive v8 has its own tests. This does not establish app/platform or measured accuracy.
[External series RL saved inputs](debye_reactive_startup_document.md) define physical validity;
[terminal waves](startup_waves.md) define reference and null-state meaning.

External `load_capacitance_f` is in F, distinct from internal F/m material
strengths. Zero/rank-one/full matrices and pulse replays preserve capacitor
current and signed charging/discharging power. Terminal power sums to internal
line energy rate plus losses; total circuit energy additionally includes the
external capacitor. No missing capacitance is inferred or defaulted.

External branch resistance/inductance are required ohm/H matrices; internal
line matrices retain per-length units. Preserve PSD branch resistance,
strict SPD inductance and original zero initial branch current. Far-port
power includes parallel resistor loss, capacitor power, branch energy rate
and branch resistor loss. Zero/rank-one/full branch resistance and pulse
replays preserve the direct result. No branch default or topology inference.


## Explicit version9 for three/four-signal startup

Explicit `version=9` selects `sipi.startup-port-waves/9` and adds only
`sipi.multiconductor-rlgc-startup/1`, for fourteen nested schema kinds.
That kind requires six/eight positive finite real references according to
its explicit validated integer `signals=3/4`. Other kinds keep their two/four
references. Default version1 and all version1..8 registries are unchanged;
they still reject the new kind. Nested versions are never upgraded.

The root keeps exactly `schema`, `startup` and `z_ref_ohm`. The nested
multiconductor document retains twelve strict keys, SI units, matrices,
positive terminal resistances, signal ordering, cell count and time rows.
Input validation does not propagate states; recursive wave documents,
wrong reference counts, inferred signal counts and scalar broadcasts fail.

```python
import numpy as np
from sipi import MulticonductorRLGCLadderDocument, StartupPortWavesDocument
from sipi.execution import normalize_saved, execute_saved

startup = MulticonductorRLGCLadderDocument(
    [0., 1e-9, 2e-9], [[0., 0., 0., 0.], [1., -.4, .2, -.1], [1., -.4, .2, -.1]],
    signals=4, R=np.diag([20., 23., 26., 29.]),
    L=np.diag([450., 470., 490., 510.])*1e-9,
    G=np.diag([.002, .0022, .0024, .0026]),
    C=np.diag([210., 220., 230., 240.])*1e-12,
    length=.1, cells=16, source_resistance=[25.]*4, load_resistance=[100.]*4)
document = StartupPortWavesDocument(startup,
    z_ref=[35., 40., 45., 50., 65., 70., 75., 80.], version=9)
assert normalize_saved(document.dumps()) == document.dumps()
out = execute_saved(document.dumps(), max_evaluations=3)
assert out['input']['schema'] == 'sipi.startup-port-waves/9'
assert out['input']['startup'] == startup.to_dict()
assert out['result']['source_kind'] == 'MulticonductorRLGCLadderResponse'
assert len(out['result']['incident_sqrt_w'][0]) == 8
```

The thirteen original kinds plus both new signal counts give fifteen test
variants and thirty ramp/pulse exact replays, including all eligible prior
versions. Separate coupled/diagonal/lossless tests preserve near/source-R,
far/load-R and whole-line power partitions. Actual time-row budgets remain
independent of cell/signal count; lossless inputs keep their delay-term budget.
Copy, strict units/matrices/signals, duplicate/nonfinite, recursive inputs,
identity corruption and original physical/wave failures are checked. Prior
version tests and the numerical wave/physical implementations stay unchanged.

[Multiconductor saved inputs](multiconductor_startup_document.md) define
physical validity; [terminal waves](startup_waves.md) define port reference
meaning. This storage contract does not establish app/platform integration,
measured accuracy or a general transient field solver.


[Explicit saved wave version10](startup_waves_document_v10.md) adds three/four-signal Debye inputs while preserving versions1–9.
