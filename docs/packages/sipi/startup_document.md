# Saved lossless startup inputs

`LosslessStartupDocument` stores `sipi.lossless-startup/1` and connects the
[lossless scalar startup API](startup.md) to common saved execution. It keeps
the explicit initially unenergized line, PWL source, resistive boundaries and
requested output times. No frequency-to-time reconstruction is inferred.

```python
from sipi import LosslessStartupDocument
from sipi.execution import normalize_saved, execute_saved

document = LosslessStartupDocument([0., 1e-9, 2e-9, 3e-9],
    source_times=[0.], source_voltages=[1.], z0_ohm=50., delay_s=1e-9,
    source_resistance=50., load_resistance=None, max_terms=10000)
text = document.dumps()
assert normalize_saved(text) == text
assert document.required_terms == 1
out = execute_saved(text, max_evaluations=2)
assert out['status'] == 'complete'
assert out['result']['terms'] == 1
assert out['result']['voltage_v'] == [[.5, 0.], [.5, 1.], [1., 1.], [1., 1.]]
assert out['input']['max_terms'] == 10000
```

## Strict schema

All nine fields are required: `schema`, `time_s`, `source_times_s`,
`source_voltages_v`, `z0_ohm`, `delay_s`, `source_resistance_ohm`,
`load_resistance_ohm`, `max_terms`. Unknown keys/versions, duplicate keys,
nonfinite numbers and booleans in numeric fields are rejected. Times are
nonnegative, nonempty and strictly increasing. Source voltage shape matches
source times; one knot represents a step. Units and zero-prehistory/final-hold
behavior follow the API. Load null means open; zero means short, never missing.

Loading uses the API's shared control validation and required-term preflight.
It does not evaluate a waveform, generate a mesh or solve a field. Canonical
JSON and dictionary access are detached copies. This preflight does not prove
that every later shifted knot remains resolved or that output amplitudes stay
finite; those numerical checks still run in the solver.

## Two separate limits

The saved `max_terms` (1..10000) is a hard ceiling for potentially active
forward round-trip terms and is preserved exactly. `required_terms` is the
actual count determined by the saved horizon, first source knot and reflection
coefficients. `analyze(max_evaluations=128)` and common execution require that
count to fit the caller budget (existing integer range 2..10000) before any
waveform calculation. They do not require the caller to cover an unused saved
ceiling, and they never replace that ceiling with a smaller value.

Thus the example's matched source needs one forward term, even with saved cap
10000; its returning open-load wave is retained. An undamped ideal source
whose horizon requires three terms is rejected by caller budget two. The count
may be zero before the first source knot. Output time samples and interpolation
work are distinct from terms, so these budgets are not time/memory guarantees.

`analyze()` verifies that the solver kept the saved inputs, output times and
required count. Common execution returns the existing `sipi.execution/1`
envelope with the API's finite result dictionary. Port currents point into
the line at both ends; port names, units, traveling waves and original inputs
remain present. Existing byte limits and diagnostic restrictions apply:
characteristic/mode diagnostics require top-level transmission/volume lines.

Malformed inputs, budgets and ordinary solver failures raise their original
exceptions. In particular, unresolved shifted knots do not become a partial
success. This follows common execution's existing non-goal failure policy.

Acceptance checks strict parsing, no-waveform normalization, detached copies,
actual-term budgets, saved ceiling preservation, result identity and direct
API equality for steps/pulses with open, short, matched, mismatched and extreme
finite loads. The underlying independent LC refinement and exact energy gates
remain unchanged. The real document participates in the saved-schema registry.

This bounded model does not add reactive loads, loss, dispersion, coupled-line
startup or general TDR interpretation. A saved schema does not by itself add
an application form or establish browser/Windows support.

[Startup API](startup.md) · [Common execution](execution.md) ·
[한국어](../../locales/ko/pages/packages/sipi/startup_document.md)
