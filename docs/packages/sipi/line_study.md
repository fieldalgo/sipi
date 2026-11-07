# Sampling lossy scalar-line quantities

[한국어](../../locales/ko/pages/packages/sipi/line_study.md) · [Source sampling](study.md) · [Lossy goals](line_goal_document.md)

`LineQuantityStudyDocument` evaluates full extracted lossy R/L/G/C for each
geometry/material sample. Its quantity is `impedance_real` (Re(Zc), ohm) or
`attenuation` (Re(gamma), Np/m). These are scalar forward-wave quantities,
not abs(Zc), finite-line insertion loss or pair modal targets.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.execution import normalize_saved, execute_saved

mesh = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)
source = ImpedanceStudyDocument('stripline', dict(width=.5e-3, plane_spacing=1e-3,
    thickness=50e-6, eps_r=4., tan_delta=.02, box_width=4e-3),
    quantity='z0', frequency=1e9, materials={}, mesh=mesh,
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='width', lower=.3e-3, upper=.8e-3)]))
study = LineQuantityStudyDocument(source, quantity='impedance_real',
    conductor=dict(kind='surface', conductivity=58e6, relative_permeability=1.,
        roughness=dict(kind='hammerstad', rms_m=.5e-6), ground_thickness=35e-6))
assert normalize_saved(study.dumps()) == study.dumps()
report = execute_saved(study.dumps(), max_evaluations=3)
assert report['status'] == 'complete'
assert report['result']['count'] == 3 and report['result']['failed'] == 0
assert report['result']['unit'] == 'ohm'
assert report['result']['summary']['minimum'] > 0
```

The exact saved fields are `schema='sipi.line-quantity-study/1'`, `study`,
`conductor` and `quantity`. The source study must be /3 or /4, a scalar z0
template, and one fixed positive material-evaluation frequency. Its z0 chooses
the source contract, not the computed lossy value. No source study is analyzed.
Existing sweep/corners/uniform/correlated-normal samples, seeds, numeric material
leaf bindings and fixed total plane spacing are reused without changing their
definitions. Multiple geometry/material variables are allowed.

The conductor is a fixed strict line/6 record, including explicit ground faces
when present. Each candidate is a zero-length line/6 at a 50-ohm reference;
that reference does not define its Zc or gamma. Nominal mesh settings are reused
but geometry is remeshed per sample. This does not prove convergence of every
sample. Check physical validity and mesh/outer-domain convergence for the range.

```python
import json
from sipi.dielectric import ConstantDielectric

loss_source = ImpedanceStudyDocument('stripline', dict(width=.5e-3,
    plane_spacing=1e-3, eps_r=1., box_width=4e-3), quantity='z0', frequency=1e9,
    materials={'dielectric': ConstantDielectric(4., .02)}, mesh=mesh,
    material_variables={'loss': dict(region='dielectric', path=['tan_delta'])},
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='loss', lower=0., upper=.1)]))
loss_study = LineQuantityStudyDocument(loss_source, conductor=dict(kind='perfect'),
                                      quantity='attenuation')
result = loss_study.analyze(max_evaluations=3)
assert result.failed == 0 and result.rows[0].value == 0
assert result.variable_names == ('loss',) and result.unit == 'Np/m'
assert result.summary['minimum'] == 0
json.dumps(result.to_dict(), allow_nan=False)
```

Normalization preserves the source's bounded endpoint geometry/material
preflight and checks nominal conductor guards without meshing. Normal sampling
is unbounded: invalid physical samples remain failed rows. Generated samples
are neither clipped nor replaced. Sampling overflow raises before field work,
because nonfinite sample inputs cannot form a valid replay report.

The caller's `max_evaluations` (integer 2–10000, default 128) must cover all
samples before field work starts. Every generated sample is attempted in order,
even after failures. Rows retain index, ordered `sample_values`, available
template parameters, actual sampled material input and canonical line input,
plus either the scalar value or error type/message and phase. `variable_names`
defines vector order. If a derived input cannot be represented as finite JSON,
that snapshot is null; the original sample and failure remain. Phases are
parameters, materials, input, extraction, diagnostic, or complete. Python rows
also retain available full line results. Shared output omits those objects but
can replay successful fields from their exact line inputs.

Shared execution uses `incomplete` if any row fails and keeps every row with
summary null. It does not compute partial statistics from only successful rows.
If all succeed, summary contains minimum, maximum, mean, sample standard
deviation (ddof=1), and linear-interpolated p05/p95. Scaling nonnegative values
avoids unnecessary intermediate overflow. Zero attenuation remains valid.
These are descriptive statistics for the stated samples: no production yield,
confidence interval, distribution calibration or worst-case proof is inferred.
Input/sample budgets do not bound memory, elapsed time or mesh complexity.

Tests compare direct line inputs/RLGC/values within 1e-10, homogeneous PEC
attenuation samples with their closed form within 1e-10, and scikit-rf Zc/gamma
using identical extracted RLGC within 1e-10. Independent stable statistics and
manual percentile interpolation agree within 1e-12, including zero, extreme
finite and subnormal inputs. Tests retain correlated-normal failures, later
attempts, joint geometry/material samples, fixed height and ground-face laws.
Saved-goal replay is also checked after sharing source construction. These are
engine contracts, not measured manufacturing, app or Windows acceptance.

```sh
python -m pytest -q tests/sipi/test_line_study.py tests/sipi/test_line_goal_document.py tests/sipi/test_execution.py tests/sipi/test_material_variables.py
```
