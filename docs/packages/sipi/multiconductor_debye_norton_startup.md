# Multiconductor Debye current-source startup

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_debye_norton_startup.md)

`psd_multiconductor_debye_norton_reactive_ladder_response` returns a separate
`NortonMulticonductorDebyeReactiveLadderResponse`. It adds explicit injected
currents and parallel source conductances to the [three/four-signal PSD Debye
circuit with external C and series RL loads](multiconductor_debye_reactive_startup.md).

```python
import numpy as np
from sipi import psd_multiconductor_debye_norton_reactive_ladder_response
t=np.linspace(0.,4e-9,41)
drive=.02*np.minimum(t/1e-9,1.)[:,None]*[1.,-.4,.2]
r=psd_multiconductor_debye_norton_reactive_ladder_response(
    t,drive,signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,
    source_shunt_conductance=[0.,.02,0.],load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
assert r.voltage.shape==r.current.shape==(41,6)
assert r.source_currents.shape==r.load_branch_current.shape==(41,3)
assert not np.any(r.polarization_voltage[:,:,1])
```

`source_currents` is in amperes, shape(time,N), with first row zero.
`source_shunt_conductance` is an N-vector of finite nonnegative siemens; zero
means an ideal current source. No scalar broadcast, inferred Thevenin input,
ideal short or mixed source type is accepted. `source_currents_a` and
`source_shunt_conductance_s` are explicit canonical input fields. Source voltage,
source resistance and series-resistor-loss aliases are absent.

Near into-line current is `Iin-Gs*Vnear`. Supplied source power is
`sum(Iin*Vnear)`; `source_shunt_resistor_loss=sum(Gs*Vnear**2)` is separate.
Positive Gs is equivalent at the line to explicit `Vs=Iin/Gs, Rs=1/Gs`, while
the source power partitions differ. The internal positive placeholder used to
reuse time/line/load validation is never used in propagation or exported inputs.

```python
near=r.voltage[:,:3]
np.testing.assert_allclose(r.current[:,:3],drive-near*[0.,.02,0.],rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(r.source_power,np.sum(drive*near,axis=1),rtol=1e-10,atol=1e-15)
np.testing.assert_array_equal(r.total_energy,
    r.line_energy+r.load_capacitor_energy+r.load_branch_energy)
np.testing.assert_allclose(r.total_energy_rate,
    r.source_power-r.source_shunt_resistor_loss-r.load_resistor_loss
    -r.load_branch_resistor_loss-r.series_loss-r.shunt_loss-r.relaxation_loss,
    rtol=1e-10,atol=1e-15)
assert max(r.power_balance_relative_error,r.total_power_balance_relative_error)<=1e-10
assert not r.source_currents.flags.writeable
assert 'source_voltages_v' not in r.inputs
assert r.to_dict()['scope']=='finite-passive-multiconductor-psd-debye-norton-reactive-startup'
```

Original passive line and load contracts remain: N=3 or4, cells1–64,
positive length[m], uniform2–10000 time rows starting0, one/two positive Debye
pole frequencies[Hz], real exactly symmetric matrices. R[ohm/m],G[S/m],
DeltaC[F/m], Cload[F] and Rbranch[ohm] are PSD. L[H/m],C_inf[F/m] and
Lbranch[H] are SPD with normalized eigenvalue ratio>1e-12; load resistances
are positive finite N-vectors. Computed negative PSD eigenvalues are rejected
conservatively, without symmetry repair, clipping or a rank cutoff. Small
positive strengths and declared zero pole columns are preserved.

The far into-line current remains `-Vfar/Rload-Cload*dVfar/dt-Ibranch`, with
`Lbranch*dIbranch/dt=Vfar-Rbranch*Ibranch` and zero initial state. Parallel
load-resistor and branch-resistor losses remain separate. `line_energy/rate`
contains instantaneous plus polarization storage; `total_energy/rate` also
includes external C/L storage. Both relative1e-10 power guards, finite
nonnegative storage/loss checks, readonly arrays and detached input/export
copies remain. Counts limit resources, not accuracy or execution time.

Independent physical checks cover positive-Gs Thevenin equivalence, zero
Debye-strength two-signal blocks, noncommuting charge/branch-KCL DOP853
(V1e-8/I1e-9/branchI1e-9), the Gs→0 limit and the analytical short-line PWL
RL limit. Source/installed regression preserves112 old full-state hashes.

Frequency and transient evidence are distinguished. Pure-frequency finite-pi
KCL converges toward scikit-rf2.2.0 continuum modal ABCD at100/500MHz for
16/32/64cells, with strict error decrease and final<=1e-3V. For periodic PWL
input sampled N times per cycle, the sampled fundamental sums harmonic
transfers at `k=1+m*N`, weighted by `sinc(k/N)**2`; negative frequencies use
conjugate transfer. This matches the actual input rather than treating its
interpolant as a continuous sinusoid. Independent finite-pi PWL KCL agrees
with original-fixture transient endpoints within1e-8V at72cycles128samples.
That finite-circuit check does not establish continuum spatial convergence.

The original low-loss100MHz16/18/19cycle settling check failed the1e-8V gate
(max8.889e-7V). Extending to48/60/72cycles at128samples passed settling but
failed strict spatial error decrease, including after matching the continuum
PWL input. A fixed24-condition frequency survey also retained nonmonotonic
100MHz cases at128/256samples. These failed conditions remain unqualified.
A separate spectral fixture scales only line R/G by10; its short100MHz
8/8.5/9cycle and500MHz28/30/32cycle horizons also failed (max1.259e-5V and
1.454e-7V). These are not accepted by changing tolerances.

For that same damped fixture, longer qualified horizons are100MHz16/18/19
cycles at512samples and500MHz64/72/76cycles at128samples. The1e-8V horizon
gate passes; input interpolation errors at128/256/512samples decrease.
Spatial16/32/64cell comparisons use19cycles512samples and76cycles128samples
respectively. Matching continuum PWL aliases8192/16384/32768 converge within
1e-8V; the constant-transfer coefficient check is1e-8. Spatial errors strictly
decrease, finest<=1e-3V. Every candidate spatial endpoint also agrees within
1e-8V with independent finite-pi PWL aliases32/64/128, checking actual settling.
The candidate equations and thresholds were unchanged through these studies.
Qualified fixtures do not guarantee arbitrary bandwidth, horizon or measured
board accuracy. The last-four-cycle phasor window must itself be settled.

The separate result can be replayed through the strict saved-input document;
terminal-wave APIs do not yet admit it.
No general SPICE topology, ideal source short, field extraction, FFT/TDR,
platform integration or new runtime dependency is added.


[Saved current-source inputs](multiconductor_debye_norton_startup_document.md) preserve explicit amperes and source conductances with a strict versioned schema.
