# Multiconductor Debye current-source port waves

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_debye_norton_startup_waves.md)

`startup_port_waves` explicitly admits
`NortonMulticonductorDebyeReactiveLadderResponse` with six/eight positive real
port references. It converts terminal samples from the [current-source
circuit](multiconductor_debye_norton_startup.md) without another propagation.
The supplied diagonal reference vector is constant in time; characteristic
or modal impedance is not inferred.

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
from sipi import startup_port_waves
w=startup_port_waves(r,z_ref=[35.,45.,55.,65.,75.,85.])
assert w.source_kind=='NortonMulticonductorDebyeReactiveLadderResponse'
assert w.incident.shape==w.reflected.shape==(41,6)
```

Ports are near N followed by far N; both terminal currents enter the line.
Near current is injected current minus `Gs*Vnear`, so injected amperes cannot
replace the terminal current. Segment, capacitor and branch currents also
remain distinct. The original conversion is
`a=(V+Zref*I)/(2*sqrt(Zref))`, `b=(V-Zref*I)/(2*sqrt(Zref))` in sqrt(W).
Per-port wave power `a²-b²` equals terminal `V*I`.

```python
root_z=np.sqrt(w.z_ref)
np.testing.assert_allclose(root_z*(w.incident+w.reflected),r.voltage,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose((w.incident-w.reflected)/root_z,r.current,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,:3].sum(axis=1),
    r.source_power-r.source_shunt_resistor_loss,rtol=1e-10,atol=1e-12)
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

Near terminal power excludes source shunt loss. Far power is the negative
sum of parallel resistor loss, capacitor power, branch-inductor energy rate
and branch resistor loss. External storage can return power; individual port
power need not stay negative. The sum of terminal powers uses internal
`line_energy_rate`, not total energy including external C/L storage. Original
relative1e-10 reconstruction/power guards, detached readonly exports and
nonrepresentable-scale rejection remain.

Checks cover coupled/diagonal/zero-RG ramp/pulse cases, ideal/partly shunted/
positive/near-zero source conductances, full Debye positive-Gs Thevenin wave
equivalence, and sixteen zero-Debye-strength modal reconstructions. The latter
uses uniform Gs0 or.02S so it commutes with the modal transform, zero/full
external C, and an existing constant two-signal Norton reactive circuit with
one unexcited dummy channel. This does not assume a two-signal Norton Debye API.

Six/eight-port synthetic phasors independently match scikit-rf2.2.0 Z-to-S
within1e-10 sqrt(W), testing conversion rather than a propagated line.
Signal/pole permutations, null polarization, near PSD strengths, external
C/Rbranch rank limits, explicit references, source/terminal distinction and
finite/shape guards are checked. Ninety-two pre-edit wave exports (23 kinds,
two drives, two reference vectors) preserve exact source/installed hashes.

Only explicit type admission changes; the wave formula and physical engine
are unchanged. The engine's failed low-loss PWL/short-horizon conditions and
qualified damped continuum scope remain. No arbitrary transient accuracy,
FFT/TDR, eigenmode extraction or new dependency is added. Strict [saved current
inputs](multiconductor_debye_norton_startup_document.md) are available; saved
wave versions1–13 still reject this kind. At the native-wave addition the library registry contained
87 schemas/37 templates, with no browser/desktop deployment change.
See [startup power waves](startup_waves.md).


[Explicit saved wave version14](startup_waves_document_v14.md) now admits this kind; versions1–13 retain their original rejection. This addition brings the common registry to88 schemas/37 templates.
