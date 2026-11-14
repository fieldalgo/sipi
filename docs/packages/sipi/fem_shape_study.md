# Checked FEM-current geometry and material sampling

`FEMShapeLineQuantityStudyDocument` explicitly selects the checked FEM shape-current
line for every sample. The nested `ImpedanceStudyDocument` supplies the existing
study/3 or /4 geometry, fixed positive frequency, dielectric models, constraints
and sampling. Its `z0` or `z_diff_forward` selects scalar or paired inputs; the
quasi-static source calculation is not executed.

```python
from sipi import FEMShapeLineQuantityStudyDocument
from sipi.study import ImpedanceStudyDocument

source = ImpedanceStudyDocument(
    'stripline', dict(width=.0004, plane_spacing=.002, eps_r=4.,
                     thickness=.00005, box_width=.008),
    quantity='z0', frequency=2e9, materials={},
    mesh=dict(edge_size=5e-6, far_size=.0002, grade=.1),
    sampling=dict(kind='sweep', count=2,
                  variables=[dict(name='width', lower=.00039, upper=.00041)]))
metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness=dict(kind='smooth'))
document = FEMShapeLineQuantityStudyDocument(
    source, conductors={'signal': metal}, reference=metal,
    ground_thickness=35e-6, quantity='impedance_real')
assert FEMShapeLineQuantityStudyDocument.loads(document.dumps()).dumps() == document.dumps()
# result = document.analyze(max_evaluations=2)
# print(result.to_dict())
```

The strict six-key `sipi.fem-shape-line-quantity-study/1` contract contains
`schema`, `study`, `conductors`, `reference`, `ground_thickness_m` and `quantity`.
Each signal has one fixed whole-boundary surface metal; all grounded metals share
the fixed reference law. The [saved FEM line](fem_shape_line.md) validates those
laws, including layered metals, finite-core and skin-depth admission. These metal
parameters are not sampled. Geometry and dielectric numeric leaves follow the
nested study's existing sampling rules. Unknown keys, duplicate JSON keys and
nonfinite input numbers are rejected.

Choose `impedance_real` (Re Zc, ohm) or `attenuation` (Re gamma, Np/m) for a scalar
source. A paired source admits `differential_forward_impedance_real` (Re Zdd,
Ic=0 launch) or `common_forward_impedance_real` (Re Zcc, Id=0 launch). Asymmetric
coupling remains present; the launches are not asserted to be independent modes.
Every row creates a zero-length line at a fixed 50-ohm network reference. These
characteristic quantities do not depend on that port reference.

All samples are generated and budgeted before field work. The budget counts line
attempts, including failed or duplicate rows, rather than the line's internal
capacitance requests or velocity solves. Samples retain their original order and
values; later rows run after a failure. There is no clipping, rejection sampling,
resampling, deduplication or reweighting. KeyboardInterrupt/SystemExit propagate.
Nominal resolved mesh controls are reused, while each changed geometry is meshed
again. No automatic mesh or outer-domain convergence certificate is produced.

Every row retains parameters, dielectric evaluation, normalized line input,
phase, error type/message and any extracted result. Complete currents include the
original gradient evidence and all shape-energy derivative samples. A typed line
failure retains its staged complete or partial current record in `cause_details`;
a later diagnostic failure retains the completed current under `current_solver`.
An absent current record is not reconstructed. Failure-only nonfinite markers
follow the saved line contract.

Descriptive minimum/maximum, mean, sample standard deviation and linear p05/p95
exist only if every row succeeds. Failed rows have no value and suppress the
entire summary. Correlation, corners or a finite sweep do not establish production
yield; this interface supplies no confidence interval. Common saved execution
reports a study containing failed rows as `incomplete`, with the rows preserved.
Execution records and projects retain that receipt without rerunning it.

Validation uses actual scalar/paired width samples, dielectric-loss samples,
independent scalar square roots and matrix-square-root characteristic relations,
mesh refinement, and saved complete/partial failures. Cached extracted fields in
transport-only checks are explicitly distinguished from new field calculations.
The current derivative gates, original gradient flux gate and metal gates remain
unchanged. Full regression, platform support, runtime bounds and empirical
accuracy require separate evidence. Existing saved study defaults are unchanged.

[한국어](../../locales/ko/pages/packages/sipi/fem_shape_study.md)
