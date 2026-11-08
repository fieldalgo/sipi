# Multiconductor Debye series RL load startup

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_debye_reactive_startup.md)

`psd_multiconductor_debye_reactive_ladder_response` returns a separate
`MulticonductorDebyeReactiveLadderResponse`. An explicit series RL branch is
parallel to the existing load resistance and external capacitor of the
[three/four-signal PSD Debye circuit](multiconductor_debye_capacitive_startup.md).

```python
import numpy as np
from sipi import psd_multiconductor_debye_reactive_ladder_response
t=np.linspace(0.,4e-9,41)
r=psd_multiconductor_debye_reactive_ladder_response(
    t,np.minimum(t/1e-9,1.)[:,None]*[1.,-.4,.2],signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,
    source_resistance=[25.]*3,load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
assert r.voltage.shape==r.current.shape==(41,6)
assert r.load_branch_current.shape==(41,3)
assert not np.any(r.polarization_voltage[:,:,1])
```

Every external matrix is real, exactly symmetric N×N. Cload[F] and Rbranch[ohm]
are PSD, including zero and rank-one; Lbranch[H] is SPD with normalized
eigenvalue ratio>1e-12. No absent branch, symmetry repair, eigenvalue clipping
or rank threshold is inferred. Negative computed PSD eigenvalues are rejected
conservatively even near singularity, so not every floating representation
of mathematical PSD is accepted. Small positive entries remain unchanged.

Original line inputs retain R[ohm/m],G[S/m],1–2 DeltaC[F/m] PSD matrices,
L[H/m]/C_inf[F/m] SPD ratio>1e-12 and positive relaxation frequencies[Hz].
Explicit signals3/4, cells1–64, length[m]>0, uniform2–10000 time rows starting0,
drive(time,N) with first row0, and N positive finite source/load resistances
are required. Counts bound resources, not accuracy/runtime. There is no
automatic horizon, scalar broadcasting or arbitrary boundary inference.

Branch current leaves the far line into the load and starts at zero:
`Lbranch*di/dt=Vfar-Rbranch*i`. The far-node mass remains `dx/2*C_inf+Cload`;
its incoming flow also subtracts the branch current. Into-line terminal current
is `-Vfar/Rload-Cload*dVfar/dt-i`. Parallel resistor loss is `sum(Vfar**2/Rload)`;
branch resistor loss is separately `i.T*Rbranch*i`. Neither uses total terminal
current as its resistor current. The branch adds N states; Debye auxiliary
voltages retain canonical `tau*w'=V-w`, declared pole order and zero columns.

```python
far=r.voltage[:,3:]
np.testing.assert_allclose(r.current[:,3:],
    -far/100-r.load_capacitor_current-r.load_branch_current,rtol=1e-10,atol=1e-12)
np.testing.assert_array_equal(r.total_energy,
    r.line_energy+r.load_capacitor_energy+r.load_branch_energy)
np.testing.assert_allclose(r.total_energy_rate,
    r.source_power-r.source_resistor_loss-r.load_resistor_loss
    -r.load_branch_resistor_loss-r.series_loss-r.shunt_loss-r.relaxation_loss,
    rtol=1e-10,atol=1e-15)
assert max(r.power_balance_relative_error,r.total_power_balance_relative_error)<=1e-10
assert not r.load_branch_current.flags.writeable
assert r.to_dict()['scope']=='finite-passive-multiconductor-psd-debye-reactive-startup'
```

`line_energy/rate` includes internal instantaneous and polarization storage.
`total_energy/rate` additionally includes external capacitor and branch-inductor
storage. Branch energy is `.5*i.T*Lbranch*i`; its rate equals `Vfar.T*i` minus
branch loss. Branch current is(time,N); energy/rate/loss are(time,). Storage
and losses must be finite/nonnegative; energy rates can be negative on discharge.
Both line and source power guards remain relative1e-10 without clipping.
Terminal order is near N followed by far N, with currents entering the line.
Outputs are detached/read-only, and `to_dict(include_states=True)` exports
internal node and polarization states. Existing two-signal and multi-signal
circuits without a branch retain their original arithmetic and full outputs.

Independent checks compare2+1/2+2 existing two-signal reactive circuits at
absolute V1e-10/I1e-12. One active channel uses an uncoupled/unexcited dummy
channel, not a separate scalar reactive API. Separate noncommuting charge-state
KCL with a branch-current state uses DOP853, requiring V1e-8/I1e-9 and branch
current1e-9A. Large explicit Lbranch scales100/1000/10000 approach the existing
capacitive model with decreasing voltage error and final<=1e-3V. With Cload,
line R/G and strengths zero, lengths .01/.001/.0001m approach the analytical
PWL lumped-RL limit with decreasing error and final<=1e-3V.

Independent scikit-rf2.2.0 modal ABCD uses
`Yload=1/R+jωCload+1/(Rbranch+jωLbranch)`. Spatial16/32/64-cell errors must
decrease, with final<=1e-3V at100/500MHz. Time128/256/512-sample errors must
decrease against a separate finite-pi frequency solve. The original three-signal
8→9-cycle settling difference was1.0230294e-7V, exceeding the1e-8V gate;
that failed condition is retained and is not claimed accepted. A separate
longer-horizon qualification keeps the same gate:9/10/11 cycles at512 samples,
plus9/9.25/9.5 cycles at1024 samples. Spatial checks use100MHz9cycles1024samples
and500MHz30cycles256samples, within the10000-row budget. The candidate numerical
code and all tolerances were unchanged. These specified fixtures do not establish
arbitrary-band, arbitrary-horizon or measured-board accuracy.

Zero/rank-one/near-zero external matrices, storage/current partition,
linearity/time/impedance/signal/pole invariants, declared zero strengths,
strict inputs, readonly copies and original failures are checked. Existing96
full-state outputs retain exact source/installed hashes. This separate class
does not yet enter saved or wave APIs. No general RLC topology, field extraction,
fitted material, FFT/TDR, platform integration or new dependency is added.
See the [two-signal reactive contract](debye_reactive_startup.md).
