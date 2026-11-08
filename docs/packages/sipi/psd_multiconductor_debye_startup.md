# Multiconductor PSD Debye startup

**English** | [한국어](../../locales/ko/pages/packages/sipi/psd_multiconductor_debye_startup.md)

`psd_multiconductor_debye_rlgc_ladder_response` returns a separate
`PSDMulticonductorDebyeRLGCLadderResponse` for three/four-signal zero-state
finite circuits. It admits singular positive-semidefinite R/G and Debye
strength matrices. The [strict-strength API](multiconductor_debye_startup.md)
and its saved/wave contracts retain their previous restrictions.

```python
import numpy as np
from sipi import psd_multiconductor_debye_rlgc_ladder_response

t = np.linspace(0., 4e-9, 41)
r = psd_multiconductor_debye_rlgc_ladder_response(
    t, np.minimum(t/1e-9, 1.)[:, None]*[1., -.4, .2], signals=3,
    R=np.diag([20., 0., 26.]), L=np.diag([450., 480., 510.])*1e-9,
    G=np.diag([.002, .0022, 0.]), C_inf=np.diag([210., 220., 230.])*1e-12,
    delta_C=np.array([np.diag([150., 0., 0.]), np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7, 7e8], length=.1, cells=4,
    source_resistance=[25.]*3, load_resistance=[100.]*3)
assert r.voltage.shape == r.current.shape == (41, 6)
assert r.polarization_voltage.shape == (41, 5, 2, 3)
assert np.any(r.polarization_voltage[:, :, 0, 1:])
assert not np.any(r.polarization_charge[:, :, 0, 1:])
assert not np.any(r.polarization_voltage[:, :, 1])
assert r.inputs['signals'] == 3
```

Inputs are explicit real exactly symmetric N×N matrices. R[ohm/m],G[S/m] and
each of1–2 DeltaC[F/m] are PSD. L[H/m] and C_inf[F/m] must be SPD with
normalized eigenvalue ratio above1e-12. Positive relaxation frequencies use Hz:
`C(f)=C_inf+sum(DeltaC/(1+j*f/fp))`. There is no symmetry repair, negative
eigenvalue clipping or rank threshold. Every negative computed normalized
eigenvalue is rejected, including numerical sign ambiguity near singularity;
this conservative rule does not accept every floating representation of a
mathematically PSD matrix. Tiny positive diagonal strengths remain nonzero.

Explicit `signals` is3 or4; `cells` is1–64. Uniform time has2–10000 rows,
starts at0 and matches drive shape(time,N), whose first row is zero. Both
source/load resistance vectors require N positive finite values. Length uses
metres. No scalar resistance broadcasting or ideal/open/short/reactive/current
boundary is inferred. Counts bound resources, not accuracy or execution time.

The finite pi circuit uses half shunt capacitance/conductance at both ends.
For each nonzero strength, canonical auxiliary voltage obeys `tau*w'=V-w`,
without inverting DeltaC. Null-direction w is an unobservable low-pass state,
not a measured polarization coordinate; it contributes no polarization charge,
current, energy or relaxation loss. Exactly zero strengths omit states and
preserve zero output columns and declared pole order. Arrays are
(time,node,pole,signal); charge/current include lumped node capacitance and
half-end weights in C/A. State count is N*(2*cells+1)+active_poles*N*(cells+1).
SciPy lsim propagates the zero-state PWL interpolant through the existing
canonical PSD kernel; existing two-signal and strict multi-signal paths stay
unchanged. Algebraically factored derivatives retain the multi-signal power
checks without subtracting large relaxation matrix products.

```python
np.testing.assert_allclose(
    r.total_energy_rate,
    r.line_power - r.series_loss - r.shunt_loss - r.relaxation_loss,
    rtol=1e-10, atol=1e-15)
assert max(r.power_balance_relative_error,
           r.total_power_balance_relative_error) <= 1e-10
assert not r.polarization_charge.flags.writeable
assert r.port_names == ('near_0', 'near_1', 'near_2', 'far_0', 'far_1', 'far_2')
assert r.to_dict()['scope'] == 'finite-passive-psd-multiconductor-debye-ladder-startup'
```

Terminal order is near N followed by far N; both terminal currents enter the
line. Instantaneous and polarization energy/rates are separate. Series, shunt,
relaxation, source-resistor and load-resistor losses are nonnegative; line and
source balances each retain relative1e-10 guards. Nonfinite, unrepresentable
or negative diagnostics fail without clipping. Exports are detached/read-only;
`to_dict(include_states=True)` includes node and polarization states.

Independent validation covers diagonal/block scalar Debye modes and2+1/2+2
PSD block circuits at absolute V1e-10/I1e-12, and separate noncommuting
charge-state node KCL integrated by DOP853 at V1e-8/I1e-9. Independent
scikit-rf2.2.0 distributed scalar ABCD checks require decreasing16/32/64-cell
error and finest voltage error <=1e-3V at100/500MHz. Separate128/256/512-sample
and8/9/10-cycle checks address PWL and settling errors. These are specified
fixtures, not arbitrary frequency-band or board accuracy guarantees.
Null/near-zero strengths, positive-strength agreement, pole/signal permutations,
linearity/time/impedance scaling, slow/fast pole limits, original strict API
rejection, readonly copies and original failure gates are checked.64 old
full-state exports are retained exactly in source and installed runs.

[Explicit saved inputs](psd_multiconductor_debye_startup_document.md) now preserve
this API. [Explicit terminal-wave conversion](psd_multiconductor_debye_startup_waves.md)
accepts its separate response class with six/eight positive real references. It adds no
field extraction, fitted dispersion, arbitrary boundary, FFT/TDR, platform
integration or measured accuracy. See the [two-signal PSD contract](psd_debye_startup.md).
SciPy/scikit-rf remain existing dependencies/test references with existing
notices; no new dependency is introduced.
