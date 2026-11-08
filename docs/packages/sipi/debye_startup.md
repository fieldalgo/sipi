# Passive Debye startup response

`debye_rlgc_ladder_response` propagates an explicit scalar finite line circuit
from zero initial energy. It adds causal dielectric relaxation to constant
R/L/G and an instantaneous capacitance. The caller supplies every pole:

C*(f) = C_inf + sum(delta_C / (1 + j f / relaxation_hz)).

`R` is nonnegative ohm/m, `L` positive H/m, `G` nonnegative S/m, `C_inf`
positive F/m. `delta_C` contains 1–4 nonnegative strengths in F/m and
`relaxation_hz` the same number of positive frequencies in Hz. Pole order,
repeated frequencies and zero strengths are preserved. No material, geometry,
permittivity or frequency-table conversion is inferred.

```python
import numpy as np
from sipi import debye_rlgc_ladder_response

t = np.linspace(0., 12e-9, 241)
a = debye_rlgc_ladder_response(t, np.minimum(t/2e-9, 1.),
    R=20., L=500e-9, G=.002, C_inf=200e-12,
    delta_C=[150e-12, 50e-12], relaxation_hz=[1e9, 1e8],
    length=.1, cells=32, source_resistance=25., load_resistance=100.)
assert a.voltage.shape == (241, 2)
assert a.polarization_charge.shape == (241, 33, 2)
assert a.total_power_balance_relative_error <= 1e-10
result = a.to_dict()
assert not result['states_included']
```

Use 1–128 cells and 2–10000 uniformly spaced time samples starting at zero.
The real source voltage array matches time and starts at zero. Its linear
interpolant is propagated, with the last value held and final slope zero.
Source/load resistances are finite and nonnegative: zero source resistance
is an ideal voltage source, zero load a short, and `None` load an open.
The two port currents enter the line; segment currents point toward the load.
Resource limits are not accuracy or execution-time guarantees.

Each cell has series R/L and shunt G/C_inf, with half shunts at the endpoints.
For each active pole, tau = 1/(2 pi relaxation_hz) and tau dw/dt = V - w.
`energy`/`energy_rate` include only C_inf/L. `polarization_energy` is
sum(C_pole w²)/2, `polarization_energy_rate` its derivative, and
`relaxation_loss` is sum(C_pole (V-w)²/tau). `total_energy` and
`total_energy_rate` combine the two storage terms. All are whole-line J/W.
Both line-port balance and supplied-source balance must hold to relative
1e-10, including source/load resistor loss. Returned energy is never clipped.

Polarization voltage, charge and current arrays are ordered
(time, node, declared pole), in V/C/A. Charges include each node's lumped
capacitance and half-end weight. Zero-strength columns remain zero while their
internal dynamic states are omitted. Arrays are copied, finite and read-only;
`inputs` returns a fresh copy. `to_dict(include_states=True)` additionally
includes internal states with explicit unit keys. This result serialization
is not a versioned, executable saved request. Existing constant-RLGC and
wave-adapter contracts remain separate.

## Independent validation and limits

A one-cell ideal-source/short ramp-and-hold has exact inductor and Debye
charge solutions. Zero strengths recover the constant-RLGC API. Separate
node KCL with charge states and SciPy DOP853 agrees within 1e-8 V/1e-9 A for
one/two-pole ideal, finite, open and short cases. Pole splitting/permutation,
voltage/time/impedance scaling, six boundaries and energy checks supplement
these references. The explicit capacitance function agrees with
`C0 * DebyeDielectric.permittivity(f)` when its parameters are supplied consistently.

Continuous scikit-rf ABCD comparisons use 32/64/128 cells and final-four-cycle
phasors. At 100 MHz, eight cycles with 1024 samples/cycle give voltage errors
23.0454/5.40911/2.10120 microvolt. At 500 MHz and 1 GHz, twenty cycles with
256 samples/cycle give 1.49601/.377782/.101349 mV and
5.42325/1.35706/.343489 mV. Each decreases below 1 mV at 128 cells.
For the 100 MHz case, 256/512/1024 samples reduce error against an independent
finite-circuit frequency solution from 40.9758 to 10.1580 to 2.53950 microvolt;
seven/eight/nine-cycle phasor differences stay below 1e-8 V.

The original 100 MHz, 256-sample protocol failed spatial monotonicity because
PWL source error dominated; the six-cycle settling check also failed 1e-8 V.
Those settings are not qualified by the successful, separately specified
checks. The API never changes the user's time grid or horizon. Check source,
time and spatial convergence for each application.

This is a finite passive circuit, not general dispersive field extraction,
frequency-dependent conductor loss, coupled Debye matrices, arbitrary loads,
TDR interpretation or measured-board accuracy. No new dependencies are added:
SciPy 1.18.1 and test-only scikit-rf 2.2.0 use the existing license/notice review.
Browser and Windows require separate integration.
[Explicit terminal waves](startup_waves.md) preserve the polarization power balance.

[Constant RLGC](rlgc_startup.md) · [Frequency-dependent dielectric](dielectrics.md) ·
[한국어](../../locales/ko/pages/packages/sipi/debye_startup.md)

[Saved inputs](debye_startup_document.md) provide a separate executable request.
