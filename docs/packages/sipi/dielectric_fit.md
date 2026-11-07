# Passive Debye fitting at fixed relaxation poles

[한국어](../../locales/ko/pages/packages/sipi/dielectric_fit.md) · [Dielectric models](dielectrics.md)

`fit_debye` fits an existing `DebyeDielectric` to explicit real permittivity and
nonnegative dielectric loss samples. You supply the relaxation frequencies; the
algorithm fits only `eps_inf >= 1` and nonnegative strengths. It preserves the
original samples, weights, predictions, residuals and error-limit decision.

```python
import json
import numpy as np
from sipi.dielectric import DebyeDielectric, dielectric_from_dict
from sipi.dielectric_fit import fit_debye

frequency = np.geomspace(1e6, 1e12, 61)
poles = [1e8, 1e9, 1e10]
known = DebyeDielectric(2., [.8, 0., 1.2], poles)
samples = known.permittivity(frequency)
fit = fit_debye(frequency, eps_real=samples.real, eps_loss=-samples.imag,
               relaxation_hz=poles, max_error=1e-8)
assert fit.accepted and fit.maximum_error <= 1e-8
np.testing.assert_allclose(fit.model.strengths, [.8, 0., 1.2], atol=1e-8, rtol=0)
report = fit.to_dict()
json.dumps(report, allow_nan=False)
restored = dielectric_from_dict(report['model'])
np.testing.assert_array_equal(restored.permittivity(frequency), fit.predicted)
```

This example uses synthetic samples, not measured material data. The output model
can be supplied to the existing line/study/design material APIs and their saved
material records. [Saved fitting requests](dielectric_fit_document.md) reuse the
same algorithm through dielectric-fit/1 and shared execution.

## Inputs and objective

Supply 2–10000 distinct increasing nonnegative frequencies and 1–32 distinct
increasing positive relaxation poles, all in Hz. DC may be included. `eps_real`
and `eps_loss` must match the frequency grid and contain finite real numbers,
with eps_real >= 1 and eps_loss >= 0. The convention is
`eps = eps_real - j*eps_loss` for exp(+j omega t). No sign correction, clipping,
missing-row removal or pole inference is performed.

Optional `weights` are positive finite values at every frequency, defaulting to
one. The objective is `sum(weights * abs(model_eps - input_eps)**2)`: the real
and loss components at each frequency share that weight. Multiplying all weights
by one positive factor leaves the fit unchanged. Weights express the specified
objective; they are not automatically measurement uncertainties or confidence levels.

The real design matrix stacks the real and positive-loss parts of the Debye
relaxations, with a constant column for eps_inf-1. Weight and target scales are
normalized before SciPy NNLS. The matrix must have full column rank and condition
number <= 1e10. Nearly indistinguishable poles or uninformative samples reject;
they do not produce a seemingly unique accepted model. Relaxation basis evaluation
avoids frequency-ratio and squared-frequency overflow.

NNLS has a fixed iteration cap of 10*(number of poles+1), without retries. Its
returned nonnegative coefficients must pass a scaled KKT check <= 1e-10: the
objective gradient cannot be negative, and coefficient times gradient must vanish.
The gradient scale is max(1, largest singular value times residual norm); the
complementarity check also divides by max(1, largest coefficient). These checks
refer to the normalized optimization variables, not a statistical error bound.
Nonfinite output, nonconvergence or failed optimality checks raise an exception.

## Result and acceptance

`max_error` is a required positive absolute limit on the **largest complex
permittivity residual at any supplied frequency**, independent of weights.
`accepted` is true exactly when maximum_error <= error_limit. A numerically valid
fit outside that limit still returns its candidate and all residuals with
`accepted=False`; no row is dropped and no alternative tolerance is chosen.

`DebyeFit` retains the model, original frequency/real/loss/weight arrays, complex
`predicted` and `residual` arrays, matrix condition, scaled KKT error, maximum
error, weighted complex RMS error and requested error limit. Residual means
model minus input, including the negative-imaginary loss convention. Arrays are
read-only copies. `to_dict()` returns detached finite values, real/imaginary
arrays for complex data and the existing versioned dielectric-model record.

Fixed nonnegative Debye strengths and positive poles define a mathematically
passive causal model. Successful sampled fitting does not establish empirical
material validity, uncertainty, an error bound between samples or extrapolation
accuracy. The supplied poles are not optimized. No conductor/fixture deembedding,
roughness fitting, tensor-axis fitting or joint field inverse problem is performed.

## Validation

Synthetic multi-pole coefficients and zero-strength/constant/baseline limits are
recovered within absolute 1e-8. An independent exhaustive single-pole active-set
calculation agrees within 1e-10. A separate SciPy 1.18.1 bounded-variable least
squares solver with direct complex basis agrees on coefficients and predictions
within 1e-8; both use SciPy numerical primitives, so the analytic checks remain
separate. Tests retain deliberately nonfitting data, check weight-scale invariance,
ill-conditioning rejection, numerical failures and large finite frequencies.

Fitted model serialization and forward line extraction reproduce a known synthetic
material within 1e-8. No mesh operation is introduced by fitting; the original
forward material/field convergence evidence applies separately. These checks do
not establish a new platform or measured-material acceptance.

```sh
python -m pytest -q tests/sipi/test_dielectric_fit.py tests/sipi/test_dielectric.py tests/sipi/test_line_model.py
```
