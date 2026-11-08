# Coupled passive Debye startup

`coupled_debye_rlgc_ladder_response` propagates an explicit two-signal circuit
from zero state. It uses constant real symmetric 2x2 R/L/G/C_inf matrices and
one or two matrix-valued Debye strengths:

C*(f) = C_inf + sum(delta_C[k] / (1 + j f / relaxation_hz[k])).

R [ohm/m] and G [S/m] must be positive semidefinite; L [H/m] and C_inf [F/m]
positive definite with normalized eigenvalue ratio greater than 1e-12.
Each strength [F/m] is exactly zero or positive definite at the same ratio.
All matrices must be exactly symmetric. General singular/rank-one strengths
and negative eigenvalues are rejected without repair. R/G can be rank deficient.
Strength order and exact zero declarations remain in the returned inputs.

```python
import numpy as np
from sipi import coupled_debye_rlgc_ladder_response

t = np.linspace(0., 12e-9, 121)
drive = np.minimum(t/2e-9, 1.)[:, None]*[1., -.4]
a = coupled_debye_rlgc_ladder_response(t, drive,
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -25.], [-25., 150.]], [[50., -10.], [-10., 50.]]])*1e-12,
    relaxation_hz=[1e9, 1e8], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.])
assert a.voltage.shape == (121, 4)
assert a.polarization_charge.shape == (121, 17, 2, 2)
assert a.total_power_balance_relative_error <= 1e-10
assert np.min(a.total_energy) >= 0.
```

Each source/load resistance vector has two finite positive ohm values.
Time has 2–10000 uniformly spaced samples starting at zero and source voltage
shape (times,2), with first row zero. The linear interpolant is propagated
with SciPy lsim. Explicit cells=1–128 and one/two poles are resource bounds,
not accuracy or execution-time guarantees. No poles, times or cells are inferred.

Port order is near_0,near_1,far_0,far_1. All port currents enter the line;
segment currents point toward the far end. Node/segment states have a final
two-conductor axis. Polarization voltage/charge/current arrays are
(time,node,declared pole,conductor), in V/C/A. Charge and current include
lumped node capacitances and half-end weights. Cross terms can give signed
individual charges; passivity concerns the complete quadratic energy.

For each active pole, tau*w'=V-w with tau=1/(2 pi relaxation_hz).
`energy` and `energy_rate` cover only instantaneous C_inf/L storage;
`polarization_energy` and `polarization_energy_rate` cover sum(wᵀ C_pole w)/2
and its derivative. `relaxation_loss` is sum((V-w)ᵀ C_pole (V-w)/tau).
Total properties combine both storage terms. Energy is J and rate/loss W,
summed over the complete line and both signals. Neither energy nor negative
return power is clipped. Relative line-port and supplied-source balance gates
are 1e-10, including source/load resistor loss. Coefficients, propagated states
and diagnostics must remain finite; the initial propagated state must be zero.

`CoupledDebyeRLGCLadderResponse` is separate from the scalar class and is not
implicitly admitted into scalar wave/saved adapters. Its arrays are copied and
read-only; input dictionaries are detached. `to_dict()` includes port/energy
results, while `to_dict(include_states=True)` also includes internal arrays.
This output is not an executable saved request.

## Independent checks and limits

Decoupled and exchange-symmetric modal decomposition agrees with two scalar
Debye calculations within 1e-10 V/1e-12 A. Zero strengths recover the original
constant coupled RLGC response. A separate noncommuting charge-state node KCL
model integrated with DOP853 agrees within 1e-8 V/1e-9 A. It does not reuse
the candidate's assembled mass or stiffness matrices.

For the documented exchange matrices and sine input amplitudes [1,-.4],
continuous modal scikit-rf ABCD comparisons at 32/64/128 cells give:

| Frequency / explicit time samples | Maximum terminal voltage errors |
|---|---|
| 100 MHz, 8 cycles, 1024 samples/cycle | 22.6771 / 5.30428 / 1.83043 microvolt |
| 500 MHz, 20 cycles, 256 samples/cycle | 1.49727 / .377406 / .100628 mV |
| 1 GHz, 20 cycles, 256 samples/cycle | 5.74077 / 1.43556 / .362797 mV |

Each decreases below 1 mV at 128 cells. At 100 MHz/128 cells, refining
256/512/1024 samples/cycle reduces error against independent finite-pi modal
solutions to 39.9698/9.92406/2.48102 microvolt. Seven/eight/nine-cycle phasor
differences are below 1e-8 V. These are specified cases, not general accuracy
bounds. Pulse, zero inputs, PSD R/G, pole/conductor permutation, scaling,
readonly/copy, strict matrix and numerical-failure checks supplement them.

This model excludes ideal/open/short/current-source/reactive external ends,
generic PSD strengths, automatic geometry/material extraction, conductor
frequency dependence, arbitrary fitting, TDR interpretation and measured-board
accuracy. Browser and Windows require separate integration. The [terminal wave adapter](startup_waves.md) now explicitly accepts this response; saved wave v1..4 remain unchanged. Existing NumPy/SciPy and test-only scikit-rf versions/licenses are
retained; no new dependency is introduced.

[Scalar Debye](debye_startup.md) · [Constant coupled RLGC](coupled_startup.md) ·
[한국어](../../locales/ko/pages/packages/sipi/coupled_debye_startup.md)

[Saved inputs](coupled_debye_startup_document.md) provide a separate executable request.

[Separate PSD-strength API](psd_debye_startup.md) admits singular strengths explicitly; this page retains its strict SPD limits.


[Three/four-signal positive-strength Debye API](multiconductor_debye_startup.md) uses a separate explicit result type and bounded circuit contract.
