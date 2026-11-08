# Saved multiconductor PSD Debye input

**English** | [한국어](../../locales/ko/pages/packages/sipi/psd_multiconductor_debye_startup_document.md)

`PSDMulticonductorDebyeRLGCLadderDocument` stores explicit inputs for the
[three/four-signal PSD Debye circuit](psd_multiconductor_debye_startup.md).
Its separate schema is `sipi.psd-multiconductor-debye-rlgc-startup/1`; existing
strict-strength documents retain their original admission rules.

```python
import numpy as np
from sipi import PSDMulticonductorDebyeRLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved, saved_schemas

t = np.linspace(0., 4e-9, 41)
doc = PSDMulticonductorDebyeRLGCLadderDocument(
    t, np.minimum(t/1e-9, 1.)[:, None]*[1., -.4, .2], signals=3,
    R=np.diag([20., 0., 26.]), L=np.diag([450., 480., 510.])*1e-9,
    G=np.diag([.002, .0022, 0.]), C_inf=np.diag([210., 220., 230.])*1e-12,
    delta_C=np.array([np.diag([150., 0., 0.]), np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7, 7e8], length=.1, cells=4,
    source_resistance=[25.]*3, load_resistance=[100.]*3)
text = doc.dumps()
assert normalize_saved(text) == text
assert doc.to_dict()['schema'] == 'sipi.psd-multiconductor-debye-rlgc-startup/1'
assert doc.to_dict()['schema'] in saved_schemas()
assert PSDMulticonductorDebyeRLGCLadderDocument.loads(text).dumps() == text
```

The closed object has exactly14 keys: `schema`, `time_s`, `source_voltages_v`,
`signals`, `R_ohm_per_m`, `L_h_per_m`, `G_s_per_m`, `C_inf_f_per_m`,
`length_m`, `cells`, `source_resistance_ohm`, `load_resistance_ohm`,
`delta_C_f_per_m`, `relaxation_hz`. R/G and strengths retain every supplied
PSD matrix entry, including zero directions and tiny positive values. Reading
and normalization invoke the physical validator without propagation; there is
no rank clipping, eigenvector conversion, resampling, hidden source, pole
reordering or version upgrade. Unknown/duplicate keys, nonfinite values,
wrong units/shapes, boolean/complex values and invalid physical inputs fail.

Explicit signals3/4,1–2 declared poles,cells1–64 and uniform time2–10000
starting0 are unchanged. Source drive shape is(time,signals), first row0;
source/load resistances are positive vectors. PSD sign and SPD L/C_inf
conditioning gates are those of the physical API, including conservative
rejection of a negative computed eigenvalue near singularity.

```python
loaded = PSDMulticonductorDebyeRLGCLadderDocument.loads(text)
r = loaded.analyze(max_evaluations=41)
out = execute_saved(text, max_evaluations=41)
assert out['status'] == 'complete' and out['error'] is None
assert out['input'] == doc.to_dict() and out['result'] == r.to_dict()
assert r.voltage.shape == (41, 6)
assert np.any(r.polarization_voltage[:, :, 0, 1:])
assert not np.any(r.polarization_charge[:, :, 0, 1:])
assert not np.any(r.polarization_voltage[:, :, 1])
assert r.inputs['delta_C_f_per_m'] == doc.to_dict()['delta_C_f_per_m']
assert max(r.power_balance_relative_error, r.total_power_balance_relative_error) <= 1e-10
```

`max_evaluations` is an integer actual-time-row budget2–10000, independent of
cell/signal/pole count. A budget smaller than the stored sample count fails
before the single engine call; it cannot reset cell count or truncate time.
Common execution preserves the canonical input, returns the compact physical
result and uses the same budget. Direct `analyze` exposes all readonly states;
`to_dict(include_states=True)` exports them explicitly.

The adapter checks the exact response type, input values, time, drive and
all array shapes, including polarization(time,node,pole,signal). Canonical
null auxiliary voltage can be nonzero while its polarization charge/current,
energy and loss remain zero. Exactly zero strengths retain zero columns and
pole order. Original finite-scale, propagation and power failures are passed
through without clipping or retry.

Validation includes12 coupled/diagonal/zero-RG ramp/pulse full-state replays,
rank-one losses, null-only drives, near-zero strengths0/1e-13/1e-20, one/zero/
reordered poles,44 response identity/shape corruptions, every key, strict
nested inputs, budgets and preserved failures. Existing strict documents
continue rejecting singular inputs; saved wave versions1–10 reject this new
kind. The common registry adds one explicit schema, for81 schemas and37
section templates, and its actual-document fixture retains exact set equality.
No numerical source, solver, dependency, accuracy certification, wave adapter,
application or platform support is added. See [common execution](execution.md).
