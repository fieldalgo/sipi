# Sampled periodic network response

`periodic_response(network, incident)` applies a `LineNetwork` to one period
of real incident power waves. `periodic_impulse(network)` gives the matching
discrete circular-convolution weights. Existing RLGC, circuit and measured
network producers can be used only when their output meets this contract.

## Frequency and time contract

- Supply `F >= 2` samples beginning at **exactly 0 Hz** and at harmonics
  `f[k] = k*df`, `df = f[1] > 0`. Maximum grid error must be at most
  `1e-12*f[-1]`. This tolerates roundoff; it does not interpolate samples.
- The entire DC S matrix must have exactly zero imaginary part. Missing DC,
  irregular spacing and complex DC are errors. No DC estimate, extrapolation,
  window, padding, smoothing or passivity/causality repair is performed.
- The time sample count is **odd**, `N = 2*F-1`, with `T = 1/df` and
  `dt = T/N`. There is no Nyquist bin; the phase of the highest positive
  frequency is retained. Times are `0, dt, ..., (N-1)*dt` (no repeated endpoint).
  Unrepresentable periods, grids, spectra or output values raise `ValueError`.
- `incident` must be finite real numbers, shape `(N, ports)`, with no booleans.
  The real Fourier coefficients obey `b[k] = S[k] @ a[k]`.
  The network's port order, basis and positive real, frequency-independent
  reference impedances are retained. Nonreciprocal matrices are not transposed.

The result provides read-only `incident`, `reflected` [sqrt(W)], `voltage` [V],
`current` [A], `time` [s], `z_ref` [ohm], `period`, `dt`, `port_names` and `basis`.
At every time and port,

```
V = sqrt(Zref) * (a + b)
I = (a - b) / sqrt(Zref)
V*I = a*a - b*b
```

Current points **into** the network. These are real time samples, with no
phasor/RMS factor of one half. Mixed-mode waves use the network's actual mode
references (for example, 100 ohm differential and 25 ohm common for a
50 ohm single-ended pair).

## Example: a matched line's periodic delay

```python
import numpy as np
from sipi import rlgc_network, periodic_response, periodic_impulse

frequency = np.arange(9)*1e8
count = 2*len(frequency)-1
dt = (1/frequency[1])/count
velocity = 2e8
network = rlgc_network(frequency, R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length=velocity*2*dt, z_ref=50.)
incident = np.zeros((count, 2))
incident[:, 0] = np.cos(2*np.pi*np.arange(count)/count)
response = periodic_response(network, incident)
np.testing.assert_allclose(response.reflected[:, 1],
    np.roll(incident[:, 0], 2), atol=1e-12, rtol=0)
impulse = periodic_impulse(network)
assert impulse.weights.shape == (count, 2, 2)
assert response.port_names == network.port_names
```

## Discrete impulse and limits

`PeriodicImpulse.weights[lag, output_port, input_port]` is dimensionless.
Centered lags run from `-(F-1)*dt` to `+(F-1)*dt`. Unshift with
`np.fft.ifftshift(weights, axes=0)` to obtain lags `0..N-1` for circular
convolution. Sum over all lags equals the DC S matrix within numerical error.
These weights multiply discrete samples, **not** a continuous Dirac density;
do not multiply by `dt` in their discrete convolution.

Negative lags wrap around one period. This is finite-band periodic steady
state, not a startup transient, an isolated pulse response, TDR impedance,
or an inference of causality, stability or physical material accuracy.
Increasing the highest frequency changes time resolution; changing `df`
changes the period and wraparound. Sampled S alone specifies neither missing
harmonics nor behavior between samples. Aliasing and a short period can hide
long delays. No automatic unwrapping or physical error estimate is provided.
An active externally constructed S is not rejected merely for gain greater
than one, and is not thereby certified stable. Use an appropriate source model.

## Validation scope

Tests compare arbitrary nonreciprocal multiport responses to explicit finite
DFT sums (without FFT) to absolute `1e-12`, including the highest positive bin.
Constant reflection, integer-sample delays/wrap, superposition, time shift,
real power balance and passive sampled-network energy are checked. Known RC
harmonics agree at two periods and two resolutions to `1e-12`; this proves the
represented harmonic solution, not convergence of an arbitrary transient.
Lossless RLGC delay and mixed-mode normalization use the existing line engine.
No geometric extraction or mesh convergence claim is added by this transform.

scikit-rf 2.2.0 (BSD-3-Clause) provides unwindowed odd-length lowpass impulse
comparisons; it shares NumPy's FFT backend, so the separate direct finite-sum
reference remains required. SciPy 1.18.1 (BSD-3-Clause) direct convolution is
folded circularly and compared to the response, absolute `1e-12`. These tools
do not supply measured validation. Strict input and numeric-scale failures
are tested. This Python API does not change saved JSON schemas or application
support. [Networks](network.md) · [한국어](../../locales/ko/pages/packages/sipi/periodic.md)
