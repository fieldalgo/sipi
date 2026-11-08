# Multiconductor mixed-boundary port waves

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_boundary_startup_waves.md)

`startup_port_waves` explicitly accepts `MixedBoundaryMulticonductorRLGCLadderResponse`
with six/eight positive real references. It converts the sampled terminal V/I
from the [constant mixed-boundary circuit](multiconductor_boundary_startup.md)
without propagating again. References are constant diagonal port resistances;
characteristic or modal impedance is not inferred.

```python
import numpy as np
from sipi import multiconductor_boundary_ladder_response
t=np.linspace(0.,4e-9,41)
drive=np.minimum(t[:,None]/1e-9,1.)*np.array([1.,-.4,.2])
r=multiconductor_boundary_ladder_response(t,drive,signals=3,
    R=np.array([[20.,-20.,0.],[-20.,20.,0.],[0.,0.,0.]]),
    L=np.array([[450.,60.,0.],[60.,480.,60.],[0.,60.,510.]])*1e-9,
    G=np.array([[0.,0.,0.],[0.,.002,.002],[0.,.002,.002]]),
    C=np.array([[210.,-20.,0.],[-20.,220.,-20.],[0.,-20.,230.]])*1e-12,
    length=.1,cells=8,source_resistance=[0.,25.,0.],
    load_resistance=[None,0.,75.])
assert r.voltage.shape==r.current.shape==(41,6)
assert r.node_voltage.shape==(41,9,3) and r.segment_current.shape==(41,8,3)
np.testing.assert_array_equal(r.voltage[:,[0,2]],drive[:,[0,2]])
assert not np.any(r.current[:,3]) and not np.any(r.voltage[:,4])
assert r.current[0,0]!=0.  # A prescribed ramp includes endpoint displacement current.
from sipi import startup_port_waves
w=startup_port_waves(r,z_ref=[35.,45.,55.,65.,75.,85.])
assert w.source_kind=='MixedBoundaryMulticonductorRLGCLadderResponse'
assert w.incident.shape==w.reflected.shape==(41,6)
```

Ports are near N followed by far N. Both terminal currents enter the line.
The unchanged formulas are `a=(V+Zref*I)/(2*sqrt(Zref))` and
`b=(V-Zref*I)/(2*sqrt(Zref))` in sqrt(W). Each port satisfies `a²-b²=V*I`.
Ideal voltage sources retain the full terminal displacement current, including
mutual endpoint C; segment current alone is not the terminal current.
Open ends have I=0 and a=b; short ends have V=0 and a=-b. Both have zero
terminal power without replacing their boundaries by finite resistors.

```python
root_z=np.sqrt(w.z_ref)
np.testing.assert_allclose(root_z*(w.incident+w.reflected),r.voltage,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose((w.incident-w.reflected)/root_z,r.current,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,:3].sum(axis=1),
    r.source_power-r.source_resistor_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,3:].sum(axis=1),
    -r.load_resistor_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power.sum(axis=1),
    r.energy_rate+r.series_loss+r.shunt_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_array_equal(w.incident[:,3],w.reflected[:,3])
np.testing.assert_array_equal(w.incident[:,4],-w.reflected[:,4])
other=startup_port_waves(r,z_ref=2*w.z_ref)
np.testing.assert_array_equal(other.port_power,w.port_power)
assert not w.incident.flags.writeable
assert max(w.voltage_reconstruction_relative_error,w.current_reconstruction_relative_error,
           w.power_balance_relative_error)<=1e-10
```

Near power excludes source resistor loss; far power is minus load resistor
loss. Summed terminal power equals internal energy rate plus R/G losses.
The relative1e-10 reconstruction/power guards, detached readonly outputs and
finite-scale rejection remain unchanged. Only one import, the documented
class list and two explicit class predicates change in the wave converter;
wave arithmetic and the physical engine are unchanged.

Tests cover twelve coupled/diagonal/lossless ramp/pulse V/I/power cases and
24 scalar-modal reconstructions across Rs0/25, load0/open/100, both signal
counts and two drives. All1512 boundary combinations check open/short wave
identities. Two one-cell ideal/short pure-L ramp solutions independently
retain mutual endpoint displacement current. PSD near-loss cases, signal
permutations, reference invariance, strict shape/type/finite guards and
no-repropagation checks also pass.

Independent synthetic six/eight-port phasors agree with scikit-rf2.2.0 Z-to-S
within1e-10 sqrt(W); this checks conversion, not propagated-line accuracy.
All108 prior full-wave outputs (27 kinds, two drives, two reference vectors)
retain exact source/installed hashes. Existing KCL and qualified spatial
convergence limits remain as documented by the underlying engine; this
addition does not establish new field, measured or arbitrary-transient accuracy.

[Saved inputs](multiconductor_boundary_startup_document.md) are supported.
Saved wave versions1–15 still reject this separate kind. The registry remains
91schemas/37templates. No new dependency, FFT/TDR, mode extraction or
browser/desktop update is added. See [startup power waves](startup_waves.md).
