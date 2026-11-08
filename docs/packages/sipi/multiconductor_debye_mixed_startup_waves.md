# Multiconductor Debye typed-source port waves

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_debye_mixed_startup_waves.md)

`startup_port_waves` explicitly admits
`MixedSourceMulticonductorDebyeReactiveLadderResponse` with six/eight positive
real port references. It converts terminal samples from the [typed-source
circuit](multiconductor_debye_mixed_startup.md) without another propagation.
The diagonal reference vector is constant in time; characteristic or modal
impedance is not inferred. Original typed V/A source samples remain distinct
from into-line terminal currents.

```python
import numpy as np
from sipi import psd_multiconductor_debye_mixed_reactive_ladder_response
t=np.linspace(0.,4e-9,41)
drive=np.minimum(t/1e-9,1.)
sources=[dict(kind='current',current_a=(.02*drive).tolist(),shunt_conductance_s=0.),
         dict(kind='voltage',voltage_v=(-.4*drive).tolist(),series_resistance_ohm=50.),
         dict(kind='current',current_a=(.004*drive).tolist(),shunt_conductance_s=.01)]
r=psd_multiconductor_debye_mixed_reactive_ladder_response(
    t,sources,signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
assert r.source_kinds==('current','voltage','current')
assert r.source_units==('A','V','A')
assert r.inputs['sources']==sources
assert r.voltage.shape==r.current.shape==(41,6)
assert r.source_values.shape==(41,3)
from sipi import startup_port_waves
w=startup_port_waves(r,z_ref=[35.,45.,55.,65.,75.,85.])
assert w.source_kind=='MixedSourceMulticonductorDebyeReactiveLadderResponse'
assert w.incident.shape==w.reflected.shape==(41,6)
```

Ports are near N followed by far N, with both terminal currents entering the
line. A voltage source contributes `(Vs-Vnear)/Rs` amperes at the near terminal;
a current source contributes `Iinj-Gs*Vnear`. The mixed-unit `source_values`
array cannot replace these currents. Internal segment, capacitor and branch
currents remain distinct. The unchanged conversion is
`a=(V+Zref*I)/(2*sqrt(Zref))`, `b=(V-Zref*I)/(2*sqrt(Zref))` in sqrt(W).
Per-port `a²-b²` equals terminal `V*I`.

```python
root_z=np.sqrt(w.z_ref)
np.testing.assert_allclose(root_z*(w.incident+w.reflected),r.voltage,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose((w.incident-w.reflected)/root_z,r.current,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,:3].sum(axis=1),
    r.source_power-r.source_series_resistor_loss-r.source_shunt_resistor_loss,
    rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,3:].sum(axis=1),
    -r.load_resistor_loss-r.load_capacitor_power-r.load_branch_energy_rate-r.load_branch_resistor_loss,
    rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power.sum(axis=1),
    r.line_energy_rate+r.series_loss+r.shunt_loss+r.relaxation_loss,rtol=1e-10,atol=1e-12)
other=startup_port_waves(r,z_ref=2*w.z_ref)
np.testing.assert_array_equal(other.port_power,w.port_power)
assert not w.incident.flags.writeable
assert max(w.voltage_reconstruction_relative_error,w.current_reconstruction_relative_error,
           w.power_balance_relative_error)<=1e-10
```

Near power excludes both voltage-source series loss and current-source shunt
loss. Far power is minus the parallel resistor loss, capacitor power, branch
inductor energy rate and branch resistor loss. External storage may return
power. The sum uses internal `line_energy_rate`, excluding external C/L energy.
Original relative1e-10 reconstruction/power guards, detached readonly exports
and nonrepresentable-scale rejection remain unchanged.

Tests cover all 24 voltage/current masks across three/four signals with two
drives, compared against explicit Norton and Thevenin terminal waves at
positive conductances. Other cases include ideal current sources, partly
shunted and near-zero shunts, separate source power/loss accounting, twelve
coupled/diagonal/zero-RG ramp/pulse cases and reference invariance.
Eight zero-Debye-strength modal comparisons use uniform Gs.02S, external C0/full,
and the existing constant two-signal Norton circuit with an unexcited dummy.
Only equivalent injected amperes are transformed into modes; mixed-unit V/A
samples are never treated as one physical vector.

Independent six/eight-port synthetic phasors match scikit-rf2.2.0 Z-to-S within
1e-10 sqrt(W). This checks conversion, not propagated-line accuracy. Signal/pole
permutations, null polarization, near PSD strengths, external C/Rbranch ranks,
strict references, source/terminal distinction and finite/shape guards are
checked. One hundred prior full-wave exports (25 kinds, two drives, two
reference vectors) retain exact source/installed hashes.

Only explicit result-type admission changes; physical equations and wave
arithmetic stay unchanged. Failed low-loss/short-horizon studies and the
qualified damped PWL continuum scope retain their limits. There is no new
arbitrary-transient accuracy, FFT/TDR, mode extraction or dependency claim.
[Typed input saving](multiconductor_debye_mixed_startup_document.md) is supported;
saved wave versions1–14 still reject this kind. At the native-wave addition the registry contained
89 schemas/37 templates. Browser/desktop candidates are unchanged.
See [startup power waves](startup_waves.md).


[Explicit saved wave version15](startup_waves_document_v15.md) adds typed multiconductor Debye inputs, preserving versions1–14. The registry becomes90 schemas/37 templates at this addition.
