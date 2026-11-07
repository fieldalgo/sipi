# Sampling lossy differential forward impedance

[한국어](../../locales/ko/pages/packages/sipi/differential_line_study.md) · [Scalar study](line_study.md) · [Forward launch](differential_line_goal.md) · [Source samples](study.md)

Explicit `sipi.line-quantity-study/2` adds the quantity
`differential_forward_impedance_real` to the existing scalar study contract.
The constructor defaults to scalar-only `/1`. Version 2 scalar quantities keep
the same behavior; future metric names are not automatically accepted.

A paired source is study/3 or /4 with `z_diff_forward`, exactly two ordered
signals and one positive fixed frequency. Modal `z_diff` is rejected rather
than reinterpreted. Each sample uses full lossy Zc and the real part of
Zdd=[1,-1] Zc [1,-1]^T in ohms. It assumes Id=(I1−I2)/2 and Ic=I1+I2=0
at the launch plane. Common voltage and asymmetric coupling remain. This is
not an independent eigenmode, a finite-terminal impedance, a magnitude, or a
claim that Ic stays zero along the line.

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
        air_height=5e-3, box_width=12e-3), quantity='z_diff_forward',
    frequency=1e9, materials={}, fixed_pitch_m=.95e-3,
    mesh=dict(edge_size=2.5e-6, far_size=.125e-3, grade=.075),
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='left_width', lower=.6e-3, upper=.8e-3)]))
study = LineQuantityStudyDocument(source, schema='sipi.line-quantity-study/2',
    quantity='differential_forward_impedance_real',
    conductor=dict(kind='surface-boundaries',
        conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
        reference=metal(58e6, 0.), ground_thickness=35e-6))
assert normalize_saved(study.dumps()) == study.dumps()
report = execute_saved(study.dumps(), max_evaluations=3)
assert report['status'] == 'complete'
assert report['result']['count'] == 3 and report['result']['failed'] == 0
assert report['result']['unit'] == 'ohm'
assert report['result']['summary']['minimum'] > 0
assert all(row['input']['schema'] == 'sipi.transmission-line/6'
           for row in report['result']['rows'])
```

The exact top-level fields are schema, study, conductor and quantity. Source
sweep, corners, uniform and correlated-normal sampling retain their original
vectors, order, seed and correlation. Multiple geometry/material numeric-leaf
variables, fixed pitch and supported total stack-height constraints are reused.
The source's real quasi-static study is not analyzed. Conductor laws are fixed
strict line/6 records; each sample gets a zero-length line/6 input at a 50-ohm
network reference, which does not define its Zdd.

Bounded-source endpoint geometry/material preflight and nominal conductor
checks remain before meshing. Unbounded normal samples can have invalid widths,
gaps or material values. Keep these rows, their original vectors, phase, error
and all representable intermediate inputs; do not clip, replace or drop them.
Later samples are still attempted. The caller budget checks the entire count
before fields. Sampling overflow raises before fields without resampling.

Shared execution returns `incomplete` if any row fails, with summary=null and
all rows retained. Only an entirely successful set receives minimum, maximum,
mean, sample standard deviation (ddof=1), and linear p05/p95. These are finite
sample descriptions, not yield confidence intervals, a worst-case bound or
production acceptance. Existing mesh settings are reused while each geometry
is remeshed; convergence of every sample is not automatically established.
Inspect mesh/outer-domain validity across the range. Full matrices remain in
Python row results or can be recovered by replaying each saved line.

Tests require direct asymmetric finite-metal sample RLGC/Zc/ReZdd agreement
within 1e-10 and independent balanced voltage/current forward eigenspace
agreement within 1e-10. Homogeneous PEC epsilon/loss corners use the analytic
Zvac/sqrt(eps_r*(1-j*tan_delta)) relation within 1e-10; this uses a computed
vacuum geometry reference. Independent descriptive statistics require 1e-12.
Correlated-normal invalid widths/gaps stay in their exact original positions,
with later valid rows preserved. Fixed height, scalar v2 equivalence, identity
and diagnostic failures, schema and budget guards are also checked. These
related tests do not establish new measured geometry accuracy, a full regression,
application support or Windows acceptance.

```sh
python -m pytest -q tests/sipi/test_differential_line_study.py tests/sipi/test_line_study.py tests/sipi/test_execution.py tests/sipi/test_material_variables.py
```
