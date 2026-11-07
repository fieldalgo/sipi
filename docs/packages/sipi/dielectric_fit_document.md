# Saved fixed-pole dielectric fitting requests

[한국어](../../locales/ko/pages/packages/sipi/dielectric_fit_document.md) · [Fitting algorithm](dielectric_fit.md) · [Shared execution](execution.md)

`DebyeFitDocument` stores the complete input to the existing fixed-pole Debye
fitter. It preserves sample order, explicit weights, fixed relaxation poles and
the requested maximum complex-permittivity error. It does not choose poles or
infer missing measurements.

```python
import numpy as np
from sipi.dielectric import DebyeDielectric, dielectric_from_dict
from sipi.dielectric_fit import DebyeFitDocument
from sipi.execution import normalize_saved, execute_saved

frequency = np.geomspace(1e6, 1e12, 61)
poles = [1e8, 1e10]
samples = DebyeDielectric(2., [1., 2.], poles).permittivity(frequency)
plan = DebyeFitDocument(frequency, eps_real=samples.real, eps_loss=-samples.imag,
                       relaxation_hz=poles, max_error=1e-8)
assert plan.to_dict()['weights'] == [1.]*len(frequency)
saved = normalize_saved(plan.dumps())
assert saved == plan.dumps()
report = execute_saved(saved, max_evaluations=len(frequency))
assert report['status'] == 'complete' and report['result']['accepted']
material = dielectric_from_dict(report['result']['model'])
np.testing.assert_allclose(material.permittivity(frequency), samples, atol=1e-8, rtol=0)
```

The strict `sipi.dielectric-fit/1` object contains exactly `schema`,
`frequency_hz`, `eps_real`, `eps_loss`, `relaxation_hz`, `weights`, `max_error`.
The Python constructor may omit weights, which resolves them to an explicit
array of ones. Saved JSON requires every field, including a complete positive
weight array; `null` is not a default. Units, sign convention, size limits and
input bounds are those of the [fitting API](dielectric_fit.md). Unknown fields,
duplicate keys, boolean numerical values and nonfinite numbers reject.

Constructing, loading and normalizing a request only validates and copies input.
It performs no SVD, optimizer call or field solve. Numerical identifiability and
conditioning checks occur in `analyze()`, followed by the existing bounded fit
and KKT check. Canonical JSON and dictionary accessors return detached values.

Shared execution checks **the number of supplied frequency samples** against
the caller's `max_evaluations` before matrix work or optimization. For example,
61 samples need a budget of at least 61, with no automatic truncation. This count
does not mean 61 optimizer iterations; the API's separate iteration cap remains
10*(number of poles+1). It does not bound process memory or wall time. The usual
input-byte limit also applies, and larger valid requests may need the caller to
explicitly allow more bytes. Line-only characteristic/mode diagnostics reject
for this request kind.

`execute_saved` returns canonical `input` and the same complete `DebyeFit.to_dict()`
result as the direct API. A numerically finished fit has `status='complete'`;
whether it meets the requested error limit is the separate `result.accepted` flag.
The following deliberately inconsistent synthetic sample is retained as a
completed but unaccepted candidate:

```python
changed = plan.to_dict()
changed['eps_real'][0] += .2
unaccepted = execute_saved(DebyeFitDocument.from_dict(changed).dumps())
assert unaccepted['status'] == 'complete'
assert not unaccepted['result']['accepted']
assert len(unaccepted['result']['residual']['real']) == len(frequency)
```

Invalid input, rank/condition rejection and optimizer failure raise their original
exceptions, matching the existing line-execution convention. They do not return
a fabricated model or a completed partial fit. The retained model uses the
existing dielectric-model schema and can be passed to line/study/design material
inputs; callers should assess its acceptance and intended validity first.

Tests require exact direct/saved model, residual and decision replay, default
resolution and detached inputs, normalization without numerical work, the exact
sample-budget boundary, original failure exceptions and strict JSON rejection.
A fitted synthetic material also reproduces existing saved-line C/G/L/S within
1e-8. Independent algorithm/active-set checks remain in the fitting API suite.
These are sampled mathematical contracts, not measured-material, continuous-band,
application-pin or new platform acceptance.

```sh
python -m pytest -q tests/sipi/test_dielectric_fit_document.py tests/sipi/test_dielectric_fit.py tests/sipi/test_execution.py tests/sipi/test_dielectric.py
```
