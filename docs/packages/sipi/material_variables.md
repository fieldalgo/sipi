# Material parameter tolerance studies

[한국어](../../locales/ko/pages/packages/sipi/material_variables.md) · [Studies](study.md)

`ImpedanceStudyDocument` writes `sipi.impedance-study/4` when
`material_variables` is supplied. Version 4 adds this required object to version
3's exact fields. Existing versions retain their original interpretation.

A binding maps a sampling alias to `{region, path}`. The region must be present
in the explicit material overrides. The path starts at that model's `parameters`
object and selects an existing finite numeric leaf. Dictionary steps are strings;
array steps are nonnegative, exact integer indices (booleans are rejected).
Aliases cannot collide with template parameter names; targets cannot repeat.
Every binding must occur among the sampling variables. The combined number of
geometry and material variables remains 1–8.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import DebyeDielectric

plan = ImpedanceStudyDocument('stripline',
    dict(width=.5e-3, plane_spacing=1e-3, eps_r=1), quantity='z0',
    frequency=1e8, materials={'dielectric': DebyeDielectric(2, [3], [1e8])},
    material_variables={'pole': dict(region='dielectric', path=['relaxation_hz', 0])},
    sampling=dict(kind='sweep', count=3,
                  variables=[dict(name='pole', lower=5e7, upper=2e8)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
restored = ImpedanceStudyDocument.loads(plan.dumps())
result = restored.analyze()
assert result.failed == 0
assert result.rows[0].material_evaluation_json is not None
```

Examples of paths are `['eps_r']` or `['tan_delta']` for a constant model,
`['strengths', 0]` or `['relaxation_hz', 0]` for Debye,
`['eps_ref']` or `['tan_delta_ref']` for wideband,
`['eps_r', 0]` for a table, and `['axis1', 'parameters', 'eps_r']` or
`['angle_rad']` for principal axes. Units are those of the original model:
relative permittivity, dimensionless loss tangent, Hz, or radians. Model kinds,
array lengths and schema versions cannot be varied. Frequency is fixed for the
study; changing a model's calibration frequency is not changing the observation
frequency.

All four sampling modes support joint geometry/material variation and correlated
normal variables. Geometry uses its existing fixed-pitch/plane-spacing rules.
Legacy template `eps_r`/`tan_delta` variables remain forbidden when overrides are
present; use an explicit model binding so no sample is silently overridden.

Construction validates the nominal model and every bounded corner without field
solving. Corners do not prove every intermediate model is valid: each actual row
is validated again, including table ordering/range, wideband calibration and
pair/tensor symmetry. Invalid normal samples are retained, never clipped or
resampled; any failed row suppresses the summary. Sweeps/corners are descriptive
samples, not probability distributions or worst-case guarantees.

`samples()` retains independent variables in listed order. `sample_parameters()`
contains only full geometry arguments. `sample_material_evaluations()` returns
detached actual material inputs, including invalid normal samples. Every version
4 result row preserves its actual `material_evaluation_json`, including failures.
The cross-section document alone does **not** replay material overrides. Save the
full study input and use each row's material input for isolated reproduction.
The shared execution adapter accepts version 4 and exports row
`material_evaluation` objects; old result shapes are unchanged.

The target is real quasi-static impedance from `Re(C)` and vacuum-derived external
`L`. Varying loss can affect this quantity through the complex field distribution;
it is not an attenuation, complex characteristic impedance, yield or band target.
There is no automatic material fitting, validity-range extension or per-row mesh
convergence. The workbench's previously built engine remains separately pinned;
adding this engine contract does not update that executable or its web assets.

Validation includes homogeneous `Z*sqrt(eps_real)` invariance within relative
1e-10, independently evaluated Debye pole changes, actual scikit-fem 12.0.2 complex
P1 impedance comparison within 1e-10, strict leaf/path checks, joint sampling,
failed-row retention and saved execution. Existing field references and refinement
checks remain required. The sampling extension does not change meshing or the
field solver and does not establish measured material accuracy.

```sh
python -m pytest -q tests/sipi/test_material_variables.py tests/sipi/test_material_impedance.py tests/sipi/test_study.py tests/sipi/test_stripline_studies.py tests/sipi/test_execution.py tests/sipi/test_sipi_references.py
```
