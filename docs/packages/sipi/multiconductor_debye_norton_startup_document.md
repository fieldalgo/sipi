# Saved multiconductor Debye current-source inputs

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_debye_norton_startup_document.md)

`NortonMulticonductorDebyeReactiveLadderDocument` preserves the explicit
[current-source circuit](multiconductor_debye_norton_startup.md) as
`sipi.multiconductor-debye-norton-startup/1`. Parsing and normalization validate
inputs without propagating states. The physical engine and its qualified
accuracy limits are unchanged.

```python
import numpy as np
from sipi import NortonMulticonductorDebyeReactiveLadderDocument
from sipi.execution import normalize_saved,execute_saved
t=np.linspace(0.,4e-9,41)
doc=NortonMulticonductorDebyeReactiveLadderDocument(
    t,.02*np.minimum(t/1e-9,1.)[:,None]*[1.,-.4,.2],signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,
    source_shunt_conductance=[0.,.02,0.],load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
text=doc.dumps()
assert normalize_saved(text)==text
assert doc.to_dict()['schema']=='sipi.multiconductor-debye-norton-startup/1'
assert len(doc.to_dict())==17 and doc.samples==41
```

The root has exactly17 keys: schema, signals, time_s, source_currents_a,
R_ohm_per_m, L_h_per_m, G_s_per_m, C_inf_f_per_m, length_m, cells,
source_shunt_conductance_s, load_resistance_ohm, delta_C_f_per_m,
relaxation_hz, load_capacitance_f, load_branch_resistance_ohm and
load_branch_inductance_h. Duplicate/unknown keys, nonfinite JSON and implicit
unit conversion are rejected. There is no voltage-source schema migration or
source-voltage/resistance alias. The physical validator's temporary resistance
is omitted from storage; the explicit conductance vector is stored instead.

Injected current is in A, shape(time,N), initially zero. Source conductance
is an N-vector in S with finite nonnegative entries; zero is an ideal current
source. All original line, PSD strength/loss, SPD storage and external C/RL
matrix rules apply, including conservative PSD eigensign rejection, declared
pole order/zero columns and no rank clipping. Stored samples and small positive
conductances are preserved without resampling or conversion to Thevenin inputs.

```python
loaded=NortonMulticonductorDebyeReactiveLadderDocument.loads(text)
r=loaded.analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['result']==r.to_dict()
assert out['input']==loaded.to_dict()
assert r.inputs['source_shunt_conductance_s']==[0.,.02,0.]
assert 'source_resistance_ohm' not in r.inputs
assert 'source_voltages_v' not in r.inputs
np.testing.assert_array_equal(r.source_currents,r.inputs['source_currents_a'])
np.testing.assert_array_equal(r.total_energy,
    r.line_energy+r.load_capacitor_energy+r.load_branch_energy)
assert r.to_dict(include_states=True)['states_included'] is True
```

`max_evaluations` counts actual time rows and must be an integer2–10000. It is
checked before one physical API call, independently of signal/cell counts.
Common execution retains its input-byte and diagnostics checks. Returned class,
canonical inputs, exact times/currents and every state/diagnostic array shape
are checked. Original propagation and finite-scale failures remain errors.
`to_dict()` and `dumps()` detach inputs; analyzed arrays are readonly.

Direct, saved and common execution compare full states for ideal/mixed/positive
source conductances and ramp/pulse drives. Tests retain PSD null/near-rank and
pole behavior, zero/rank-one/near-zero external C/Rbranch, SPD Lbranch and
separate source/parallel-load/branch power. Input-identity corruption, budgets,
strict JSON and source alias rejection are checked. Existing saved namespaces
remain unchanged; terminal-wave document versions1–13 do not admit this kind.

This adds a library schema and common execution path. It does not update a
browser/desktop engine, add a new physical accuracy claim, infer a mixed source
or ideal voltage short, or expand the qualified continuum/horizon conditions.
