# Saved tensor fitting requests

[한국어](../../locales/ko/pages/packages/sipi/tensor_dielectric_fit_document.md) · [Direct fitting](tensor_dielectric_fit.md) · [Saved execution](execution.md)

`TensorDebyeFitDocument` saves the fixed-pole, fixed-orientation tensor fitting
contract as `sipi.tensor-dielectric-fit/1`. It reuses the direct numerical fit and
its existing sample, pole, direction, reciprocity, passivity and error limits.
Parsing validates inputs, including bounded per-sample 2×2 eigenvalue checks;
it does not run SVD, optimization or field meshing. Identifiability and numerical
optimality are checked during analysis.

```python
import numpy as np
from sipi.dielectric import TensorDebyeDielectric
from sipi.tensor_dielectric_fit_document import TensorDebyeFitDocument
from sipi.execution import normalize_saved, execute_saved
from sipi.execution_request import SavedExecutionRequest

frequency = np.geomspace(1e6, 1e12, 17)
model = TensorDebyeDielectric([2, 3], [[4, .5], [.25, 3]],
    [1e8, 1e10], [0, .7], .31)
samples = model.permittivity(frequency)  # synthetic demonstration
request_input = TensorDebyeFitDocument(frequency,
    eps_real=samples.real, eps_loss=-samples.imag,
    relaxation_hz=model.relaxation_hz, angles_rad=model.angles_rad,
    eps_inf_angle_rad=model.eps_inf_angle_rad, max_error=1e-8)
saved = request_input.dumps()
assert normalize_saved(saved) == saved
assert TensorDebyeFitDocument.loads(saved).dumps() == saved
request = SavedExecutionRequest(saved, max_evaluations=len(frequency))
receipt = request.run()
assert receipt['execution']['status'] == 'complete'
assert receipt['execution']['result']['accepted']
assert receipt['execution']['result'] == request_input.analyze().to_dict()
```

The document has exactly nine keys: `schema`, `frequency_hz`, `eps_real`,
`eps_loss`, `relaxation_hz`, `angles_rad`, `eps_inf_angle_rad`, `weights` and
`max_error`. Constructor defaults become explicit values: one weight per
frequency and a zero high-frequency angle. Saved requests cannot use null
weights or omit fields. Unknown or duplicate keys, nonstandard JSON NaN/Infinity,
booleans, invalid shapes and invalid physical inputs reject. Arrays are copied
into detached JSON-compatible data. Old readers reject the new schema.

`execute_saved` and immutable saved requests use the existing UTF-8 input-byte
limit. The number of frequency samples must not exceed `max_evaluations` before
SVD or optimization; equality is allowed. This budget is a sample-count admission
rule, not a time, memory or host cancellation guarantee. Direct `analyze()` uses
the fit's declared 2–10000 sample and 1–16 pole limits. Neither path performs a
field solve. Nonidentifiable designs and optimizer failures keep their original
exceptions rather than producing a fabricated candidate.

```python
raw = request_input.to_dict()
raw['eps_loss'] = (-samples.imag + .01*np.eye(2)).tolist()
raw['max_error'] = 1e-5
unmatched = TensorDebyeFitDocument.from_dict(raw)
output = execute_saved(unmatched.dumps(), max_evaluations=len(frequency))
assert output['status'] == 'complete'
assert not output['result']['accepted']
assert output['result']['eps_loss'] == raw['eps_loss']
assert len(output['result']['residual']['real']) == len(frequency)
```

Execution completion and the sampled-error decision are separate. An above-limit
fit preserves every input, prediction, residual and its passive tensor candidate.
`result['model']` is an ordinary nested `sipi.dielectric/3` material record and can
be read with `dielectric_from_dict` for existing saved lines. It does not certify
that the data are measured, that the material exists, or that unsampled frequencies
meet the error limit. The fit result dictionary and execution receipt are outputs,
not additional registered saved-input schemas. Request identity includes canonical
input and controls; artifact authenticity and host run lifecycle remain separate.

```sh
python -m pytest -q tests/sipi/test_tensor_dielectric_fit_document.py tests/sipi/test_tensor_dielectric_fit.py tests/sipi/test_dielectric_fit_document.py tests/sipi/test_execution.py tests/sipi/test_execution_request.py
```

Checks compare accepted and above-limit saved results exactly with direct fitting,
exercise strict roundtrips and preparation without optimization, verify exact
sample/byte limits, and retain numerical failures. Existing scalar fitting and
canonical saved inputs keep their contracts. This orchestration unit adds no new
physical accuracy, browser integration or platform claim.
