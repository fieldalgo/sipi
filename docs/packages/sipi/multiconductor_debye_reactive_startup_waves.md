# Multiconductor Debye series RL port waves

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_debye_reactive_startup_waves.md)

`startup_port_waves` explicitly admits `MulticonductorDebyeReactiveLadderResponse`
with six/eight positive real port references. It uses the terminal samples from
the [three/four-signal reactive circuit](multiconductor_debye_reactive_startup.md)
without propagating again. Reference resistance is a supplied diagonal vector,
constant in time; it is not inferred characteristic or modal impedance.

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
from sipi import startup_port_waves
w=startup_port_waves(r,z_ref=[35.,45.,55.,65.,75.,85.])
assert w.source_kind=='MulticonductorDebyeReactiveLadderResponse'
assert w.incident.shape==w.reflected.shape==(41,6)
```

Ports are near N followed by far N. Current enters the line at both ends;
branch current, injected drive and internal segment current cannot replace it.
The original conversion is `a=(V+Zref*I)/(2*sqrt(Zref))` and
`b=(V-Zref*I)/(2*sqrt(Zref))`, in sqrt(W). Thus `a²-b²=V*I` at each port.

```python
root_z=np.sqrt(w.z_ref)
np.testing.assert_allclose(root_z*(w.incident+w.reflected),r.voltage,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose((w.incident-w.reflected)/root_z,r.current,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.incident**2-w.reflected**2,r.voltage*r.current,rtol=1e-10,atol=1e-12)
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

Near power equals source power minus source resistor loss. Far power is the
negative sum of parallel resistor loss, capacitor power, branch-inductor
energy rate and branch resistor loss. External storage can return power;
individual far-port power need not stay negative. The sum of terminal powers
uses internal `line_energy_rate`, not total energy including external C/L.
Original reconstruction and power guards remain relative 1e-10; exported
arrays are detached/read-only and unrepresentable scales fail.

Checks include 12 coupled/diagonal/zero-RG ramp/pulse cases and eight modal
reconstructions with zero/full external capacitance. Each active mode uses
an existing two-signal PSD reactive circuit plus an uncoupled/unexcited dummy
channel. Six/eight-port synthetic phasors independently match scikit-rf2.2.0
Z-to-S to absolute 1e-10 sqrt(W); this is conversion validation, not a new
propagated-line reference. Signal/pole permutations, null-only polarization,
zero/near strengths, rank-one/near capacitance, zero/rank-one/near branch
resistance, explicit references, original-type rejection and finite guards
retain their stated contracts. Eighty-four pre-edit wave exports (21 variants,
two drives and two reference vectors) preserve exact source/installed hashes.

The physical engine is unchanged. Its original eight-cycle settling failure
and qualified longer-horizon scope remain. No arbitrary transient accuracy,
FFT/TDR, propagation solver or runtime dependency is added. Explicit
[saved physical inputs](multiconductor_debye_reactive_startup_document.md)
are available; saved wave versions 1–12 still reject this response kind.
The registry stays at 85 schemas/37 templates at this addition, with no app
or platform integration. See [startup power waves](startup_waves.md).
