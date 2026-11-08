# Saved multiconductor Debye current-source port waves

**English** | [한국어](../../locales/ko/pages/packages/sipi/startup_waves_document_v14.md)

Explicit `StartupPortWavesDocument(..., version=14)` adds the
[17-key multiconductor Debye current-source input](multiconductor_debye_norton_startup_document.md)
to the existing version13 kinds. The default remains version1; versions1–13
retain their original admission and reject this new kind without upgrading it.
The schema is `sipi.startup-port-waves/14`.

```python
import numpy as np
from sipi import NortonMulticonductorDebyeReactiveLadderDocument
from sipi.execution import normalize_saved,execute_saved
t=np.linspace(0.,4e-9,41)
nested=NortonMulticonductorDebyeReactiveLadderDocument(
    t,.02*np.minimum(t/1e-9,1.)[:,None]*[1.,-.4,.2],signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,
    source_shunt_conductance=[0.,.02,0.],load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
text=nested.dumps()
assert normalize_saved(text)==text
assert nested.to_dict()['schema']=='sipi.multiconductor-debye-norton-startup/1'
assert len(nested.to_dict())==17 and nested.samples==41
from sipi import StartupPortWavesDocument
saved=StartupPortWavesDocument(nested,z_ref=[35.,45.,55.,65.,75.,85.],version=14)
text=saved.dumps()
assert normalize_saved(text)==text
assert saved.to_dict()['schema']=='sipi.startup-port-waves/14'
assert set(saved.to_dict())=={'schema','startup','z_ref_ohm'}
assert saved.to_dict()['startup']==nested.to_dict()
```

The root keys are exactly `schema`, `startup`, `z_ref_ohm`. Nested input must
be a supported physical document, not another wave document. Explicit signals3/4
require six/eight positive real reference resistances; old two/four-port kinds
retain their original shapes. References are constant diagonal values, not
inferred characteristic/modal impedances. No recursion or hidden upgrade.

The nested input stores injected current in `source_currents_a` and finite
nonnegative source shunts in `source_shunt_conductance_s`. Zero conductance
means an ideal current source. Values, declared poles, null directions and
samples are preserved; there is no voltage/resistance alias or Thevenin
conversion. Original line PSD loss/strength, SPD L/C_inf, external C/Rbranch
PSD and branch L SPD rules remain. Reading/normalization does not propagate.
Unknown/duplicate keys, nonfinite numbers and invalid references fail early.

```python
from sipi import startup_port_waves
physical=nested.analyze(max_evaluations=41)
w=StartupPortWavesDocument.loads(text).analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['error'] is None
assert out['input']==saved.to_dict() and out['result']==w.to_dict()
assert w.to_dict()==startup_port_waves(physical,z_ref=saved.to_dict()['z_ref_ohm']).to_dict()
np.testing.assert_allclose(w.current[:,:3],physical.source_currents
    -physical.voltage[:,:3]*np.asarray(nested.to_dict()['source_shunt_conductance_s']),
    rtol=1e-13,atol=1e-15)
np.testing.assert_allclose(w.port_power[:,:3].sum(axis=1),
    physical.source_power-physical.source_shunt_resistor_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,3:].sum(axis=1),
    -physical.load_resistor_loss-physical.load_capacitor_power
    -physical.load_branch_energy_rate-physical.load_branch_resistor_loss,
    rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power.sum(axis=1),
    physical.line_energy_rate+physical.series_loss+physical.shunt_loss+physical.relaxation_loss,
    rtol=1e-10,atol=1e-12)
assert not w.incident.flags.writeable
```

Near terminal current is injected current minus Gs*Vnear. Near terminal power
excludes the source shunt loss. Far power is the negative sum of parallel
resistor loss, capacitor power, branch-inductor energy rate and branch resistor
loss. The total terminal balance uses internal line energy, distinct from
external C/L storage. Original finite-scale, propagation and power failures
pass through unchanged.

For this circuit `max_evaluations` counts actual time rows2–10000 independently
of cell/signal/pole counts. An insufficient budget fails before the single
engine call and single wave conversion. The old lossless-delay budget keeps
its original meaning. Exact output identity checks retain time, terminal V/I,
references, port names, source kind and every wave shape.

Validation replays25 source variants with two drives and342 pre-edit canonical/
full-wave hashes across versions1–13. It checks first supported versions,
default1,20 corrupted wave identities, no parse propagation, exact budgets,
source Gs ideal/mixed/positive/near-zero limits, external C/Rbranch zero/rank-one/
near-zero entries, branch L SPD, PSD null directions, poles and original errors.
The original13 registries and five unaffected methods retain exact syntax trees.
The common registry includes an actual v14 fixture and exact set equality
(88 schemas/37 templates at this addition).

No solver or wave formula changes. The physical engine's failed low-loss PWL/
short-horizon cases and qualified damped continuum scope remain. Serialization
adds no arbitrary transient accuracy claim, FFT/TDR, runtime dependency or
application/platform integration. See [terminal waves](multiconductor_debye_norton_startup_waves.md)
and [common execution](execution.md).
