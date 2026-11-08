# Saved multiconductor Debye typed-source port waves

**English** | [한국어](../../locales/ko/pages/packages/sipi/startup_waves_document_v15.md)

Explicit `StartupPortWavesDocument(..., version=15)` adds the
[16-key typed-source input](multiconductor_debye_mixed_startup_document.md)
to version14 kinds. Default1 and versions1–14 retain their original admission;
they reject this new kind without upgrading it. The schema is
`sipi.startup-port-waves/15`.

```python
import numpy as np
from sipi import MixedSourceMulticonductorDebyeReactiveLadderDocument
t=np.linspace(0.,4e-9,41)
drive=np.minimum(t/1e-9,1.)
sources=[dict(kind='current',current_a=(.02*drive).tolist(),shunt_conductance_s=0.),
         dict(kind='voltage',voltage_v=(-.4*drive).tolist(),series_resistance_ohm=50.),
         dict(kind='current',current_a=(.004*drive).tolist(),shunt_conductance_s=.01)]
nested=MixedSourceMulticonductorDebyeReactiveLadderDocument(
    t,sources,signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
from sipi.execution import normalize_saved,execute_saved
text=nested.dumps()
assert normalize_saved(text)==text
assert nested.to_dict()['schema']=='sipi.multiconductor-debye-mixed-startup/1'
assert len(nested.to_dict())==16 and nested.samples==41
assert nested.to_dict()['sources']==sources
from sipi import StartupPortWavesDocument
saved=StartupPortWavesDocument(nested,z_ref=[35.,45.,55.,65.,75.,85.],version=15)
text=saved.dumps()
assert normalize_saved(text)==text
assert saved.to_dict()['schema']=='sipi.startup-port-waves/15'
assert set(saved.to_dict())=={'schema','startup','z_ref_ohm'}
assert saved.to_dict()['startup']==nested.to_dict()
```

Root keys are exactly `schema`, `startup`, `z_ref_ohm`. Nested input must be a
supported physical document; recursive wave documents are rejected. Explicit
signals3/4 require six/eight positive real reference resistances. Old two/four
port kinds keep their shapes. References are constant diagonal values, with
no inferred characteristic/modal impedance.

Each nested source retains its original three keys: voltage kind, V samples
and positive series resistance, or current kind, A samples and nonnegative
shunt conductance. No equivalent injected current/conductance or temporary
validator resistance is stored. Zero current shunt remains ideal current;
ideal voltage, short, unit inference and resistance aliases remain unsupported.
Line PSD loss/strength and nulls, SPD L/C_inf, external C/Rbranch PSD and branch
L SPD rules are unchanged. Reading/normalization never propagates states.
Unknown/duplicate keys, nonfinite values and invalid references fail early.

```python
from sipi import startup_port_waves
physical=nested.analyze(max_evaluations=41)
w=StartupPortWavesDocument.loads(text).analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['error'] is None
assert out['input']==saved.to_dict() and out['result']==w.to_dict()
assert w.to_dict()==startup_port_waves(physical,z_ref=saved.to_dict()['z_ref_ohm']).to_dict()
assert out['input']['startup']['sources']==sources
for j,source in enumerate(sources):
    expected=(np.asarray(source['voltage_v'])-w.voltage[:,j])/source['series_resistance_ohm'] if source['kind']=='voltage' else np.asarray(source['current_a'])-source['shunt_conductance_s']*w.voltage[:,j]
    np.testing.assert_allclose(w.current[:,j],expected,rtol=1e-13,atol=1e-15)
np.testing.assert_allclose(w.port_power[:,:3].sum(axis=1),
    physical.source_power-physical.source_series_resistor_loss-physical.source_shunt_resistor_loss,
    rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,3:].sum(axis=1),
    -physical.load_resistor_loss-physical.load_capacitor_power
    -physical.load_branch_energy_rate-physical.load_branch_resistor_loss,
    rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power.sum(axis=1),
    physical.line_energy_rate+physical.series_loss+physical.shunt_loss+physical.relaxation_loss,
    rtol=1e-10,atol=1e-12)
assert not w.incident.flags.writeable
```

Near terminal current is `(Vs-Vnear)/Rs` or `Iinj-Gs*Vnear`, according to each
source kind. Mixed V/A samples cannot replace terminal current. Near power
excludes both voltage-source series loss and current-source shunt loss. Far
power retains resistor, capacitor, branch L and branch R partitions; summed
terminal power uses internal line energy, distinct from external storage.
Original finite-scale, propagation and power failures pass through unchanged.

`max_evaluations` counts actual time rows2–10000, independently of cells,
signals and poles. Budget rejection occurs before one engine call and one
wave conversion. The old lossless delay budget keeps its meaning. Identity
checks preserve times, V/I, reference values, port names, source kind and all
wave array shapes.

Checks replay27 kinds with two drives, all24 typed masks with two drives,
and392 prior canonical/full-wave hashes across versions1–14. They cover
20 wave identity corruptions, source units/keys/conversion limits, actual
budgets, parsing without propagation, one engine/wave call, external C/Rbranch
zero/rank/near values, branch L SPD, PSD nulls/poles and original failures.
All14 old registries and five unaffected methods retain exact syntax trees.
An actual version15 fixture preserves exact registry equality:90 schemas and
37 templates at this addition.

The numerical engine and wave formulas are unchanged. Failed low-loss PWL/
short-horizon cases and qualified damped continuum limits remain separate.
Saving does not establish arbitrary transient accuracy, FFT/TDR or new platform
support. See [native waves](multiconductor_debye_mixed_startup_waves.md) and
[common execution](execution.md).
