# Saved mixed terminal circuits

`sipi.mixed-circuit/1` saves explicit [mixed terminal boundaries](mixed_termination.md)
through `sipi.mixed_circuit.MixedCircuitDocument`. Ideal voltage/short and
open/current terminals can coexist while all port voltages and currents remain
available. Top-level fields are exactly `schema`, `network`, `basis`, `boundaries`.

`network` accepts the same seven source kinds and metadata contract as
[Norton circuits](norton_circuit.md). `basis` is `single-ended` or the existing
four-port, equal-reference `mixed-mode` conversion. Every final-basis port must
appear exactly once in `boundaries`, regardless of dictionary insertion order.

Each boundary contains exactly:

- `kind='thevenin'`, `source_voltage` [V], `impedance` [ohm]; or
- `kind='norton'`, `source_current` [A], `admittance` [S].

Numbers are finite real values or `{real, imag}` objects with scalar or F-sample
components of identical shape. Canonical values always use `{real, imag}`.
Re Z/Y must be nonnegative; Z=0 is ideal voltage/short and Y=0 ideal current/open.
No source/load defaults, infinity, string loads, extra fields or booleans are
accepted. General, nonuniform and single-frequency grids remain supported;
complex DC is permitted in this frequency-domain contract. No periodic real-DC
or uniform-grid restrictions are added.

```python
import json
import numpy as np
from sipi.mixed_circuit import MixedCircuitDocument
from sipi.execution import normalize_saved, execute_saved

source = dict(kind='rlgc', frequency_hz=[0., 1e8, 2e8], R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length_m=.1, reference_ohms=50., names=['s'])
request = MixedCircuitDocument(source, boundaries={
    'near:s': dict(kind='thevenin', source_voltage=1., impedance=0.),
    'far:s': dict(kind='norton', source_current=0., admittance=0.)})
assert normalize_saved(request.dumps()) == request.dumps()
out = execute_saved(request.dumps(), max_evaluations=3)
response = out['result']['response']
v = np.array(response['voltage_v']['real'])+1j*np.array(response['voltage_v']['imag'])
i = np.array(response['current_a']['real'])+1j*np.array(response['current_a']['imag'])
theta = 2*np.pi*np.array(source['frequency_hz'])*.1*5e-9
np.testing.assert_allclose(v[:, 1], 1/np.cos(theta), atol=1e-12, rtol=0)
np.testing.assert_allclose(i[:, 1], 0., atol=1e-12, rtol=0)
assert response['kinds'] == ['thevenin', 'norton']
json.dumps(out, allow_nan=False)
```

## Budget, identity and results

Normalization does not mesh or solve fields; existing small source algebra may
run. `analyze(max_evaluations=128)` and common execution check F against the
integer 2..10000 budget before field extraction or boundary feedback. Separate
caller limits remain necessary for bytes, port count, field runtime and output
size. No frequency truncation is performed.

The existing extraction helper preserves source metadata and checks exact
frequency, port order, references and single-ended source basis before optional
mixed conversion. Each geometry occurrence is extracted once under the existing
source rules. `MixedCircuitResult` retains canonical `input_json`,
`source_network`, final `network`, `extraction` and `response`
(`MixedTerminatedNetwork`). Python exposes the nested extraction object.

Common execution retains canonical input and returns:

- `coverage='sampled-frequency-boundary'`,
  `power_convention='dc-weight-one-positive-peak'`, original/final networks;
- `response.kinds` in final port order; complex `{real, imag}` arrays
  `source_voltage_v`, `series_impedance_ohms`, `source_current_a`,
  `shunt_admittance_s`, `incident_sqrt_w`, `reflected_sqrt_w`, `voltage_v`,
  `current_a`; unused source/load columns are zero;
- real `condition_number` [F], `boundary_residual` [F,P], `wave_residual` [F];
- `frequency_power_w` arrays for `network`, `terminations`, `sources`.

KVL and KCL residuals retain the API's separate per-port units and
pre-cancellation wave scales. Powers follow each port's actual source topology.
They are independent frequency results, **not** summed into a periodic mean.
Malformed sources, metadata drift, singular/ill-conditioned feedback, overflow
and nonfinite powers propagate as errors instead of partial `complete` results.

Acceptance covers all seven no-field parsers, five exact API/JSON replays, actual
PEC single and paired mixed extraction once with direct agreement at absolute
1e-12, analytic ideal-voltage/open line response, strict tables, budget ordering,
metadata identity, nonperiodic frequency grids, complex DC and failure paths.
Volume adapter counting uses a controlled fixture, not new physics evidence.
The mixed API's independent SciPy/scikit-rf nodal checks remain in the related
regression. The 45th saved schema adds no field model, measured accuracy,
causality/startup certification, application forms or Windows acceptance.

[Common execution](execution.md) · [한국어](../../locales/ko/pages/packages/sipi/mixed_circuit.md)
