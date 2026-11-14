# Effective shunt-loss inference

`infer_shunt_loss` estimates nonnegative scalar shunt conductance G [S/m]
from **traveling-wave amplitude attenuation** alpha [Np/m] and known R [ohm/m],
L [H/m] and C [F/m]. It solves the full lossy relation
`alpha = Re sqrt((R+j*omega*L)*(G+j*omega*C))` at each frequency.
It does not subtract an approximate copper attenuation from insertion loss.

```python
import numpy as np
from sipi import infer_shunt_loss

frequency = np.array([1e8, 1e9])
# Explicit propagation attenuation supplied by the caller.
result = infer_shunt_loss(frequency, alpha=[0.2, 2.0], R=2.,
                         L=400e-9, C=150e-12, max_error_np_per_m=1e-9)
assert result.accepted
assert np.all(result.conductance >= 0)
print(result.effective_loss_tangent)
record = result.to_dict()
```

Use 1..10000 strictly increasing positive frequencies and a matching nonnegative
alpha array. R may be zero; L and C must be positive. Each known coefficient
may be scalar or a frequency array. The explicit positive error limit is in Np/m.
Inputs are copied. Results retain the original RLC and alpha, G, the G=0 baseline,
predicted alpha and beta, signed residuals, exact conductor/dielectric power-loss
contributions and root evaluation counts. Result arrays are read-only.

If alpha lies below the G=0 baseline, the best nonnegative candidate is G=0.
The original alpha and positive residual are retained. `accepted` means only
that every sampled absolute residual is at most the supplied limit. A loose limit
can accept a below-baseline mismatch; it does not validate its physical cause.
Bracketing starts at omega*C with at most 64 factors of four. Normalized Brent
iteration has a 128-iteration limit without retries. Unrepresentable values,
failure to bracket and root failures raise instead of returning a success.

`G/(omega*C)` is an **effective shunt loss tangent**. It equals a constituent
material tan(delta) only when the caller's physical model justifies that relation.
This API does not infer multiple dielectrics, deembed fixtures, convert arbitrary
S21 to propagation attenuation, estimate measurement uncertainty, or establish
continuous-band accuracy. No field solve is performed: supplied RLC still needs
its own mesh, outer-boundary and physical validation.

Validation includes the independent R=0 analytic inverse, attenuation from the
eigenvalue magnitudes of a 2x2 telegrapher matrix exponential, low/high-loss RLGC
replay, exact power balance and below-baseline data preservation. These tests
establish the inversion contract, not measured laminate accuracy.

[한국어](../../locales/ko/pages/packages/sipi/loss_inference.md)
