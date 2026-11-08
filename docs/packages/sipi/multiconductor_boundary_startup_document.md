# Saved multiconductor mixed-boundary inputs

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_boundary_startup_document.md)

`MixedBoundaryMulticonductorRLGCLadderDocument` preserves the separate
[constant mixed-boundary circuit](multiconductor_boundary_startup.md) as
`sipi.multiconductor-boundary-startup/1`. Parsing and normalization validate
without propagating states. The previous positive-resistance schema is not
upgraded or reinterpreted.

```python
import numpy as np
from sipi import MixedBoundaryMulticonductorRLGCLadderDocument
t=np.linspace(0.,4e-9,41)
drive=np.minimum(t[:,None]/1e-9,1.)*np.array([1.,-.4,.2])
doc=MixedBoundaryMulticonductorRLGCLadderDocument(t,drive,signals=3,
    R=np.array([[20.,-20.,0.],[-20.,20.,0.],[0.,0.,0.]]),
    L=np.array([[450.,60.,0.],[60.,480.,60.],[0.,60.,510.]])*1e-9,
    G=np.array([[0.,0.,0.],[0.,.002,.002],[0.,.002,.002]]),
    C=np.array([[210.,-20.,0.],[-20.,220.,-20.],[0.,-20.,230.]])*1e-12,
    length=.1,cells=8,source_resistance=[0.,25.,0.],
    load_resistance=[None,0.,75.])
from sipi.execution import normalize_saved,execute_saved
text=doc.dumps()
assert normalize_saved(text)==text
assert doc.to_dict()['schema']=='sipi.multiconductor-boundary-startup/1'
assert len(doc.to_dict())==12 and doc.samples==41
assert doc.to_dict()['source_resistance_ohm']==[0.,25.,0.]
assert doc.to_dict()['load_resistance_ohm']==[None,0.,75.]
```

The12root keys are schema,time_s,source_voltages_v,signals,R_ohm_per_m,L_h_per_m,
G_s_per_m,C_f_per_m,length_m,cells,source_resistance_ohm,load_resistance_ohm.
Sources preserve finite Rs>=0 (0ideal voltage); each load preserves null=open,
0=short,or finitepositive resistance. No scalar broadcast, source-null alias,
unit inference or small-resistor substitution is allowed. PSD R/G nulls and
conditioned SPD L/C retain the engine contract, as do signals3/4,cells1–128
and uniform first-row-zero PWL samples2–10000. Duplicate/unknown keys,
nonfinite JSON and invalid physical inputs are rejected before propagation.

```python
loaded=MixedBoundaryMulticonductorRLGCLadderDocument.loads(text)
r=loaded.analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['error'] is None
assert out['input']==doc.to_dict() and out['result']==r.to_dict()
assert r.node_voltage.shape==(41,9,3) and r.current.shape==(41,6)
np.testing.assert_array_equal(r.voltage[:,[0,2]],drive[:,[0,2]])
assert not np.any(r.current[:,3]) and not np.any(r.voltage[:,4])
np.testing.assert_allclose(r.energy_rate,r.line_power-r.series_loss-r.shunt_loss,
    rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(r.source_power,r.line_power+r.source_resistor_loss+r.load_resistor_loss,
    rtol=1e-10,atol=1e-12)
assert max(r.power_balance_relative_error,r.total_power_balance_relative_error)<=1e-10
assert not r.current.flags.writeable
```

`max_evaluations` counts actual time rows, independently of cells or signals.
A smaller budget fails before one engine call. Exact result class, original
inputs, times, source voltages and every state/diagnostic array shape are
checked. Source Rs0 and load null/0/positive cannot be silently replaced.
Runtime finite-scale, propagation and power failures pass through unchanged.

Validation covers all1512 boundary combinations without propagation; six
uniform end combinations across both signal counts and two drives; mixed/
diagonal/lossless full-state replay; source/load identity corruption; strict
keys/units/budgets; and singular/near-zero PSD losses. Previous90 canonical
schemas retain exact source/installed hashes. The actual new fixture keeps
exact registry equality:91schemas/37templates at this addition.

The numerical model and its independent KCL/analytical/qualified spatial
limits are unchanged. Explicit terminal-wave conversion is supported; saved wave versions1–15
still reject this separate kind. No field/measured accuracy, arbitrary
transient guarantee, new dependency or app/platform update is added.
See [common execution](execution.md).


[Explicit mixed-boundary port waves](multiconductor_boundary_startup_waves.md) preserve ideal/open/short terminal current and power.
