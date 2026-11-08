# Three/four-signal Debye startup

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_debye_startup.md)

`multiconductor_debye_rlgc_ladder_response` propagates an explicit finite
zero-state circuit with three or four signals, positive resistive ends and
one or two Debye strengths. It extends the modeling scope of
[constant multiconductor circuits](multiconductor_startup.md) through a separate
API/result class. Existing [two-signal Debye contracts](coupled_debye_startup.md)
keep their original accepted inputs and results.

```python
import numpy as np
from sipi import multiconductor_debye_rlgc_ladder_response

n = 3
time = np.linspace(0., 12e-9, 121)
drive = np.minimum(time / 2e-9, 1.)[:, None] * [1., -.4, .2]
result = multiconductor_debye_rlgc_ladder_response(
    time, drive, signals=n, R=np.diag([20., 23., 26.]),
    L=np.diag([450., 480., 510.]) * 1e-9,
    G=np.diag([.002, .0022, .0024]),
    C_inf=np.diag([210., 220., 230.]) * 1e-12,
    delta_C=np.array([np.diag([130., 143., 156.]),
                      np.diag([50., 55., 60.])]) * 1e-12,
    relaxation_hz=[8e7, 7e8], length=.1, cells=4,
    source_resistance=[25.] * n, load_resistance=[100.] * n)
assert result.voltage.shape == (121, 6)
assert result.polarization_charge.shape == (121, 5, 2, 3)
assert result.power_balance_relative_error <= 1e-10
assert result.total_power_balance_relative_error <= 1e-10
```

At positive-exp(jωt) frequency convention, the supplied capacitance is
`C(f) = C_inf + sum(DeltaC[p] / (1 + j*f/relaxation_hz[p]))`.
R[ohm/m], L[H/m], G[S/m], C_inf and DeltaC[F/m] are finite real exactly symmetric
N×N matrices. L/C_inf must be positive definite. R/G and each DeltaC must be
positive definite or exactly zero. Every nonzero matrix requires normalized
eigenvalue ratio greater than1e-12. No symmetry repair, clipping or singular
PSD admission occurs. Every declared pole is positive finite Hz, including a
zero-strength pole. Source/load resistances are N positive finite real ohms.

`signals` must explicitly be3 or4; cells1..64, times2..10000, uniform spacing
within relative1e-10, time starting0 and drive shape(times,N) with first row0.
The piecewise-linear source starts with all circuit states zero. Counts bound
resources, not runtime or accuracy. Each cell has series R/L and half-weighted
end C_inf/G. Active Debye poles add canonical auxiliary vectors satisfying
`tau*w' = V-w`, with tau=1/(2π fp); exactly zero strengths omit internal states
while preserving declared pole order and zero output columns. Total state count
is N*(2*cells+1) + active_poles*N*(cells+1), at most1036.

Node/segment arrays use(time,node_or_segment,signal); terminal order is all near
signals followed by all far signals, with both terminal currents entering the
line and segment current pointing toward far. Polarization arrays use
(time,node,declared_pole,signal). Charge and current include cell length and
half-end weights: q=dx*weight*DeltaC*w, iq=dx*weight*DeltaC*w'. Instantaneous
energy/rate are separate from polarization energy/rate. Relaxation loss,
R/G losses and source/load resistor losses enter both line/source power balance
checks, each relative1e-10. Finite nonnegative storage/loss is required.

```python
import json
saved_result = result.to_dict(include_states=True)
json.dumps(saved_result, allow_nan=False)
assert result.port_names == ('near_0', 'near_1', 'near_2',
                             'far_0', 'far_1', 'far_2')
assert not result.voltage.flags.writeable
np.testing.assert_allclose(result.total_energy,
                           result.energy + result.polarization_energy,
                           rtol=0., atol=0.)
```

The copied read-only result is a `MulticonductorDebyeRLGCLadderResponse`.
`to_dict` is a result export, not a versioned saved request or executable schema.
The new type is not implicitly admitted to startup-wave adapters. Explicit
[versioned saved input](multiconductor_debye_startup_document.md) preserves this API contract.
Inputs and exported dictionaries are detached; nonfinite propagation, invalid
initial state or failed power checks raise instead of returning a plausible result.

Validation compares diagonal and orthogonal modal cases with scalar Debye
responses, and2+1/2+2 blocks with existing scalar/two-signal equations (absolute
V1e-10/I1e-12). A separate charge-state KCL DOP853 integration tests noncommuting
3/4-signal matrices at V1e-8/I1e-9. The pilot maximum voltage difference was
1.14e-14V. Zero strengths recover constant multiconductor circuits; time,
impedance, source amplitude, signal/pole permutation and lumped units are checked.
Separate slow poles at10k/1k/100Hz approach the constant C_inf response, and
fast poles at10/100/1000GHz approach C_inf+sum(DeltaC), with strictly decreasing
voltage difference and final error below1e-3V for the declared finite circuit.
Forty-eight pre-edit two-signal strict/PSD/external-C/external-RL response exports
preserve exact hashes after the shared helper's default-two-signal dimension change.

For the explicitly tested modal model, independent scikit-rf2.2.0 distributed
ABCD references at100/500MHz have decreasing voltage error for16/32/64 cells.
At64 cells, maxima across3/4 signals are9.43e-6V and2.68e-4V respectively, below
the unchanged1e-3V gate. Separate128/256/512 samples-per-cycle comparisons with
the same finite circuit show decreasing interpolation error. Last-four-cycle
phasors at8/9/10-cycle horizons differ by at most1.51e-10V, below1e-8V.
These criteria are input-specific; refine time/source/space for other uses.
scikit-rf is test-only with existing BSD-3-Clause notices; SciPy remains the
existing propagator dependency. No new runtime dependency is introduced.
For the new three/four-signal path, derivatives use factored relaxation and
node/segment conservation equations to avoid cancellation at fast poles. The
initial fast-pole pointwise power checks failed by up to1.9e-14W; their unchanged
rtol1e-10/atol1e-15 checks pass after this correction. Propagated states and
stored/lost energies remain exactly equal in six before/after cases; the old
two-signal arithmetic is unchanged. Original failure evidence is retained.

This is a lumped circuit, not Maxwell FDTD or a field extraction. General
singular PSD strengths/R/G, ideal/open/short/current-source/reactive ends,
arbitrary dispersion/fitting, measured-board accuracy, application/platform
support and automatic wave/saved integration are outside this contract.
