# Saved periodic source/load circuits

`sipi.periodic-circuit/1` saves a [periodic terminated response](periodic_termination.md)
with explicit Thevenin voltage and finite impedance at **every** final-basis
port. `PeriodicCircuitDocument` lives in `sipi.periodic_circuit`. This is distinct
from [periodic-network/1](periodic_document.md), which prescribes incident waves.

The canonical object contains exactly `schema`, `network`, `basis`,
`source_voltages` and `terminations`. The constructor defaults only the basis
to `single-ended`; saved JSON includes every field. No source or load is inferred.

- `network` accepts the existing seven self-contained source kinds described
  in the periodic network contract. The same no-field normalization, real DC,
  uniform frequency, odd N, source metadata and mixed-mode restrictions apply.
- Both tables name every final-basis port exactly once, without omissions or
  extras. Key insertion order does not define port order.
- `source_voltages` values are real finite V constants (DC) or N real samples.
  Explicit zero represents an undriven port. Complex time samples are rejected.
- `terminations` values are real numbers or `{real, imag}` objects. Each
  component is a scalar or an array of F frequency samples; their shapes must
  match. Canonical values always use `{real, imag}`. Impedances are in ohms,
  finite with nonnegative real part, and DC imaginary part exactly zero.
  Booleans, negative resistance, infinity and `open` strings are rejected.
  Zero impedance is supported subject to the existing circuit conditioning gate.

The impedance is the series source/load impedance in the stated port basis.
Frequency-dependent loads represent periodic harmonic feedback; their sampled
passivity and real DC do not certify broadband causality or stability.

```python
import json
import numpy as np
from sipi import LumpedNetworkDocument
from sipi.periodic_circuit import PeriodicCircuitDocument
from sipi.execution import normalize_saved, execute_saved

source = LumpedNetworkDocument([0., 1e8, 2e8], resistance=10., inductance=2e-9)
request = PeriodicCircuitDocument(
    dict(kind='lumped-network', document=source.to_dict()),
    source_voltages={'near': [0., 1., .5, -.5, -1.], 'far': 0.},
    terminations={'near': 50., 'far': 75.})
assert normalize_saved(request.dumps()) == request.dumps()
out = execute_saved(request.dumps(), max_evaluations=5)
assert out['status'] == 'complete'
result = out['result']
assert result['harmonics']['convention'] == 'dc-mean-positive-peak'
v = np.array(result['response']['voltage_v'])
i = np.array(result['response']['current_a'])
np.testing.assert_allclose(np.mean(np.sum(v*i, axis=1)),
    result['mean_power_w']['network'], atol=1e-12, rtol=0)
json.dumps(out, allow_nan=False)
```

## Budget, retained results and failures

`analyze` and common execution count N time samples against `max_evaluations`
(default 128, integer 2..10000), before field/FFT work. Parsing may do existing
small source algebra. Input bytes, port count, field runtime and quadratic
output size require separate caller limits. The grid is not silently shortened.

The original source is extracted once per geometry occurrence under the existing
source rules. A shared helper checks frequency/port/reference/basis identity
before optional mixed-mode conversion. The Python result retains canonical
`input_json`, `source_network`, final `network`, `extraction` and `solution`
(`PeriodicTerminatedResponse` with its original harmonic circuit diagnostics).

The common finite JSON includes canonical input and these result fields:

- `coverage='sampled-periodic-steady-state'`, final `network` and `source_network`;
- `response`: the same time grid and real wave/V/I fields as periodic-network/1;
- `source_voltage_v`, `termination_voltage_v`: real time-by-port arrays;
- `harmonics`: `convention='dc-mean-positive-peak'`, complex `source_voltage_v`,
  `termination_ohms`, `incident_sqrt_w`, `reflected_sqrt_w`, `voltage_v`,
  `current_a`; real `condition_number`, `kvl_residual`, `wave_residual`;
  `frequency_power_w` with `network`, `terminations`, `sources` arrays;
- `mean_power_w`: the **sums** of those harmonic power arrays, in W.

Harmonics follow the network's frequency order and the final port basis. Complex
output uses `{real, imag}`. DC is a mean; positive harmonics are peak phasors,
not RMS. Real time power is V*I with inward current. A dynamic impedance's time
drop comes from inverse-transforming ZI, not pointwise multiplication of tables.
Nested field objects remain available through Python, not the common serializer.

Source/metadata/DC/conditioning/numeric errors propagate. The serializer also
rejects nonfinite harmonic powers or total power, rather than returning a partial
result. `complete` reports computation, not physical or causality acceptance.

Validation covers all source parsers without fields, exact algebraic direct/API/
JSON replay, actual PEC single/pair mixed responses to `1e-12`, extraction counts,
pre-field budgets, metadata drift, strict tables and power overflow. Volume-line
adapter counting uses a controlled fixture, not a new volume accuracy study.
Original periodic network behavior and independent finite-harmonic/SciPy/scikit-rf
circuit checks remain in the related regression. Time means and harmonic power
sums agree to `1e-12` W. There is no startup/TDR/eye/BER or measured-accuracy claim,
and the new schema does not update web forms or Windows acceptance.

[Common execution](execution.md) · [한국어](../../locales/ko/pages/packages/sipi/periodic_circuit.md)
