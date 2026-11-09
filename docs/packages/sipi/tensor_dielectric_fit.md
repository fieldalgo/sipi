# Tensor fitting with fixed poles and directions

[한국어](../../locales/ko/pages/packages/sipi/tensor_dielectric_fit.md) · [Tensor material](tensor_debye.md) · [Scalar fitting](dielectric_fit.md)

`fit_tensor_debye` fits a finite [TensorDebyeDielectric](tensor_debye.md) to
explicit relative-permittivity tensor samples in the `exp(+j omega t)` convention.
Supply fixed pole frequencies and fixed principal directions for each residue
and the high-frequency tensor. The unknowns are two nonnegative high-frequency
increments above one and two nonnegative strengths per pole. The result is a
passive reciprocal transverse model. This operation does not choose poles or
angles, estimate measurement uncertainty or establish measured material validity.

## Direct fitting

```python
import json
import numpy as np
from sipi.dielectric import TensorDebyeDielectric, dielectric_from_dict
from sipi.tensor_dielectric_fit import fit_tensor_debye

frequency = np.geomspace(1e6, 1e12, 41)
poles, angles, high_angle = [1e8, 1e10], [0, .7], .31
original = TensorDebyeDielectric([2, 3], [[4, .5], [.25, 3]],
    poles, angles, high_angle)
samples = original.permittivity(frequency)  # synthetic demonstration data
result = fit_tensor_debye(frequency,
    eps_real=samples.real, eps_loss=-samples.imag,
    relaxation_hz=poles, angles_rad=angles, eps_inf_angle_rad=high_angle,
    max_error=1e-8)
assert result.accepted
record = result.to_dict()
json.dumps(record, allow_nan=False)
restored = dielectric_from_dict(record['model'])
np.testing.assert_array_equal(restored.permittivity(frequency), result.predicted)
```

Frequencies are 2–10000 finite, distinct, increasing nonnegative values in Hz.
Use 1–16 finite, distinct, increasing positive poles in Hz, a matching vector of
finite angles in radians counterclockwise from global transverse x, and one
finite `eps_inf_angle_rad` (default zero). `eps_real` and `eps_loss` each have
shape `(F,2,2)` and describe `eps_real - j*eps_loss`. They must be reciprocal
within relative `1e-12`; real eigenvalues must be at least one and the loss
matrix positive semidefinite within relative roundoff. Booleans, complex-valued
component arrays, nonfinite values and incompatible shapes reject. Negative
individual off-diagonal loss entries can be valid.

Optional positive weights have one value per frequency and multiply the sum of
all four squared complex-entry residuals. Their common scale does not change the
fit. The objective is therefore the weighted Frobenius norm, including any
admitted antisymmetric roundoff in the original data. Input samples are never
clipped or averaged. `max_error` is a required positive absolute Frobenius error
limit per frequency, independent of weights.

The normalized weighted real design must have full column rank and condition
at most `1e10`. Nonnegative least squares has a fixed cap of ten times the number
of unknowns, without retries. Its scaled gradient/complementarity KKT error must
be at most `1e-10`; coefficients must construct a finite valid tensor model.
Ill-conditioned or unidentifiable bases, optimizer errors and invalid numerical
certificates raise. The number of samples alone does not guarantee identifiability.

## Retain an above-limit candidate

```python
unmatched = fit_tensor_debye(frequency,
    eps_real=samples.real, eps_loss=-samples.imag + .01*np.eye(2),
    relaxation_hz=poles, angles_rad=angles, eps_inf_angle_rad=high_angle,
    weights=np.geomspace(.5, 3, len(frequency)), max_error=1e-5)
assert not unmatched.accepted
assert unmatched.residual.shape == (len(frequency), 2, 2)
np.testing.assert_array_equal(unmatched.eps_loss, -samples.imag + .01*np.eye(2))
```

A completed fit retains every original sample, its candidate model, prediction,
residual `model-(eps_real-j*eps_loss)`, condition and KKT diagnostic. Arrays are
copied and read-only. `maximum_error` is the largest per-frequency Frobenius
residual, while `weighted_rms_error` is its weighted RMS. An above-limit model
remains available with `accepted=False`; weights cannot hide a failed sample
from the maximum-error decision. A model at the exact limit is accepted.

The model can be embedded in existing saved line/material documents. The
returned dictionary is a fit result, not a saved fitting-request schema; direct
Python fitting and material serialization are the scope of this unit. No field
solve occurs during fitting. A small sampled residual provides no mesh/outer
convergence evidence, continuous-band error bound, real-laminate certification
or new platform support. Fixed orientations describe a convex subset of tensor
responses, not every passive tensor spectrum.

## Reproduce the checks

```sh
python -m pytest -q -s tests/sipi/test_tensor_dielectric_fit.py tests/sipi/test_dielectric_fit.py
```

Independent direct-rational tensor samples require coefficient recovery within
`1e-9`, tensor predictions within `1e-10` and held-out synthetic samples within
`1e-9`. The largest 16-pole design is checked. Sixteen rotated one-pole cases use
independent two-variable normal equations and exhaustive feasible boundary
candidates. A stored synthetic noisy fixture uses seed 912, PSD perturbations
and an independent direct-rational basis with `scipy.optimize.lsq_linear`
(BVLS); coefficient and prediction differences must be below `1e-8`.
Both optimizers use SciPy primitives, so this comparison supplements the analytic
boundary and coefficient checks. Input preservation, passive limits, covariance,
weight-scale invariance, extreme frequencies and explicit failure paths are also
checked. Existing scalar fits retain their original numerical implementation.
