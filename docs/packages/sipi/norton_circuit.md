# Saved Norton circuits

`sipi.norton_circuit.NortonCircuitDocument` stores a complete frequency-domain
current-source boundary problem as **`sipi.norton-circuit/1`**. It reuses the
[Norton API](norton_termination.md) and the [shared execution entry point](execution.md).
It does not add a field model or a periodic time-domain assumption.

The exact top-level fields are `schema`, `network`, `basis`, `source_currents`
and `termination_admittances`. Both tables must explicitly name **every port
in the final basis**, including zero source currents and open admittances.
The Python solver's missing-port defaults are not implicit in a saved document.
Inputs use SI units: currents in A, parallel admittances in S.

Complex values use `{real, imag}` with matching finite scalar or frequency-array
shapes; a real scalar/array is canonicalized to that form. Each array has F
entries. Booleans, missing/extra/duplicate keys, nonfinite values, unknown ports,
unregistered versions and negative admittance real parts are rejected.
`Y=0, Is=0` explicitly means open; `Y=0, Is!=0` is an ideal current source.
The strings `open`/`short` and infinite admittances are not accepted.

```python
from sipi.norton_circuit import NortonCircuitDocument
from sipi.execution import normalize_saved, execute_saved

network = dict(kind='rlgc', frequency_hz=[0., 1e8, 3e8],
    R=[[10.]], L=[[250e-9]], G=[[.001]], C=[[100e-12]],
    length_m=.03, reference_ohms=50., names=['s'])
doc = NortonCircuitDocument(network,
    source_currents={'near:s': .001, 'far:s': 0.},
    termination_admittances={'near:s': .02, 'far:s': 0.})
assert normalize_saved(doc.dumps()) == doc.dumps()
output = execute_saved(doc.dumps(), max_evaluations=3)
assert output['status'] == 'complete' and output['input'] == doc.to_dict()
current = output['result']['response']['current_a']
assert all(abs(re[-1])+abs(im[-1]) < 1e-12
           for re, im in zip(current['real'], current['imag']))
```

## Networks, basis and budgets

Supported `network.kind` values reuse the existing strict source documents:
`rlgc`, `touchstone`, `lumped-network`, `transmission-line`, `volume-line`,
`network-transform` and `network-assembly`. Construction/normalization does not
solve fields; existing validators may perform small network algebra. Source
frequency grids and extraction validity limits remain unchanged. One frequency,
nonuniform positive samples and frequency-domain complex DC data are accepted;
there is no interpolation, DC inference or periodic real-DC restriction.

Sources must produce a single-ended network. `basis='single-ended'` preserves
its ports. `basis='mixed-mode'` requires four equal-reference source ports and
uses the existing power-dual transformation, with final port order
`d_near, d_far, c_near, c_far`. Currents and loads belong to that final basis.
No physical terminal or source position is inferred from a name.

`frequency_count` is F. `analyze(max_evaluations=128)` and `execute_saved`
require an integer budget from 2 through 10000; F must not exceed it. A
one-frequency request therefore still uses a budget of at least 2. Budget
failure happens before field extraction or terminal feedback, after validation.
Field-backed sources are extracted once. Any change in documented frequency,
port order, references or source basis is rejected before solving the boundary.

## Results and limitations

`NortonCircuitResult` retains `input_json`, `source_network`, final `network`,
optional original `extraction`, and the full Norton `response`. The common
`sipi.execution/1` output retains canonical input and reports coverage
`sampled-frequency-boundary` with these explicit units:

| Output | Meaning |
|---|---|
| `source_current_a`, `termination_admittance_s` | Current-source and parallel-load tables |
| `incident_sqrt_w`, `reflected_sqrt_w` | Power-wave phasors |
| `voltage_v`, `current_a` | Terminal voltage and current into the network |
| `condition_number`, `kcl_residual`, `wave_residual` | Original solver diagnostics |
| `frequency_power_w` | Network, parallel termination and ideal-source power per frequency |

The response fields are inside `result.response`; powers are at
`result.frequency_power_w`. Complex arrays retain separate real/imag components.
DC power weight is 1 and positive-frequency peak-phasor weight is 1/2.
Different frequency samples are **not summed into a periodic mean power**.
Norton internal source/shunt powers have their own topology; they do not equal
the internal powers after conversion to a Thevenin source.

Singular/floating, condition, residual and overflow failures retain the API's
exceptions and are not returned as complete/partial success. Output is finite
JSON. Top-level field diagnostics are not applicable to this circuit wrapper.

Validation covers all seven source kinds without field evaluation during
normalization, exact direct replay for five algebraic sources, actual PEC
single/paired mixed field extraction exactly once with `1e-12` absolute direct
agreement, strict tables, metadata drift, budget-before-field/feedback and
failure propagation. Volume-line adapter counting uses a controlled fixture;
it is not new volume-physics evidence. Numerical circuit references remain in
the separately validated Norton API. The registry has 43 saved schema versions.
This does not establish measured accuracy, general 3D behavior or current
browser/Windows support for the new schema.

[Thevenin circuit inputs](circuit_document.md) · [한국어](../../locales/ko/pages/packages/sipi/norton_circuit.md)
