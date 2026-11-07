# Saved conductivity-profile inputs

`ConductivityProfileDocument` saves the bounded
[Gaussian half-space kernel](conductivity_profile.md), including its exterior
reference-plane cutoff. It does not add this law to transmission-line
conductors. The new input schema is `sipi.conductivity-profile/1`.

```python
import json
from sipi import GaussianConductivityProfile, ConductivityProfileDocument
from sipi.execution import normalize_saved, execute_saved

doc = ConductivityProfileDocument(
    GaussianConductivityProfile(conductivity=58e6, rms_m=1e-6),
    [1e9, 4e9, 10e9], cutoff_rms=8)
text = normalize_saved(doc.dumps())
assert text == doc.dumps()
output = execute_saved(text, max_evaluations=3)
assert output['status'] == 'complete'
assert output['input'] == doc.to_dict()
assert output['result']['reference_plane_m'] == -doc.cutoff_rms*doc.profile.rms_m
assert output['result']['frequency_hz'] == [1e9, 4e9, 10e9]
json.dumps(output, allow_nan=False)
```

The top-level fields are exactly `schema`, `model`, `frequency_hz` and
`cutoff_rms`. `model` requires exactly:

```json
{"kind": "gaussian-conductivity", "conductivity_s_per_m": 58000000.0, "rms_m": 1e-6}
```

All physical units and numerical limits are those of the kernel. The Python
constructor defaults cutoff to 8, but saved JSON must include it explicitly.
RMS zero selects the same full-Maxwell smooth limit; there is no implicit
alternative model, unit conversion, unknown field acceptance or migration.
Missing/duplicate keys, nonfinite numbers, booleans in physical values,
unsupported versions/kinds and out-of-range scales fail during parsing.
Caller dictionaries and returned input dictionaries cannot mutate the saved
request. `frequency` returns a fresh array; `profile` is an immutable model.

Parsing and `normalize_saved` validate without integrating. `analyze` and
`execute_saved` count one evaluation per frequency and reject a request above
the supplied `max_evaluations` **before integration**. The common budget is
an integer 2..10000 (default 128); the kernel's independent 1024-frequency
limit still applies. A one-frequency request is valid with budget at least 2.
Budgets do not guarantee elapsed time or provide cancellation; the caller
owns execution isolation. Unsupported line diagnostics are rejected before
the profile solve. Integration failures propagate and are not returned as
partial successful calculations.

Shared output keeps the existing `sipi.execution/1` envelope with the exact
canonical input. Its `result` contains:

| Field | Meaning |
|---|---|
| `frequency_hz` | Original increasing frequency samples |
| `surface_impedance_ohms` | Separate `real` and `imag` arrays of exterior E/H |
| `skin_depth_m` | Bulk good-conductor delta used to define the bounded model |
| `cutoff_rms` | Explicit transition truncation multiplier |
| `reference_plane_m` | `-cutoff_rms*rms_m`, with x positive into the metal and mean plane x=0 |

The document checks that the result retains the saved model, frequencies and
cutoff. Negative exterior reactance is preserved. This output does not imply
that its reference plane can be replaced by a line's mean plane, or that the
result is an internal-inductance correction. Older readers reject the new
schema; the existing web/EXE candidate pins are not updated by this addition.

Tests require exact direct-kernel replay and finite JSON serialization,
independent scikit-rf 2.2.0 agreement at the same +/-5Rq plane within 1e-6,
and the zero-RMS analytic intrinsic impedance within 1e-12. Strict inputs,
pre-integration budgets, input isolation, metadata mismatch rejection and
failed-solve propagation are checked. The common registry test includes a
real instance of this schema. These checks do not establish new physical,
measured-board, browser or Windows validity beyond the kernel's contract.

[Shared execution](execution.md) · [한국어](../../locales/ko/pages/packages/sipi/conductivity_profile_document.md)
