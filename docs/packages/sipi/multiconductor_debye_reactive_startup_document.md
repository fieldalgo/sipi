# Saved multiconductor Debye series RL input

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_debye_reactive_startup_document.md)

`MulticonductorDebyeReactiveLadderDocument` stores the explicit
[three/four-signal Debye circuit with external C and series RL](multiconductor_debye_reactive_startup.md).
Its separate schema is `sipi.multiconductor-debye-reactive-startup/1`.
Existing capacitive documents reject the new branch fields.

```python
import numpy as np
from sipi import MulticonductorDebyeReactiveLadderDocument
from sipi.execution import normalize_saved, execute_saved, saved_schemas

t=np.linspace(0.,4e-9,41)
doc=MulticonductorDebyeReactiveLadderDocument(
    t,np.minimum(t/1e-9,1.)[:,None]*[1.,-.4,.2],signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,
    source_resistance=[25.]*3,load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
text=doc.dumps()
assert normalize_saved(text)==text
assert len(doc.to_dict())==17
assert doc.to_dict()['schema']=='sipi.multiconductor-debye-reactive-startup/1'
assert doc.to_dict()['schema'] in saved_schemas()
assert MulticonductorDebyeReactiveLadderDocument.loads(text).dumps()==text
```

The closed object has exactly 17 keys:
`schema`, `time_s`, `source_voltages_v`, `signals`, `R_ohm_per_m`,
`L_h_per_m`, `G_s_per_m`, `C_inf_f_per_m`, `length_m`, `cells`,
`source_resistance_ohm`, `load_resistance_ohm`, `delta_C_f_per_m`,
`relaxation_hz`, `load_capacitance_f`, `load_branch_resistance_ohm`,
`load_branch_inductance_h`.

External capacitance uses F, branch resistance ohm, and branch inductance H.
Every external matrix is real and exactly symmetric N×N. Cload and Rbranch
are PSD, including zero/rank-one/tiny positive values. Lbranch is SPD with
normalized eigenvalue ratio above 1e-12. Parsing and normalization reuse the
physical validator without propagation. No units, missing branch, symmetry
repair, rank threshold, pole reordering, resampling or version upgrade is inferred.
Unknown/duplicate keys, nonfinite numbers and invalid inputs are rejected.

Original contracts retain signals 3/4, cells 1–64, 1–2 declared poles and
uniform time 2–10000 starting at zero. Drive has shape (time,N) with first
row zero; source/load resistances are positive vectors. Line R/G/strengths
remain PSD and L/C_inf SPD. Negative computed PSD eigenvalues are rejected
conservatively, including near-singular sign ambiguity.

```python
r=MulticonductorDebyeReactiveLadderDocument.loads(text).analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['error'] is None
assert out['input']==doc.to_dict() and out['result']==r.to_dict()
assert r.voltage.shape==(41,6) and r.load_branch_current.shape==(41,3)
np.testing.assert_array_equal(r.total_energy,
    r.line_energy+r.load_capacitor_energy+r.load_branch_energy)
np.testing.assert_allclose(r.current[:,3:],
    -r.voltage[:,3:]/100-r.load_capacitor_current-r.load_branch_current,
    rtol=1e-10,atol=1e-12)
for key in ['load_capacitance_f','load_branch_resistance_ohm','load_branch_inductance_h']:
    assert r.inputs[key]==doc.to_dict()[key]
assert not np.any(r.polarization_charge[:,:,0,1:])
assert not np.any(r.polarization_voltage[:,:,1])
assert max(r.power_balance_relative_error,r.total_power_balance_relative_error)<=1e-10
```

`max_evaluations` counts actual time rows, independently of cell/signal/pole
count. An integer budget 2–10000 smaller than stored samples fails before
one engine call; it does not truncate time or reduce cells. Common execution
preserves canonical input and returns the compact result. Direct `analyze`
returns readonly states, explicitly exported by `to_dict(include_states=True)`.

The adapter checks exact response class, inputs, time, drive and every array
shape. External branch and capacitor currents are (time,N); energy/rate/loss
are (time,). Line energy includes internal instantaneous and polarization
storage; total energy adds external C and branch L. Parallel resistor loss
and branch resistor loss remain distinct. Far current includes all three
load paths. Declared zero poles retain zero columns and order; canonical
null-direction auxiliary voltage can be nonzero with zero polarization energy.
Original finite-scale, propagation and power failures pass through unchanged.

Checks include 12 coupled/diagonal/zero-RG ramp/pulse full-state replays;
zero/rank-one/near-zero C/Rbranch; SPD Lbranch boundaries; PSD line loss,
null-only excitation, near-zero and reordered strengths; 58 response identity/
shape corruptions; external matrix identity, copies, exact keys and budgets.
Saved wave versions 1–12 still reject this kind. The common registry adds
one explicit schema (85 schemas and 37 section templates at this addition),
with the existing exact-set assertion and an actual new-document fixture.
No numerical engine changes or new accuracy evidence are introduced. The
physical API's original 8-cycle settling failure and separate longer-horizon
qualification remain as documented; serialization does not expand that scope.
No new dependency, wave adapter, application or platform support is inferred.
See [common execution](execution.md).
