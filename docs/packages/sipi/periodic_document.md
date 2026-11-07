# Saved periodic network response

`sipi.periodic-network/1` saves a network source, explicit output basis,
incident power-wave samples and an optional discrete impulse request. It uses
the [periodic API](periodic.md) unchanged: real DC, uniform harmonics, odd
sample count and circular periodic steady state. It supplies no missing DC,
window, interpolation, startup transient or source/termination inference.

`PeriodicNetworkDocument` is in `sipi.periodic_document`. The canonical object
has exactly `schema`, `network`, `basis`, `incident` and `include_impulse`.
Constructor defaults are `basis='single-ended'` and `include_impulse=False`;
saved JSON explicitly contains both. Unknown fields/versions, duplicate keys,
nonfinite numbers, boolean/nonnumeric samples and malformed ports are rejected.

## Source and incident contract

`network` reuses the existing self-contained source kinds:
`rlgc`, `touchstone` (embedded text), `lumped-network`, `transmission-line`,
`volume-line`, `network-transform` and `network-assembly`.
Their model, nesting and metadata restrictions remain in force. File names,
URLs, expressions and automatic external reads are not accepted sources.

`incident` is an object with **every final-basis port name exactly once**, no
omitted ports or extra names. Each value is a real finite array of length
`N = 2*F-1` in sqrt(W), where `F` is the source frequency count. Object insertion
order does not define port order. Explicit zero arrays represent undriven ports.
These are incident waves at the reference planes; they are not Thevenin source
voltages. Nonmatched sources and loads must be included in the source network
or separately modeled; this request does not solve their feedback implicitly.

`basis='mixed-mode'` requires four equal-reference single-ended source ports
ordered near+/near-/far+/far-. Incident keys then are
`d_near`, `d_far`, `c_near`, `c_far`. The existing mixed-mode conversion supplies
the differential/common reference impedances. Other source ports use
`basis='single-ended'`. `include_impulse` must be a JSON boolean.

```python
import json
from sipi import LumpedNetworkDocument
from sipi.periodic_document import PeriodicNetworkDocument
from sipi.execution import normalize_saved, execute_saved

source = LumpedNetworkDocument([0., 1e8, 2e8], resistance=10., inductance=2e-9)
request = PeriodicNetworkDocument(
    dict(kind='lumped-network', document=source.to_dict()),
    incident={'near': [0., 1., .5, -.5, -1.], 'far': [0.]*5},
    include_impulse=True)
text = normalize_saved(request.dumps())
assert text == request.dumps()
output = execute_saved(text, max_evaluations=5)
assert output['status'] == 'complete'
assert output['result']['coverage'] == 'sampled-periodic-steady-state'
assert len(output['result']['response']['time_s']) == 5
assert output['result']['impulse'] is not None
json.dumps(output, allow_nan=False)
```

## Validation, budget and result

Normalization validates frequencies, period representation, incident count and
port metadata without meshing fields. Existing RLGC/lumped validators can do
small algebra. If S is already available, complex DC is rejected immediately;
field-derived S is checked after extraction. Source validity rules may reject
DC themselves (for example, a high-frequency surface approximation must not
be extended to DC merely to satisfy this request).

`analyze(max_evaluations=128)` and `execute_saved(..., max_evaluations=128)`
count **N time samples**, checking the existing integer budget range 2..10000
before field extraction or FFT work. They do not silently shorten the grid.
This is not a bound on field runtime, port count, quadratic S/impulse size,
or parsing algebra. The transport's input-byte budget and caller process
limits remain separate.

Each saved geometry occurrence follows the existing source extraction once.
Frequency, port order, references and single-ended source basis must still
match saved metadata after extraction, before optional mixed-mode conversion.
The Python result retains `input_json`, `source_network`, final `network`,
`extraction`, `response` and optional `impulse`.

The common finite JSON result contains both networks (with explicit names,
basis, references and complex S), plus:

- `coverage='sampled-periodic-steady-state'`;
- `response.time_s`, `period_s`, `dt_s`, `incident_sqrt_w`, `reflected_sqrt_w`,
  `voltage_v`, `current_a` (time by final-basis port);
- `impulse=null` or `{lag_s, weights}` with dimensionless weights ordered
  lag by output port by input port, on the same period and time step.

The common output retains canonical input but omits the nested field objects;
use the Python result for those. `complete` means the transform completed,
not physical accuracy or causality acceptance. Source, metadata, DC and numeric
scale errors propagate; they do not become partial successful responses.

Tests exercise all seven source kinds without field work during normalization,
five algebraic sources through exact direct/saved replay, actual PEC single/pair
extraction and mixed-mode response to absolute `1e-12`, plus source call counts,
budget guards and metadata drift. Volume-line adapter call counting uses a
controlled network fixture; it is not a new volume-extraction accuracy test.
The periodic API's independent finite DFT, scikit-rf and SciPy comparisons remain
in the related suite. EN/KO examples and exact installed artifacts are checked.
JSON availability does not update web forms, Worker parity or Windows support.

[Common execution](execution.md) · [한국어](../../locales/ko/pages/packages/sipi/periodic_document.md)
