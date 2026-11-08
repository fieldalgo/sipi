# Two-signal Debye startup with PSD strengths

`psd_coupled_debye_rlgc_ladder_response` admits singular positive semidefinite
(PSD) relaxation strengths in an explicitly specified finite circuit. A
rank-one strength can act on only one voltage combination. This is a separate
API and response class; the [strict positive-strength API](coupled_debye_startup.md)
and its saved documents retain their original restrictions.

## Physical contract

All matrices are real, exactly symmetric2x2. R/G and each of1..2 DeltaC
strengths must be PSD. Negative computed eigenvalues reject without clipping
or symmetry repair. L and C_inf remain positive definite with normalized
eigenvalue ratio above1e-12. DeltaC has no positive-rank threshold: a small
positive eigenvalue stays positive, while an exact zero is permitted.
The declared capacitance is C_inf+sum(DeltaC/(1+j*f/relaxation_hz)).
Inputs use ohm/m,H/m,S/m,F/m,Hz,m; each source/load has two finite positive
ohms. Ideal/open/short, reactive and current-source boundaries are unsupported.

Explicit1..128 cells use half shunts at each end. Uniform2..10000 time samples
start at0; the two-column voltage drive starts with a zero row. SciPy lsim
propagates its PWL interpolant from the zero state. Counts are resource bounds,
not convergence or runtime guarantees. There is no automatic horizon extension.

## Singular strengths without a matrix inverse

For each nonzero declared pole, canonical auxiliary voltage w obeys
`tau*w'=V-w`, where tau=1/(2*pi*relaxation_hz). Its dynamics do not invert
DeltaC. Charge is node-lumped `weight*dx*DeltaC*w`, and current is its time
derivative. A null-direction component of w is a selected zero-state low-pass
realization, not an observable material polarization. It carries zero charge,
energy and relaxation loss in that direction. Exactly zero matrices omit the
auxiliary states and keep zero output columns; pole order/repeats are preserved.

Storage is .5*weight*dx*w.T*DeltaC*w and relaxation loss is
weight*dx*(V-w).T*DeltaC*(V-w)/tau. Instantaneous C_inf/L energy remains
separate. Finite nonnegative storage/loss and line/source power balance within
relative1e-10 are required without clipping. Unrepresentable cell coefficients,
underflowed nonzero strengths, nonfinite propagation and nonzero initial states
reject. The original strict-SPD path shares propagation bookkeeping while
retaining its original mass/coupling arithmetic and admissibility checks.

```python
from sipi import psd_coupled_debye_rlgc_ladder_response
import numpy as np

time = np.linspace(0., 12e-9, 121)
response = psd_coupled_debye_rlgc_ladder_response(time,
    np.minimum(time/2e-9, 1.)[:, None]*[1., -.4],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -150.], [-150., 150.]],
                      [[50., 50.], [50., 50.]]])*1e-12,
    relaxation_hz=[1e9, 1e8], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.])
assert response.voltage.shape == (121, 4)
assert response.polarization_charge.shape == (121, 17, 2, 2)
assert response.power_balance_relative_error <= 1e-10
assert response.total_power_balance_relative_error <= 1e-10
np.testing.assert_allclose(response.line_power,
    response.total_energy_rate + response.series_loss + response.shunt_loss
    + response.relaxation_loss, rtol=1e-10, atol=1e-12)
assert response.to_dict()['scope'] == 'finite-passive-two-signal-psd-debye-ladder-startup'
```

## Output and verification limits

`PSDCoupledDebyeRLGCLadderResponse` copies finite read-only arrays. Four terminals
are near_0,near_1,far_0,far_1, currents into the line. Polarization voltage,
node-lumped charge and current are(time,node,pole,conductor). Internal states
are omitted from JSON unless `include_states=True`. This independent response
does not implicitly enter prior contracts. The [terminal wave adapter](startup_waves.md) now explicitly accepts this response; saved wave v1..5 still reject PSD saved inputs.

Independent diagonal/exchange scalar modes, zero-strength constant RLGC and
strict-SPD full-state limits are checked. A separate noncommuting rank-one
charge-state KCL integration uses DOP853, not the candidate circuit matrix.
Its terminal limits are1e-8V/1e-9A; scalar limits are1e-10V/1e-12A.
For an explicit exchange fixture,100MHz finite-pi comparisons improve with
256/512/1024 samples per cycle and7/8/9-cycle phasor differences stay below1e-8V.
Continuous modal ABCD comparisons improve across32/64/128 cells at100MHz,
500MHz and1GHz, with finest voltage error below1mV. The100MHz case uses8cycles
and1024 samples/cycle;500MHz/1GHz use20cycles and256samples/cycle. These
fixture-specific checks do not establish a universal discretization rule.

Rank-one/near-singular/null-direction cases, scaling, permutations, strict
inputs, copies, finite failures and original propagation exceptions are tested.
Sixteen original strict-SPD cases preserve full physical/saved/wave JSON hashes.
Existing NumPy/SciPy and test-only scikit-rf versions/licenses are reused;
there is no new runtime dependency. No geometry/material extraction, general
fitting, measured accuracy, browser or Windows integration is established.

[한국어](../../locales/ko/pages/packages/sipi/psd_debye_startup.md)

[Separate PSD saved inputs](psd_debye_startup_document.md) preserve singular matrices and original time samples; saved waves remain separate.

[External capacitive-load API](debye_capacitive_startup.md) separates internal polarization from external storage.
