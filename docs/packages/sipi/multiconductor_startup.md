# Three/four-signal constant RLGC startup

`multiconductor_rlgc_ladder_response` propagates a finite uniform circuit from
zero stored energy. It takes an explicit `signals=3` or `4`; it does not infer
signal count from matrices. `MulticonductorRLGCLadderResponse` is independent
of the existing [two-signal response](coupled_startup.md).

Provide constant real exactly symmetric N-by-N `R` [ohm/m], `L` [H/m],
`G` [S/m], `C` [F/m]. L/C must be positive definite. R/G must be positive
definite or exactly zero: nonzero singular positive-semidefinite matrices
are outside this first contract. Every nonzero matrix must have normalized
minimum/maximum eigenvalue ratio above 1e-12. There is no symmetrization,
eigenvalue clipping, rank thresholding or scalar broadcasting.

`source_resistance` and `load_resistance` each contain N finite positive ohm
values. `length` is finite positive metres. Required integer `cells=1..128`
gives series R/L and shunt G/C with half shunt weights at both endpoints.
There are N*(2*cells+1) dynamic states. `time` has 2..10000 samples, starts
exactly at zero and has uniform spacing within relative 1e-10. Real PWL
`source_voltages` has shape (times,N), with its first row exactly zero.
No ideal/open/short/reactive/current termination is inferred.

```python
import numpy as np
from sipi import multiconductor_rlgc_ladder_response

time = np.linspace(0., 12e-9, 121)
r = multiconductor_rlgc_ladder_response(time,
    np.minimum(time/2e-9, 1.)[:, None]*[1., -.4, .2], signals=3,
    R=np.diag([20., 23., 26.]), L=np.diag([450., 470., 490.])*1e-9,
    G=np.diag([.002, .0022, .0024]), C=np.diag([210., 220., 230.])*1e-12,
    length=.1, cells=16, source_resistance=[25., 25., 25.],
    load_resistance=[100., 100., 100.])
assert r.voltage.shape == (121, 6)
assert r.port_names == ('near_0', 'near_1', 'near_2', 'far_0', 'far_1', 'far_2')
np.testing.assert_allclose(r.line_power,
    r.energy_rate+r.series_loss+r.shunt_loss, rtol=1e-10, atol=1e-12)
np.testing.assert_allclose(r.source_power,
    r.energy_rate+r.series_loss+r.shunt_loss+r.source_resistor_loss+r.load_resistor_loss,
    rtol=1e-10, atol=1e-12)
assert r.to_dict(include_states=True)['states_included']
```

Terminal ordering is all near signals then all far signals. Both terminal
currents enter the line; interior segment currents point from near to far.
Node voltage has shape (times,cells+1,N), segment current (times,cells,N),
and terminal V/I (times,2*N). Responses copy arrays and expose them read-only;
`inputs` returns a fresh snapshot. `to_dict(include_states=True)` includes
interior states; the default omits them. This result serialization is not a
versioned saved-input schema. Existing saved and two/four-port wave adapters
do not implicitly accept this response.

Stored energy and losses sum all signals. The signed identities are
`line_power = energy_rate + series_loss + shunt_loss` and
`source_power = energy_rate + series_loss + shunt_loss + source_resistor_loss
+ load_resistor_loss`. Both line/source relative residual guards are 1e-10,
with zero scale handled exactly. Finite coefficient/state/diagnostic and
nonnegative storage/loss guards remain mandatory. Negative terminal power
is retained. Power conservation does not establish physical accuracy.

Validation covers both N=3 and N=4: decoupled scalar and original 2+1/2+2
block limits (1e-10 V/1e-12 A), independent noncommuting node KCL integrated
with SciPy DOP853 (1e-8 V/1e-9 A), and continuous scalar modal ABCD from
scikit-rf 2.2.0. Modal 32/64/128-cell errors decrease at 100 MHz, 500 MHz
and 1 GHz, with finest error at most 1 mV for the documented test fixtures.
At 100 MHz, 256/512/1024 samples per cycle refine the finite-cell frequency
reference; 7/8/9-cycle horizons differ by at most 1e-8 V. Tests retain the
explicit horizons and gates. These are fixture-specific acceptance results,
not an error bound for arbitrary inputs. Pulse/zero/lossless behavior,
conductor permutation, amplitude/time/impedance scaling, copies, invalid
matrices, extreme scales and propagation failures have separate coverage.

The model solves a finite constant-RLGC circuit with SciPy PWL state-space
propagation. It does not extract fields, model arbitrary material dispersion,
provide full-wave transients or infer measured TDR. Independently check
source/time/spatial convergence for each intended input. Counts do not
promise runtime or accuracy. See [development](../../development.md) for
exact installed-artifact validation and reference-tool versions.

[Saved three/four-signal inputs](multiconductor_startup_document.md) preserve explicit signal count, SI inputs and actual time-row budgets.

[Terminal waves](startup_waves.md) explicitly accept this response with six/eight ports. Existing saved wavev1..8 keep their original input kinds.
