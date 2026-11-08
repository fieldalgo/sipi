# Multiconductor Debye capacitive startup

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_debye_capacitive_startup.md)

`psd_multiconductor_debye_capacitive_ladder_response` returns a separate
`MulticonductorDebyeCapacitiveLadderResponse` for explicit three/four-signal
zero-state finite circuits with a passive capacitor in parallel with the load
resistors. It retains the [PSD Debye line contract](psd_multiconductor_debye_startup.md).

```python
import numpy as np
from sipi import psd_multiconductor_debye_capacitive_ladder_response
t=np.linspace(0.,4e-9,41)
r=psd_multiconductor_debye_capacitive_ladder_response(
    t,np.minimum(t/1e-9,1.)[:,None]*[1.,-.4,.2],signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,
    source_resistance=[25.]*3,load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12)
assert r.voltage.shape==r.current.shape==(41,6)
assert r.load_capacitor_current.shape==(41,3)
assert not np.any(r.polarization_voltage[:,:,1])
assert not np.any(r.load_capacitor_current[:,1])
```

`load_capacitance` is a real exactly symmetric N×N PSD matrix in F, including
zero and rank-one matrices. There is no symmetry repair, eigenvalue clipping
or rank threshold. Any negative computed normalized eigenvalue is rejected,
including numerical sign ambiguity near singularity; this conservative rule
does not accept every floating representation of mathematical PSD matrices.
Tiny positive diagonal capacitances remain nonzero. R[ohm/m], G[S/m] and
1–2 DeltaC[F/m] matrices are PSD; L[H/m] and C_inf[F/m] are SPD with normalized
eigenvalue ratio above1e-12. Relaxation frequencies are positive Hz.

Explicit signals3/4, cells1–64, length[m]>0, and uniform2–10000 time rows starting
at0 are required. Drive shape is(time,N), first row zero. Both resistance
vectors contain N positive finite ohm values. Counts bound resources, not
accuracy/runtime. No scalar broadcasting or ideal/open/short/current/inductive
boundary is inferred. Existing two-signal and resistive multi-signal paths
retain their arithmetic and full-state output hashes.

The far-node mass is `dx/2*C_inf+Cload`. Its derivative uses independent
incoming segment flow minus resistor, shunt and polarization currents.
Far current enters the line: `I_far=-Vfar/Rload-Cload*dVfar/dt`.
`load_resistor_loss=sum(Vfar**2/Rload)`; total terminal current includes the
capacitor and must not be substituted into resistor I²R. The external load
adds no auxiliary state; internal Debye voltages retain `tau*w'=V-w`, no
DeltaC inverse, declared pole order and exactly zero strength columns.

```python
far=r.voltage[:,3:]
np.testing.assert_allclose(r.current[:,3:],-far/100-r.load_capacitor_current,
                           rtol=1e-10,atol=1e-12)
np.testing.assert_array_equal(r.total_energy,r.line_energy+r.load_capacitor_energy)
np.testing.assert_allclose(r.total_energy_rate,
    r.source_power-r.source_resistor_loss-r.load_resistor_loss
    -r.series_loss-r.shunt_loss-r.relaxation_loss,rtol=1e-10,atol=1e-15)
assert max(r.power_balance_relative_error,r.total_power_balance_relative_error)<=1e-10
assert not r.load_capacitor_energy.flags.writeable
assert r.to_dict()['scope']=='finite-passive-multiconductor-psd-debye-capacitive-startup'
```

`line_energy/rate` includes instantaneous and polarization storage only.
`total_energy/rate` additionally includes external `.5*Vfar.T*Cload*Vfar`
and its power. `load_capacitor_current` is(time,N), while load energy/power
are(time,). Terminal order is near N followed by far N, both currents entering
the line. Arrays are detached/read-only; full node/polarization states are
available through `to_dict(include_states=True)`. Line and source power
balances each retain relative1e-10 guards, finite nonnegative storage/loss
and no clipping. Capacitor power may be negative during discharge.

Independent acceptance covers2+1/2+2 block circuits and zero external C at
absolute V1e-10/I1e-12. The one active channel is padded with an uncoupled,
unexcited dummy in the existing two-signal API, not a separate scalar API.
Noncommuting charge-state node KCL integrated by DOP853 requires V1e-8/I1e-9.
The analytical PWL lumped-RC limit requires decreasing error for lengths
.01/.001/.0001m and final error<=1e-3V. Independent scikit-rf2.2.0 modal ABCD
with `Yload=1/R+jωCload` requires decreasing16/32/64-cell errors and final
<=1e-3V at100/500MHz. Separate128/256/512-sample and8/9/10-cycle checks address
PWL and settling errors (horizon difference<=1e-8V). These are specified
fixtures, not arbitrary-band or measured-board accuracy guarantees.

Zero/rank-one/near-zero load matrices, pole columns, signal/pole permutations,
linearity/time/impedance scaling, current/storage partition, copies, finite
guards and original exceptions are tested. [Explicit saved inputs](multiconductor_debye_capacitive_startup_document.md)
preserve this model. [Explicit terminal-wave conversion](multiconductor_debye_capacitive_startup_waves.md)
now admits the separate response class with six/eight real references. No field extraction, arbitrary termination,
fitted dispersion, FFT/TDR, platform integration or measured accuracy is added.
Existing dependencies and notices remain; no new dependency is introduced.
See the [two-signal capacitive contract](debye_capacitive_startup.md).
