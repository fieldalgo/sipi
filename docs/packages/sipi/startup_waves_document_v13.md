# Saved multiconductor Debye series RL port waves

**English** | [한국어](../../locales/ko/pages/packages/sipi/startup_waves_document_v13.md)

Explicit `StartupPortWavesDocument(..., version=13)` adds the
[17-key multiconductor Debye reactive input](multiconductor_debye_reactive_startup_document.md)
to the existing version12 kinds. The default remains version1; versions1–12
retain their original admission and reject this new kind without upgrading it.
The schema is `sipi.startup-port-waves/13`.

```python
import numpy as np
from sipi import MulticonductorDebyeReactiveLadderDocument
from sipi.execution import normalize_saved, execute_saved, saved_schemas

t=np.linspace(0.,4e-9,41)
nested=MulticonductorDebyeReactiveLadderDocument(
    t,np.minimum(t/1e-9,1.)[:,None]*[1.,-.4,.2],signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,
    source_resistance=[25.]*3,load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
text=nested.dumps()
assert normalize_saved(text)==text
assert len(nested.to_dict())==17
assert nested.to_dict()['schema']=='sipi.multiconductor-debye-reactive-startup/1'
assert nested.to_dict()['schema'] in saved_schemas()
assert MulticonductorDebyeReactiveLadderDocument.loads(text).dumps()==text
from sipi import StartupPortWavesDocument
saved=StartupPortWavesDocument(nested,z_ref=[35.,45.,55.,65.,75.,85.],version=13)
text=saved.dumps()
assert normalize_saved(text)==text
assert saved.to_dict()['schema']=='sipi.startup-port-waves/13'
assert set(saved.to_dict())=={'schema','startup','z_ref_ohm'}
assert saved.to_dict()['startup']==nested.to_dict()
```

Root keys are exactly `schema`, `startup`, `z_ref_ohm`. Nested input must be a
supported physical document, not another wave document. Validated signals3/4
require six/eight positive real reference resistances; two/four-port kinds
retain their original shapes. References are constant diagonal values, not
inferred characteristic/modal impedances. No recursion or hidden upgrade.

Nested Cload[F]/Rbranch[ohm] remain exact-symmetric real PSD matrices, including
zero/rank-one/tiny positive entries. Lbranch[H] is SPD with ratio>1e-12.
Original line PSD loss/strength, SPD L/C_inf, pole order, cells1–64 and PWL
sample contracts remain. Parsing and normalization do not propagate or alter
matrices, pole order, drive, samples or references. Invalid nested matrices,
unknown/duplicate keys, nonfinite numbers and invalid references fail early.

```python
from sipi import startup_port_waves
physical=nested.analyze(max_evaluations=41)
w=StartupPortWavesDocument.loads(text).analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['error'] is None
assert out['input']==saved.to_dict() and out['result']==w.to_dict()
assert w.to_dict()==startup_port_waves(physical,z_ref=saved.to_dict()['z_ref_ohm']).to_dict()
np.testing.assert_allclose(w.port_power[:,3:].sum(axis=1),
    -physical.load_resistor_loss-physical.load_capacitor_power
    -physical.load_branch_energy_rate-physical.load_branch_resistor_loss,
    rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power.sum(axis=1),
    physical.line_energy_rate+physical.series_loss+physical.shunt_loss+physical.relaxation_loss,
    rtol=1e-10,atol=1e-12)
assert not w.incident.flags.writeable
```

For this circuit, `max_evaluations` counts actual time rows2–10000; its limit
is independent of cell/signal/pole count. A short budget fails before the
single engine call and single wave conversion. The existing lossless-delay
budget retains its original meaning. Exact wave identity checks retain time,
terminal V/I, reference values, port names, source kind and all wave shapes.

Terminal current enters the line at both ends. Near power excludes source
resistor loss. Far power includes parallel resistor loss, capacitor power,
branch-inductor energy rate and branch resistor loss with a negative sign.
The total terminal balance uses internal line energy, not total external C/L
storage. Original finite-scale/propagation/power failures pass through unchanged.

Validation replays23 source variants with two drives and296 pre-edit
canonical/full-wave hashes across versions1–12. It checks first supported
versions/default1,20 corrupted wave identities, no parse propagation,
one engine/one conversion, exact budgets, C/Rbranch zero/rank-one/near values,
branch L SPD, PSD null directions, declared poles, and original failures.
The original12 registries and five unaffected methods retain exact syntax
trees. The common registry adds the actual v13 fixture while retaining exact
set equality (86 schemas/37 templates at this addition).

No numerical solver or conversion formula changes. The physical engine's
original8-cycle settling failure and qualified longer-horizon scope remain;
serialization adds no accuracy certification, arbitrary-horizon guarantee,
FFT/TDR, runtime dependency, application or platform integration.
See [terminal waves](multiconductor_debye_reactive_startup_waves.md) and
[common execution](execution.md).
