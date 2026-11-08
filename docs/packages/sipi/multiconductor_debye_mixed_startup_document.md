# Saved multiconductor Debye typed-source inputs

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_debye_mixed_startup_document.md)

`MixedSourceMulticonductorDebyeReactiveLadderDocument` preserves original
[typed voltage/current sources](multiconductor_debye_mixed_startup.md) as
`sipi.multiconductor-debye-mixed-startup/1`. Reading and normalization validate
without propagating states. Physical equations and qualified accuracy limits
remain unchanged.

```python
import numpy as np
from sipi import MixedSourceMulticonductorDebyeReactiveLadderDocument
t=np.linspace(0.,4e-9,41)
drive=np.minimum(t/1e-9,1.)
sources=[dict(kind='current',current_a=(.02*drive).tolist(),shunt_conductance_s=0.),
         dict(kind='voltage',voltage_v=(-.4*drive).tolist(),series_resistance_ohm=50.),
         dict(kind='current',current_a=(.004*drive).tolist(),shunt_conductance_s=.01)]
doc=MixedSourceMulticonductorDebyeReactiveLadderDocument(
    t,sources,signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
from sipi.execution import normalize_saved,execute_saved
text=doc.dumps()
assert normalize_saved(text)==text
assert doc.to_dict()['schema']=='sipi.multiconductor-debye-mixed-startup/1'
assert len(doc.to_dict())==16 and doc.samples==41
assert doc.to_dict()['sources']==sources
```

The root has exactly16 keys: schema, time_s, sources, signals, R_ohm_per_m,
L_h_per_m, G_s_per_m, C_inf_f_per_m, length_m, cells, load_resistance_ohm,
delta_C_f_per_m, relaxation_hz, load_capacitance_f, load_branch_resistance_ohm
and load_branch_inductance_h. Duplicate/unknown keys, nonfinite JSON and
implicit source-schema migration are rejected.

Each source has exactly three keys. Voltage sources retain `kind='voltage'`,
`voltage_v` samples[V] and `series_resistance_ohm>0`. Current sources retain
`kind='current'`, `current_a` samples[A] and `shunt_conductance_s>=0`[S].
The kind must be a string. No converted equivalent current/conductance or
validator-only resistance is stored. Near-zero conductances and original
samples remain exact; zero shunt conductance means an ideal current source.
No ideal voltage/short or implicit resistance/conductance alias is accepted.

The shared input validator retains all line PSD/strength/null, SPD storage,
external C/RL, declared pole order and finite transformation rules. It does
not resample inputs, clip small ranks or propagate during parsing. Source
conversion overflow/nonzero underflow is rejected before an engine call.

```python
loaded=MixedSourceMulticonductorDebyeReactiveLadderDocument.loads(text)
r=loaded.analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['error'] is None
assert out['result']==r.to_dict() and out['input']==loaded.to_dict()
assert r.source_units==('A','V','A') and r.inputs['sources']==sources
assert 'source_currents_a' not in r.inputs and 'source_voltages_v' not in r.inputs
assert 'source_shunt_conductance_s' not in r.inputs and 'source_resistance_ohm' not in r.inputs
np.testing.assert_allclose(r.source_power-r.source_series_resistor_loss-r.source_shunt_resistor_loss,
    np.sum(r.voltage[:,:3]*r.current[:,:3],axis=1),rtol=1e-10,atol=1e-12)
assert r.to_dict(include_states=True)['states_included'] is True
assert not r.source_values.flags.writeable
```

`max_evaluations` counts actual time rows2–10000, independently of cells,
signals or poles, and is checked before exactly one physical API call. Common
execution retains input-byte and diagnostic limits. The result's exact class,
canonical typed inputs, time/source-values and every state/diagnostic array
shape are checked. The source-values columns retain their V/A units. Original
propagation/finite-scale failures remain errors; exports detach mutable inputs.

Validation compares direct, saved and common full-state execution for every
voltage/current mask across3/4 signals and ramp/pulse drives. It checks strict
root/nested keys, units, source-kind rejection, transformations, actual budgets,
source/input/array identity corruption, source series/shunt power, external
C/Rbranch zero/rank/near-zero values, SPD branch L, PSD nulls and pole order.
The previous88 schemas keep canonical normalization hashes on source and
installed artifacts; the actual new fixture retains exact registry equality
(89 schemas/37 templates at this addition).

This library schema does not change the physical engine or its failed/qualified
PWL/horizon scopes. Existing native wave conversion and saved wave versions1–14
do not admit this response/document kind. No measured accuracy, arbitrary
transient guarantee, new dependency, browser/desktop engine update or platform
integration is added. See [common execution](execution.md).
