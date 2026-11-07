# Saved periodic current-source circuits

`sipi.periodic-norton-circuit/1` saves the [periodic Norton response](periodic_norton.md).
`PeriodicNortonCircuitDocument` lives in `sipi.periodic_norton_circuit`.
It explicitly stores every final-basis port's current waveform and parallel
admittance, including open terminals. The canonical fields are exactly `schema`,
`network`, `basis`, `source_currents` and `termination_admittances`.

- `network` accepts the seven existing source kinds in the
  [periodic network contract](periodic_document.md). Normalization never meshes
  fields; existing small network algebra is allowed. The uniform harmonic grid
  begins at exactly real DC, with F≥2, odd N=2F−1, period 1/df and no Nyquist bin.
- `basis` is `single-ended` or the existing four-port, equal-reference
  `mixed-mode` conversion. Tables refer to the final basis, not the original one.
- Both tables name **every** final port exactly once. No source or load default
  is inferred. Key insertion order does not determine network port order.
- `source_currents` values are finite real scalar DC constants or N samples [A].
  Complex samples and booleans are rejected; explicit zero is an undriven port.
- `termination_admittances` values are finite real numbers or `{real, imag}`
  objects [S], with matching scalar or F-sample components. Canonical values
  always use `{real, imag}`. Real parts must be nonnegative; DC imaginary part
  is exactly zero. Zero admittance is an ideal current source or, when its
  source is zero, an open. Infinity and string load names are rejected.

```python
import json
import numpy as np
from sipi.periodic_norton_circuit import PeriodicNortonCircuitDocument
from sipi.execution import normalize_saved, execute_saved

source = dict(kind='rlgc', frequency_hz=[0., 1e8, 2e8], R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length_m=.1, reference_ohms=50., names=['s'])
request = PeriodicNortonCircuitDocument(source,
    source_currents={'near:s': [.001, 0., -.001, 0., .001], 'far:s': 0.},
    termination_admittances={'near:s': .02, 'far:s': 0.})
assert normalize_saved(request.dumps()) == request.dumps()
out = execute_saved(request.dumps(), max_evaluations=5)
result = out['result']
v = np.array(result['response']['voltage_v'])
i = np.array(result['response']['current_a'])
np.testing.assert_allclose(i[:, 1], 0., atol=1e-12, rtol=0)
np.testing.assert_allclose(np.array(result['source_current_a']),
    i+np.array(result['termination_current_a']), atol=1e-12, rtol=0)
np.testing.assert_allclose(np.mean(np.sum(v*i, axis=1)),
    result['mean_power_w']['network'], atol=1e-12, rtol=0)
json.dumps(out, allow_nan=False)
```

## Execution and retained evidence

`analyze` and common execution count N against `max_evaluations` (default 128,
integer 2..10000), before fields or FFT work. No grid truncation is performed.
Parsing can run existing small source algebra; separate caller limits remain
necessary for input bytes, port count, field runtime and output size.

Each source geometry occurrence is extracted once under the existing source
rules. Exact frequency, port order, references and source basis are checked
before optional mixed-mode conversion. `PeriodicNortonCircuitResult` preserves
`input_json`, `source_network`, final `network`, `extraction` and `solution`
(`PeriodicNortonResponse`). Nested field objects are available through Python.

Common execution retains canonical input and serializes:

- `coverage='sampled-periodic-steady-state'`, original and final networks;
- `response`: time [s], period [s], dt [s], waves [sqrt(W)], V and inward I;
- real N×P `source_current_a` and `termination_current_a` time arrays;
- `harmonics` with `convention='dc-mean-positive-peak'`, complex
  `source_current_a`, `termination_admittance_s`, `incident_sqrt_w`,
  `reflected_sqrt_w`, `voltage_v`, `current_a`, and real `condition_number`,
  `kcl_residual`, `wave_residual` diagnostics;
- `harmonics.frequency_power_w` and `mean_power_w`, each keyed by `network`,
  `terminations`, `sources`. The latter sums the periodic harmonic powers.

Complex outputs use `{real, imag}`. Harmonics use the network's frequency and
final-port order; DC is a mean and positive frequencies are peak phasors.
Reactive shunt current is synthesized from Y(f)V(f), not obtained by pointwise
time multiplication. Time-average V*I equals the harmonic power sum. This
periodic mean does not change the general [Norton circuit](norton_circuit.md)
contract, whose unrelated frequency powers are not summed.

Invalid metadata, DC/grid, floating or ill-conditioned feedback, nonfinite
harmonic power and nonfinite power sums raise errors. `complete` only reports
successful computation. Passive shunts do not establish network passivity,
broadband causality, stability, startup behavior or measured-board accuracy.

Acceptance includes seven source parsers without fields, five exact algebraic
API/JSON replays, actual PEC single and paired mixed field extraction once and
agreement at absolute 1e-12, strict tables/budgets/metadata, analytic resistor
current division, an open far terminal and time/power identities. Volume-line
adapter counting uses a controlled fixture, not a new volume physics study.
Existing periodic API analytical/SciPy/scikit-rf checks remain in the related
regression. The 44th schema does not update application forms or Windows support.

[Common execution](execution.md) · [한국어](../../locales/ko/pages/packages/sipi/periodic_norton_circuit.md)
