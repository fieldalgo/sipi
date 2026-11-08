# Saved multiconductor PSD Debye port waves

**English** | [한국어](../../locales/ko/pages/packages/sipi/startup_waves_document_v11.md)

Explicit `StartupPortWavesDocument(..., version=11)` adds
`sipi.psd-multiconductor-debye-rlgc-startup/1` to the supported nested startup
kinds. The root keeps exactly `schema`, `startup`, and `z_ref_ohm`.
Default version1 and every version1–10 retain their existing admissions and
canonical outputs; they reject this new nested kind without upgrading it.

```python
import numpy as np
from sipi import PSDMulticonductorDebyeRLGCLadderDocument, StartupPortWavesDocument
from sipi.execution import execute_saved, normalize_saved

t = np.linspace(0., 4e-9, 41)
startup = PSDMulticonductorDebyeRLGCLadderDocument(
    t, np.minimum(t/1e-9, 1.)[:, None]*[1., -.4, .2], signals=3,
    R=np.diag([20., 0., 26.]), L=np.diag([450., 480., 510.])*1e-9,
    G=np.diag([.002, .0022, 0.]), C_inf=np.diag([210., 220., 230.])*1e-12,
    delta_C=np.array([np.diag([130., 0., 0.]), np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7, 7e8], length=.1, cells=4,
    source_resistance=[25.]*3, load_resistance=[100.]*3)
request = StartupPortWavesDocument(
    startup, z_ref=[35., 45., 55., 65., 75., 85.], version=11)
text = request.dumps()
assert normalize_saved(text) == text
assert request.to_dict()['schema'] == 'sipi.startup-port-waves/11'
assert request.to_dict()['startup'] == startup.to_dict()
```

The explicit nested `signals` value is3 or4, requiring six or eight positive
finite real references. Port order is near N then far N, with both currents
entering the line. Scalar references, complex references, guessed port counts,
recursive wave documents, duplicate/unknown keys and nonfinite values are
rejected. The [saved physical circuit](psd_multiconductor_debye_startup_document.md)
retains its14-key contract,1–2 declared poles, PSD strengths/losses,
positive resistance boundaries and cells1–64. Parsing/normalization validates
without propagation or changing time samples, pole order, strengths or references.

```python
from sipi import startup_port_waves
out = execute_saved(text, max_evaluations=41)
expected = startup_port_waves(startup.analyze(max_evaluations=41),
                             z_ref=[35., 45., 55., 65., 75., 85.]).to_dict()
assert out['status'] == 'complete' and out['error'] is None
assert out['input'] == request.to_dict() and out['result'] == expected
assert out['result']['source_kind'] == 'PSDMulticonductorDebyeRLGCLadderResponse'
assert len(out['result']['incident_sqrt_w'][0]) == 6
```

Analysis runs the physical engine once and [wave conversion](psd_multiconductor_debye_startup_waves.md)
once. Its budget counts actual time rows,2–10000, independently of cell/signal
count; lossless nested inputs retain their original delay-term budget. Too-small
budgets fail before propagation. Existing output type, time, V/I, reference,
port-name, source-kind and wave-array shape guards stay unchanged. Original
physical and wave reconstruction failures propagate without clipping or retry.
Total terminal power retains instantaneous/polarization energy rates and
series, shunt and relaxation losses.

Validation replays19 source variants with ramp and pulse drives through direct,
saved and common execution; all eligible older versions keep their results.
216 pre-edit canonical input/full-wave hashes are checked exactly in source
and installed runs. One/zero/reordered poles, single engine/conversion calls,
strict nested inputs, budgets and output identity corruption are covered.
At this addition, validation covers82 schemas and37 section templates; the all-schema
fixture contains an actual version11 document and retains exact set equality.
Numerical engine/wave formulas and old numerical tests are unchanged.
This storage adapter adds no physical model, accuracy certification, TDR/FFT,
application or platform integration. See [all saved wave versions](startup_waves_document.md).

Additional replay checks preserve rank-one R/G, near-zero strengths0/1e-13/1e-20
and null-only drives. Canonical null auxiliary voltage may be nonzero without
polarization charge or relaxation loss; terminal power retains that distinction.
