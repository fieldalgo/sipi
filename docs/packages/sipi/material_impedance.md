# Fixed-frequency material impedance studies and goals

Impedance studies and bounded design accept `frequency` in Hz and a `materials`
mapping together. The mapping uses the same scalar or principal-axis models as
[frequency-line extraction](principal_dielectrics.md). Each geometry sample is
meshed separately; the fixed material models are evaluated at the saved frequency.
Omit both arguments to retain the existing constant-section behavior and JSON.
An explicit empty mapping is allowed and uses the section's scalar defaults.

The reported quantity remains the **real quasi-static impedance**: single-line
`z0=sqrt(L_external/Re(C_complex))`, or `z_diff=2*z_odd` for a symmetric pair.
External L comes from the vacuum C0 problem. Complex dielectric loss affects the
electrostatic field and C, but this is **not** the complex lossy characteristic
impedance `sqrt((R+jωL)/(G+jωC))`, an attenuation target or a band optimization.
No conductor-loss approximation is silently selected.

## Geometry tolerance study

```python
from sipi.dielectric import PrincipalAxisDielectric, DebyeDielectric, ConstantDielectric
from sipi.study import ImpedanceStudyDocument

material = PrincipalAxisDielectric(
    DebyeDielectric(2, [2], [1e8]), ConstantDielectric(5, .02), angle_rad=0,
)
parameters = dict(width=.5e-3, substrate_height=.5e-3, eps_r=4,
                  thickness=35e-6, air_height=4e-3, box_width=8e-3)
mesh = dict(edge_size=4e-6, far_size=.25e-3, grade=.2)
study = ImpedanceStudyDocument(
    'microstrip', parameters, quantity='z0', mesh=mesh,
    frequency=1e8, materials={'substrate': material},
    sampling=dict(kind='sweep', count=2,
                  variables=[dict(name='width', lower=.45e-3, upper=.55e-3)]),
)
saved = study.dumps()
result = ImpedanceStudyDocument.loads(saved).analyze()
assert result.failed == 0
result.summary, [row.impedance for row in result.rows]
```

This mode samples **geometry parameters only**. Template parameters containing
`eps_r` or `tan_delta` are rejected as variables even if only some regions have
overrides; this prevents material variation from being silently overridden.
Model-parameter and axis-angle tolerances are not implemented. Sweep, corners,
uniform and correlated-normal sampling retain their existing ordering, seeds,
bounds and failure handling. Invalid normal rows remain failures, never resampled;
any failed row suppresses the aggregate summary. Fixed horizontal pitch and total
plane spacing retain their existing template restrictions.

For `z_diff`, evaluated transverse material tensors must be diagonal in mesh x/y
within relative `1e-12`; tilted nonisotropic tensors are rejected **before meshing**.
This avoids assuming exchange symmetry for a tilted material. Equal-axis models
are isotropic at any angle. The existing 1% self-capacitance symmetry gate still
checks the resulting pair before its mean self term is used. It is not a general
asymmetric-mode solver or proof that arbitrary geometry is symmetric.

## Bounded goal with a separate refinement check

```python
from sipi import ImpedanceDesignDocument

goal = ImpedanceDesignDocument(
    'microstrip', parameters, variable='width', bounds=[.3e-3, .9e-3],
    target=60, quantity='z0', tolerance=1, max_evaluations=24, mesh=mesh,
    frequency=1e8, materials={'substrate': material},
)
solution = ImpedanceDesignDocument.loads(goal.dumps()).solve()
assert abs(solution.residual) <= 1
assert abs(solution.refined_residual) <= 1
solution.parameter, solution.material_evaluation_json
```

Both requested and refined meshes use the same frequency and models. Bisection,
bracket checks, evaluation budgets, retained failure history and mandatory final
refinement are unchanged. A missing bracket or a refined target miss is still a
`GoalSeekError`; a result is not a certified manufacturing tolerance or evidence
that the finite exterior is converged. Check domain size separately.

The direct `seek_impedance(factory, bounds, target, ..., frequency=...,
materials=...)` API accepts the same fixed overrides. Its caller controls the
factory; the engine does not infer what a generic factory parameter means.
The saved design document restricts its named variable to geometry.

## Exact saved contracts and replay

Existing `sipi.impedance-study/1` and `/2`, and `sipi.impedance-design/1`, are
unchanged. A material study uses `/3`, adding `material_evaluation` and including
`fixed_plane_spacing_m` even when null. A material design uses `/2`, adding
`material_evaluation` to its existing fields. That object contains **exactly**
`frequency_hz` and `materials`; each named material is a complete
`sipi.dielectric/1` or `/2` record. Frequency is a finite nonnegative real scalar.
Unknown/missing fields, invalid models, unknown region names and table-range
errors are rejected before meshing. Both public arguments must be present.

The study's `input_json` preserves the complete recipe. Each `StudyRow.document`
is still the **geometry** input and does not carry material overrides. Save the
full study JSON to reproduce rows. A goal result likewise retains the geometry
in `document` and the additional immutable JSON string in
`material_evaluation_json` (None for legacy results). Preserve both or the saved
goal document. Replaying only `document.analyze()` uses its scalar defaults.

For example, replay a single-line study row without losing its materials:

```python
import json
import numpy as np
from sipi.dielectric import dielectric_from_dict, dispersive_line

evaluation = json.loads(result.input_json)['material_evaluation']
models = {name: dielectric_from_dict(record)
          for name, record in evaluation['materials'].items()}
row = result.rows[0]
sweep = dispersive_line(row.document.section, [evaluation['frequency_hz']],
                        materials=models, **row.document.mesh_options)
replayed_z0 = np.sqrt(sweep.L[0, 0] / sweep.C[0, 0, 0])
assert np.isclose(replayed_z0, row.impedance, rtol=1e-10, atol=0)
```

## Verification

Run `python -m pytest -q -s tests/sipi/test_material_impedance.py` together with
the existing study, constraint, design and material suites. Independent scikit-fem
12.0.2 complex/vacuum solves check single and paired sampled impedances at relative
`1e-9`. Homogeneous materials obey `Z=Z_vac/sqrt(Re eps)` within `1e-10`.
An independent Cohn stripline expression checks a dispersive width goal within 1%,
with both mesh residuals within 0.25 Ω. Tensor width goals require both residuals
within 1 Ω. The underlying tensor mesh/outer convergence tests remain required.
JSON compatibility, sampling replay, constraint composition, copies, invalid-input
preflight, failed normal rows and solve budgets are checked separately.

No measured laminate, statistical yield, material fitting, general asymmetric
propagation, new platform, browser or portable interface is certified by this work.

[Studies](study.md) · [Design](design.md) · [Materials](principal_dielectrics.md) ·
[한국어](../../locales/ko/pages/packages/sipi/material_impedance.md)
