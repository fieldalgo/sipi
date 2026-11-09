# Common-current forward-impedance sampling

**English** | [한국어](../../locales/ko/pages/packages/sipi/common_forward_line_study.md)

Explicit `sipi.line-quantity-study/3` adds `common_forward_impedance_real`
for sweep, corners, uniform and correlated-normal sampling. It also retains
the scalar and differential quantities. The constructor default is still `/1`;
versions1 and2 continue rejecting the common-current quantity.

Each value is Re(Zcc) in ohms, using full lossy asymmetric RLGC at one fixed
positive frequency. With Vc=(V1+V2)/2, Ic=I1+I2 and launch Id=(I1-I2)/2=0,
Vc=Zcc Ic while differential voltage may remain nonzero. No downstream Id=0,
decoupled eigenmode or abs(Zcc) assumption is made. See the
[forward contract](common_forward_line_goal.md) and [saved goals](common_forward_goal_document.md).

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.execution import normalize_saved, execute_saved

def metal(sigma, rms):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness=dict(kind='hammerstad', rms_m=rms))
source = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3, substrate_height=.5e-3,
        eps_r=4., tan_delta=.02, left_thickness=35e-6, right_thickness=50e-6,
        air_height=10e-3, box_width=24e-3), quantity='z_diff_forward',
    frequency=1e9, materials={}, fixed_pitch_m=.95e-3,
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='left_width', lower=.6e-3, upper=.8e-3)]))
doc = LineQuantityStudyDocument(source, schema='sipi.line-quantity-study/3',
    conductor=dict(kind='surface-boundaries',
        conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
        reference=metal(58e6, 0.), ground_thickness=35e-6),
    quantity='common_forward_impedance_real')
assert normalize_saved(doc.dumps()) == doc.dumps()
result = doc.analyze(max_evaluations=3)
assert result.failed == 0 and len(result.rows) == 3
assert result.unit == 'ohm' and result.variable_names == ('left_width',)
assert all(row.value > 0 and row.phase == 'complete' for row in result.rows)
```

The four root keys are schema,study,conductor,quantity. Nested study/3 or/4
uses `z_diff_forward` solely as the paired geometry/material input contract;
that quasi-static source study is never analyzed. Supported fixed pitch,
total stack height, numeric material leaves and fixed line/6 conductor laws
are reused. Every sample becomes a zero-length line/6 input with a50-ohm
network reference; that reference does not define Zcc.

The nominal resolved mesh settings are reused, rather than one physical mesh.
All generated samples are attempted in order. Failed geometry, materials,
input construction, extraction or diagnostics retain the original sample,
phase and available intermediate inputs. Later samples still run. There is
no clipping, resampling or dropping failed rows; any failure suppresses the
whole summary. Sampling-generation errors and an exceeded count budget reject
before field work. A per-call sample budget does not bound memory or time.

```python
import json
import statistics
import numpy as np
values = [row.value for row in result.rows]
np.testing.assert_allclose(result.summary['mean'], statistics.mean(values), rtol=1e-12)
np.testing.assert_allclose(result.summary['sample_std'], statistics.stdev(values), rtol=1e-12)
for row in result.rows:
    mixed = row.result.characteristic().mixed_mode().z_characteristic[0]
    np.testing.assert_allclose(row.value, mixed[1, 1].real, rtol=1e-10)
    assert abs(mixed[0, 1]) > 1e-3
report = execute_saved(doc.dumps(), max_evaluations=3)
assert report['status'] == 'complete' and report['result'] == result.to_dict()
assert report['result']['scope'] == 'stated-samples-descriptive-not-production-yield'
json.dumps(report, allow_nan=False)
```

Statistics are descriptive: mean, sample standard deviation (ddof1), and
linear-interpolated5th/95th percentiles. They are neither confidence intervals
nor measured production yield. Within-row normal correlation is retained,
while iid distribution assumptions are not inferred from manufacturing data.
The direct yield assessment API and explicit [saved yield /2](common_forward_line_yield.md)
also admit study /3 under a separate iid inference contract. Saved yield /1
and fixed selection /2 still accept study /1 or /2 only.

Validation replays widths.6/.7/.8mm against direct lines and independent
balanced2N telegrapher eigenspaces within1e-10, and independent statistics
within1e-12. Each of these three samples separately halves edge/far/grade;
requested/refined relative changes must be<=.005. With the frozen refined
mesh controls, box/air24/10mm→36/15mm→48/20mm must remain within.005 of
the refined base and successive absolute differences must decrease.
These finite-domain checks are not infinite-domain error bounds or guarantees
for every possible sampled input. General sampling does not refine every row.

For a homogeneous PEC pair, an independent SPD vacuum geometric mean and
Zvac/sqrt(eps_r*(1-j*tan_delta)) check four material corners eps3/5×loss0/.04
within1e-10 and retain exact material snapshots. A seeded correlated-normal
fixture preserves three invalid rows and continues through all eight samples.
Strict controls, identity, original failures, previous-version parity and
old94canonical inputs are checked in source and installed packages.
ENKO examples and95schemas/37templates accompany this explicit extension.
Numerical extraction and statistical formulas remain unchanged. No measured/
full-wave accuracy, new app/platform or deployment acceptance is implied.
