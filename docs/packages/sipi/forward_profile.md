# Explicit multiconductor forward launches

`rlgc_forward_profile` evaluates a specified current launch along a uniform
reciprocal line using the existing full-matrix characteristic solution. It
retains coupling between every conductor. Even a conductor with zero current
at the launch can have induced voltage and nonzero current further along the
line. This is a pure forward wave with a corresponding matched continuation;
use a terminated circuit calculation for source or load reflections.

```python
import numpy as np
from sipi.forward_profile import rlgc_forward_profile

profile = rlgc_forward_profile(
    [1e9, 3e9],
    R=np.array([[2., .2, .1], [.2, 3., .2], [.1, .2, 2.5]]),
    L=np.array([[3., .4, .2], [.4, 3.5, .3], [.2, .3, 4.]])*1e-7,
    G=np.eye(3)*.002,
    C=np.array([[1.5, -.1, -.05], [-.1, 1.8, -.1], [-.05, -.1, 2.]])*1e-10,
    launch_current=[.01, -.01, 0.],  # Peak A, explicit conductor order.
    positions=[0., .01, .02],       # Metres from the launch plane.
    names=('left', 'middle', 'right'),
)
assert profile.voltage.shape == (2, 3, 3)
assert np.array_equal(profile.current[:, 0, 2], [0., 0.])
assert np.all(profile.power[:, -1] < profile.power[:, 0])
```

The frequency array is positive Hz; DC is excluded. `launch_current` is either
an `(N,)` complex peak-ampere vector shared by all frequencies or an explicit
`(F,N)` array. No current normalization or RMS conversion is performed.
`positions` is a nonempty, strictly increasing array of finite nonnegative
metre distances; it need not start at zero. RLGC matrices may be `(N,N)` or
`(F,N,N)` and retain the existing reciprocal/passive admission and conditioning
gates. Frequency-dependent samples do not establish a causal material model.

The sign convention is exp(+j omega t), with current positive along +z:
V0=Zc I0, V(z)=exp(-Gamma_voltage z)V0 and I(z)=Yc V(z).
`voltage` and `current` have shape `(F,P,N)` in volts and amperes. The real
`power`, `conductor_loss` and `dielectric_loss` arrays have shape `(F,P)`:

- P = Re(V^H I)/2, average transmitted power in W.
- qR = Re(I^H R I)/2, conductor dissipation in W/m.
- qG = Re(V^H G V)/2, dielectric dissipation in W/m.

All cross terms remain. These are total powers, not independent per-conductor
losses or modal attenuation constants. Local conservation is dP/dz=-(qR+qG).
Power and dissipation are not clipped; accepted PSD roundoff from the existing
matrix contract remains visible. A zero launch returns zero outputs.
Nonfinite arithmetic is rejected. Arrays are copied, read-only snapshots;
constructing `ForwardWaveProfile` directly validates shape, not physics.

Validation covers scalar closed forms, a manufactured nonorthogonal
power-dual coordinate transform, independent 2N state eigenspaces for three
and four conductors, integrated dissipation and local telegrapher power
balance, permutations and complex-amplitude scaling. This validates RLGC
algebra; it adds no field extraction, arbitrary termination, scalar/pair
impedance goal, modal tracking, saved schema or UI. It does not qualify a new
geometry, field mesh, measurement accuracy or platform.

[한국어](../../locales/ko/pages/packages/sipi/forward_profile.md)
