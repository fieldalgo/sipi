# Saved multiconductor mixed-boundary port waves

**English** | [한국어](../../locales/ko/pages/packages/sipi/startup_waves_document_v16.md)

Explicit `StartupPortWavesDocument(..., version=16)` adds the
[12-key mixed-boundary input](multiconductor_boundary_startup_document.md)
to version15 kinds. Default1 and versions1–15 keep their original admission;
they reject this new kind without upgrading it. The schema is
`sipi.startup-port-waves/16`.

```python
import numpy as np
from sipi import MixedBoundaryMulticonductorRLGCLadderDocument
t=np.linspace(0.,4e-9,41)
drive=np.minimum(t[:,None]/1e-9,1.)*np.array([1.,-.4,.2])
nested=MixedBoundaryMulticonductorRLGCLadderDocument(t,drive,signals=3,
    R=np.array([[20.,-20.,0.],[-20.,20.,0.],[0.,0.,0.]]),
    L=np.array([[450.,60.,0.],[60.,480.,60.],[0.,60.,510.]])*1e-9,
    G=np.array([[0.,0.,0.],[0.,.002,.002],[0.,.002,.002]]),
    C=np.array([[210.,-20.,0.],[-20.,220.,-20.],[0.,-20.,230.]])*1e-12,
    length=.1,cells=8,source_resistance=[0.,25.,0.],
    load_resistance=[None,0.,75.])
from sipi.execution import normalize_saved,execute_saved
text=nested.dumps()
assert normalize_saved(text)==text
assert nested.to_dict()['schema']=='sipi.multiconductor-boundary-startup/1'
assert len(nested.to_dict())==12 and nested.samples==41
assert nested.to_dict()['source_resistance_ohm']==[0.,25.,0.]
assert nested.to_dict()['load_resistance_ohm']==[None,0.,75.]
from sipi import StartupPortWavesDocument
saved=StartupPortWavesDocument(nested,z_ref=[35.,45.,55.,65.,75.,85.],version=16)
text=saved.dumps()
assert normalize_saved(text)==text
assert saved.to_dict()['schema']=='sipi.startup-port-waves/16'
assert set(saved.to_dict())=={'schema','startup','z_ref_ohm'}
assert saved.to_dict()['startup']==nested.to_dict()
```

Root keys are exactly `schema`, `startup`, `z_ref_ohm`. Nested input must be a
supported physical document; recursive wave documents are rejected. Explicit
signals3/4 require six/eight positive real reference resistances. Existing
two/four-port kinds keep their shapes. References are constant diagonal values;
no characteristic/modal impedance is inferred.

The nested12 keys preserve original voltage samples, Rs>=0 with0=ideal,
and load null=open/0=short/positive=resistor. PSD R/G nulls and conditioned
SPD L/C retain the engine contract. No unit inference, scalar broadcast or
small-resistor substitution is introduced. Parsing and normalization do not
propagate; unknown/duplicate keys, nonfinite values and invalid references
fail before the engine.

```python
from sipi import startup_port_waves
physical=nested.analyze(max_evaluations=41)
w=StartupPortWavesDocument.loads(text).analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['error'] is None
assert out['input']==saved.to_dict() and out['result']==w.to_dict()
assert w.to_dict()==startup_port_waves(physical,z_ref=saved.to_dict()['z_ref_ohm']).to_dict()
assert out['input']['startup']['source_resistance_ohm']==[0.,25.,0.]
assert out['input']['startup']['load_resistance_ohm']==[None,0.,75.]
np.testing.assert_allclose(w.port_power[:,:3].sum(axis=1),
    physical.source_power-physical.source_resistor_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,3:].sum(axis=1),
    -physical.load_resistor_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power.sum(axis=1),
    physical.energy_rate+physical.series_loss+physical.shunt_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_array_equal(w.incident[:,3],w.reflected[:,3])
np.testing.assert_array_equal(w.incident[:,4],-w.reflected[:,4])
assert not w.incident.flags.writeable
```

Near power excludes source resistor loss; far power is minus load resistor
loss. Ideal-source terminal current retains full mutual endpoint C displacement;
open/short currents are not replaced by segment currents or resistor aliases.
Open waves satisfy a=b, short waves a=-b, both with zero port power. Summed
terminal power equals internal energy rate plus R/G loss. Physical and wave
finite-scale, propagation and reconstruction failures pass through unchanged.

`max_evaluations` counts actual time rows2–10000 independently of cells and
signals. Budget rejection occurs before one engine call and one conversion;
the old lossless delay budget keeps its meaning. Identity checks retain times,
V/I, reference values, port names, source kind and all wave array shapes.

Checks replay29 kinds with two drives and446 prior canonical/full-wave hashes
across versions1–15. They include24 uniform boundary combinations/drives,
all1512 boundary masks normalized without propagation,20 wave identity
corruptions, strict boundary vectors/units/keys, actual budgets, engine/wave
call counts, PSD null/near losses and original failures. All15 old registries
and five unaffected methods retain exact syntax trees. An actual version16
fixture retains exact registry equality:92schemas/37templates at this addition.

Numerical equations and wave formulas are unchanged. Independent KCL and
qualified spatial/sampling limits remain as documented by the physical engine.
Saving does not establish new field/measured or arbitrary-transient accuracy,
FFT/TDR or platform support. See [native waves](multiconductor_boundary_startup_waves.md)
and [common execution](execution.md).
