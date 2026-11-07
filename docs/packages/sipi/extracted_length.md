# Length boundaries from an extracted cross-section

[한국어](../../locales/ko/pages/packages/sipi/extracted_length.md) · [Length brackets](length_design.md) · [Face-metal lines](face_line.md)

`sipi.line-length-design/2` connects a saved cross-section line to the existing
sampled-band length search. It extracts the entire declared frequency grid once,
then holds R/L/G/C fixed while varying length. It accepts a `transmission-line`
source using line/1–4 or a `volume-line` source using volume-line/1. The nested
line's `length_m` must be zero. Version 1 remains the default explicit-RLGC contract.

```python
from sipi import CrossSectionDocument, stripline
from sipi.line_model import TransmissionLineDocument
from sipi.length_design import LineLengthDesignDocument

cross = CrossSectionDocument(stripline(width=.5e-3, plane_spacing=1e-3,
    thickness=35e-6, eps_r=4., tan_delta=.02, box_width=4e-3),
    mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05))
line = TransmissionLineDocument(cross, [1e9, 2e9], materials={},
    conductor=dict(kind='perfect'), length=0.)
plan = LineLengthDesignDocument(dict(kind='transmission-line', document=line.to_dict()),
    limits=[dict(name='insertion', input_port='near:signal', output_port='far:signal',
                 frequency_hz=[1e9, 2e9], minimum=.7, maximum=None)],
    bounds=[0., 2.], tolerance=1e-5, max_evaluations=32,
    schema='sipi.line-length-design/2')
result = LineLengthDesignDocument.loads(plan.dumps()).solve()
assert result.feasible.passed and not result.infeasible.passed
assert result.infeasible_length_m-result.feasible_length_m <= 1e-5
ledger = result.to_dict()['source_evaluation']
assert ledger['field_extractions'] == 1
assert ledger['evaluations'] == 1+len(result.history) <= 32
assert ledger['resolved_network']['length_m'] == 0.
```

The example uses perfect conductors and dielectric loss. Surface, boundary-metal,
face-metal and volume conductor inputs retain their original skin-depth, material,
mesh, flux and supported-frequency gates. Normalization solves no fields. The
source frequency order, conductor/port names and common real reference are retained;
mixed-mode conversion occurs after each length network is constructed.

The saved budget is 3–10000: **one attempted extraction job plus every attempted
length-network evaluation**, including a failed attempt. An extraction job can
contain many internal field solves; this budget is not a limit on their count,
runtime or memory. The caller's `execute_saved` budget is checked before extraction.
No new field solve is performed at a midpoint or accepted endpoint.

On success, `source_evaluation` retains `phase='complete'`, `field_extractions`,
`length_evaluations`, total `evaluations` and a detached complete `resolved_network`
RLGC source. Original geometry/material input remains in the canonical request;
the Python result also retains `extraction`. The resolved source can be replayed
through version 1. This snapshot reproduces sampled matrices, not the original
field convergence evidence.

`LengthGoalError.source_evaluation` and the shared execution error retain the same
ledger on failure, with phase `extraction`, `network`, `bracket`, `budget` or
`resolution`. A failed extraction has no fabricated resolved model. Later failures
keep the extracted matrices, completed history, failed length when applicable and
underlying exception type. No incomplete bracket is returned as an accepted result.
Version-1 results/errors retain their existing shape without this extra ledger.

Only a feasible lower/infeasible upper bracket is supported. All constraints apply
at declared frequency samples. Bisection finds one boundary; it does not certify a
global maximum, monotonicity, continuous-band performance, measured accuracy or
manufacturing yield. The original field source still needs independent mesh and
outer-boundary convergence evidence; repeated length algebra does not improve it.

Related tests exercise actual scalar face-metal, coupled mixed-mode and volume
extractions, one extraction per request, exact resolved replay, strict nested
input, budget and failure accounting. Independent scikit-rf 2.2.0 endpoint S agrees
within absolute 1e-10; an independent scalar root lies within the accepted bracket
of width at most 1e-5 m. That comparison validates the network search on the same
extracted matrices, not the physical accuracy of those matrices. The previous
distortionless analytical limit and field-source convergence tests remain separate.

```sh
python -m pytest -q tests/sipi/test_extracted_length_design.py tests/sipi/test_length_design.py tests/sipi/test_band.py tests/sipi/test_execution.py
```
