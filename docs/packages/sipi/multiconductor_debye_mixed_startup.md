# Multiconductor Debye circuits with typed voltage/current sources

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_debye_mixed_startup.md)

`psd_multiconductor_debye_mixed_reactive_ladder_response` supports explicit
voltage/current source mixtures for three/four signals, PSD Debye polarization
and external capacitor/series RL loads. It returns a separate
`MixedSourceMulticonductorDebyeReactiveLadderResponse`. The unchanged
[current-source circuit](multiconductor_debye_norton_startup.md) propagates
once; this boundary adapter preserves each source's original values and units.

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
```

`sources` is a list/tuple with exactly `signals` objects, each having exactly
three keys. The kind must be a string; NumPy arrays are rejected before propagation.
A voltage object uses `kind='voltage'`, `voltage_v` (one V value per
time row) and finite `series_resistance_ohm>0`. A current object uses
`kind='current'`, `current_a` (A) and finite `shunt_conductance_s>=0` (S).
Zero conductance is an ideal current source. There is no resistance alias for
current shunts, scalar waveform broadcast, implicit unit inference, ideal
voltage source, Dirichlet near end or short circuit in this API.

All columns share uniform2–10000 time rows starting0 and initially zero values.
Finite positive1/Rs and Vs/Rs map voltage boundaries to the existing Norton
circuit. Nonfinite conversions or a nonzero voltage lost to zero current through
underflow fail before propagation. The original typed sources, not equivalent
current aliases, are exported. `source_values` columns use `source_units`.

```python
near_v=r.voltage[:,:3];near_i=r.current[:,:3]
np.testing.assert_allclose(near_i[:,0],r.source_values[:,0],rtol=1e-13,atol=1e-15)
np.testing.assert_allclose(near_i[:,1],(r.source_values[:,1]-near_v[:,1])/50.,rtol=1e-13,atol=1e-15)
np.testing.assert_allclose(near_i[:,2],r.source_values[:,2]-.01*near_v[:,2],rtol=1e-13,atol=1e-15)
np.testing.assert_allclose(r.source_series_resistor_loss,50.*near_i[:,1]**2,rtol=1e-13,atol=1e-15)
np.testing.assert_allclose(r.source_shunt_resistor_loss,.01*near_v[:,2]**2,rtol=1e-13,atol=1e-15)
np.testing.assert_allclose(r.source_power-r.source_series_resistor_loss-r.source_shunt_resistor_loss,
    np.sum(near_v*near_i,axis=1),rtol=1e-10,atol=1e-12)
np.testing.assert_array_equal(r.total_energy,r.line_energy+r.load_capacitor_energy+r.load_branch_energy)
assert max(r.power_balance_relative_error,r.total_power_balance_relative_error)<=1e-10
assert 'source_currents_a' not in r.inputs and 'source_voltages_v' not in r.inputs
out=r.to_dict(include_states=True)
assert out['source_units']==['A','V','A'] and not r.source_values.flags.writeable
```

Voltage-source power is Vs*Iterminal; current-source power is Iinjected*Vnear.
Series resistor loss is summed only over voltage sources, shunt resistor loss
only over current sources. Both terminal currents enter the line. Near terminal
power excludes both source losses. Far power retains separate parallel R,
capacitor and series RL terms. Internal `line_energy` includes instantaneous
and polarization storage; `total_energy` also includes external C/L. The original
line balance and the typed-source total balance must remain within relative1e-10.
Nonfinite diagnostics and negative passive losses fail; no clipping is applied.

Original matrix and resource rules remain: signals3/4, cells1–64,1–2 positive
relaxation frequencies in Hz, exactly symmetric real PSD R/G/DeltaC/Cload/Rbranch,
and SPD L/C_inf/Lbranch with eigenvalue ratio>1e-12. Conservative computed PSD
sign rejection is retained. Original arrays, pole order, null directions and
finite-scale failures are preserved. Counts bound resources, not accuracy.

Validation covers all24 voltage/current masks across3/4 signals, homogeneous
Thevenin/Norton full-state reductions and four zero-strength constant two-signal
mixed-circuit block limits. An independent noncommuting charge/branch KCL system
is integrated by SciPy DOP853 with input-knot splitting; gates are1e-8V and1e-9A.
Strict type/key/units/finite conversion, propagation failure, readonly/copy,
linearity, time/impedance scaling, conductor permutation and pole-order checks
are included. Existing128 full-state exports retain exact source/installed hashes.

The separate spectral qualification uses uniformGs=.02S, alternating typed
sources and a damped modal fixture (R/G ten times the original low-loss fixture).
At100MHz the16/18/19-cycle horizons use512 samples/cycle; at500MHz the64/72/76-cycle
horizons use128. Final four-cycle phasor changes must be<=1e-8V. Input refinement
128/256/512 must decrease error. Cells16/32/64 must strictly decrease the same-PWL
continuum error and finish<=1e-3V. scikit-rf2.2.0 continuum ABCD sums periodic-PWL
aliases8192/16384/32768; reference and constant-transfer coefficient gates are1e-8.
Independent finite-pi KCL aliases32/64/128 also agree with each time result within
1e-8V. This qualifies those explicit fixtures, not arbitrary bandwidth or horizon.
Prior low-loss PWL/short-horizon failures remain outside the accepted scope.

No field extraction, arbitrary dispersion/initial energy, measured accuracy,
automatic time selection, new dependency, saved/wave admission or application/
platform integration is added. The library registry remains88 schemas/37 templates.
The earlier [two-signal constant mixed API](mixed_startup.md) has a separate boundary
contract; its ideal voltage/short options are not inferred here.
