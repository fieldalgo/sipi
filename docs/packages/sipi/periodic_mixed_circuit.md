# Saved periodic mixed source circuits

`sipi.periodic-mixed-circuit/1` stores [periodic mixed sources](periodic_mixed.md)
through `sipi.periodic_mixed_circuit.PeriodicMixedCircuitDocument`. The exact
top-level fields are `schema`, `network`, `basis`, `boundaries`.

The seven self-contained network sources and metadata checks follow the
[mixed circuit contract](mixed_circuit.md). The periodic grid additionally needs
F≥2 uniform harmonics from exactly real DC S, odd N=2F−1 and period 1/df.
`basis` is single-ended or the existing four-port/equal-reference mixed mode.
Every final-basis port must have an explicit boundary; no defaults are inferred.

- Thevenin fields: `kind='thevenin'`, `source_voltage` [V], `impedance` [ohm].
- Norton fields: `kind='norton'`, `source_current` [A], `admittance` [S].
- Source values are finite real DC constants or N real time samples. Complex
  objects, booleans and incorrect shapes are rejected.
- Load values are finite real numbers or `{real, imag}`, scalar or F samples
  with matching component shapes. Canonical loads always use `{real, imag}`.
  Re Z/Y≥0 and exactly real DC are required. Z=0 ideal voltage/short and Y=0
  ideal current/open may coexist. Infinity, string loads and extra fields fail.

```python
import json
import numpy as np
from sipi.periodic_mixed_circuit import PeriodicMixedCircuitDocument
from sipi.execution import normalize_saved, execute_saved

source = dict(kind='rlgc', frequency_hz=[0., 1e8, 2e8], R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length_m=.1, reference_ohms=50., names=['s'])
drive = (.3+.2*np.cos(2*np.pi*np.arange(5)/5)).tolist()
request = PeriodicMixedCircuitDocument(source, boundaries={
    'near:s': dict(kind='thevenin', source_voltage=drive, impedance=0.),
    'far:s': dict(kind='norton', source_current=0., admittance=0.)})
assert normalize_saved(request.dumps()) == request.dumps()
out = execute_saved(request.dumps(), max_evaluations=5)
result = out['result']
v = np.array(result['response']['voltage_v'])
i = np.array(result['response']['current_a'])
np.testing.assert_allclose(v[:, 0], drive, atol=1e-12, rtol=0)
np.testing.assert_allclose(i[:, 1], 0., atol=1e-12, rtol=0)
np.testing.assert_allclose(np.mean(np.sum(v*i, axis=1)),
    result['mean_power_w']['network'], atol=1e-12, rtol=0)
assert result['harmonics']['kinds'] == ['thevenin', 'norton']
json.dumps(out, allow_nan=False)
```

## Execution, diagnostics and power

Parsing never solves fields, although existing small network algebra can run.
`analyze` and common execution count N against `max_evaluations` (default 128,
integer 2..10000) before field/FFT work. They do not shorten the grid. Input
bytes, ports, field runtime and output size need separate caller limits.

The original source is extracted once per geometry occurrence under existing
source rules. Exact frequency, ports, references and original basis are checked
before optional mixed conversion. `PeriodicMixedCircuitResult` retains canonical
`input_json`, `source_network`, final `network`, `extraction` and `solution`
(`PeriodicMixedResponse`). Python exposes nested field objects.

Common execution preserves canonical input and returns finite JSON:

- `coverage='sampled-periodic-steady-state'`, original/final networks;
- `response`: time, period, dt [s], real waves [sqrt(W)], V and inward I;
- N×P real `source_voltage_v`, `source_current_a`, `termination_voltage_v`,
  `termination_current_a`; unused-kind columns remain zero;
- `harmonics`: `convention='dc-mean-positive-peak'`, port-ordered `kinds`, the
  general mixed circuit's four complex source/load arrays and a/b/V/I,
  `condition_number` [F], `boundary_residual` [F,P], `wave_residual` [F];
- `harmonics.frequency_power_w` and `mean_power_w`, keyed by `network`,
  `terminations`, `sources`. Mean power sums the periodic harmonic powers [W].

Complex harmonic output uses `{real, imag}`; DC means and positive peak phasors
follow the original frequency and final port order. Reactive series drops and
shunt currents are synthesized from ZI/YV. Time-average powers use V·I,
drop·I+V·shunt and Vs·I+V·Is, respectively. This periodic sum does not alter the
general mixed circuit's independent-frequency power semantics. Per-port KVL/KCL
normalization retains its separate units and pre-cancellation wave scales.

Malformed inputs, metadata/DC drift, singular feedback and nonfinite powers or
power sums raise errors; `complete` reports computation only. No interpolation,
window, missing DC or causal startup is inferred.

Acceptance covers seven no-field parsers, five exact API/JSON replays, actual
PEC single and paired mixed field extraction once with absolute 1e-12 agreement,
analytic periodic ideal-voltage/open line synthesis, time/harmonic power and
kind-specific columns, strict inputs/budgets/metadata and failure propagation.
Volume adapter counting is controlled, not new physical validation. Independent
SciPy/scikit-rf periodic mixed references and existing general mixed serialization
remain in the related regression. The 46th saved schema adds no new field or
measured accuracy, startup/causality certificate, application form or Windows
acceptance.

[Common execution](execution.md) · [한국어](../../locales/ko/pages/packages/sipi/periodic_mixed_circuit.md)

## Replaying power totals

`mean_power_w` uses Python `sum` on each exported `frequency_power_w` list.
Replaying the saved component values therefore reproduces the total exactly
in the supported Python runtime, without selecting NumPy's different reduction.
The harmonic solve, time-domain power checks and nonfinite-result rejection
remain unchanged. This rounding convention is not an accuracy improvement
to the physical model.
