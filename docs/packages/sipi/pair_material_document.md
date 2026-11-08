# Saved geometry and material pair targets

`PairImpedanceDesignDocument` selects `sipi.pair-impedance-design/2` when
`material_variables` is supplied. It reuses the [pair material API](pair_material_design.md)
through named numeric-leaf bindings, without serializing functions or executable
code. The exactly two positive bounded variables can be one geometry parameter
and one material alias, or two material aliases. Both real symmetric-pair
impedance targets remain ordered `z_diff`, `z_common` in ohms at one fixed
nonnegative frequency. This does not add a complex lossy or broadband objective.

The example's midpoint already satisfies the independently checked thin-stripline
targets, so it needs only requested/refined evaluations. A distant initial point
requires a larger budget, for example 64 with `initial=[.35e-3,5.5]`.

```python
from sipi import PairImpedanceDesignDocument
from sipi.dielectric import DebyeDielectric
from sipi.execution import normalize_saved, execute_saved

goal = PairImpedanceDesignDocument('coupled_stripline',
    dict(width=.5e-3, gap=.1e-3, plane_spacing=1e-3, eps_r=1., box_width=8e-3),
    variables=['width', 'strength'], bounds=[[.3e-3,.7e-3],[2.,6.]],
    targets={'z_diff':69.86609070536932, 'z_common':30.721416289368904},
    tolerances={'z_diff':.5, 'z_common':.2}, max_evaluations=2,
    mesh=dict(edge_size=1e-6, far_size=.125e-3, grade=.1),
    frequency=1e9, materials={'dielectric':DebyeDielectric(2.,[4.],[1e9])},
    material_variables={'strength':dict(region='dielectric',path=['strengths',0])})
text = goal.dumps()
assert goal.to_dict()['schema'] == 'sipi.pair-impedance-design/2'
assert normalize_saved(text) == text
out = execute_saved(text, max_evaluations=2)
assert out['status'] == 'complete' and out['result']['evaluations'] == 2
rows = out['result']['history']
assert rows[0]['material_evaluation'] == rows[1]['material_evaluation']
assert all(abs(r)<=t for r,t in zip(out['result']['refined_residuals_ohm'], [.5,.2]))
```

## Strict binding and preflight contract

Version 2 has every [version 1 field](pair_design_document.md) plus required
`material_variables`. `material_evaluation` must be a valid fixed-frequency
model mapping rather than null. Each alias maps to exactly `region` and `path`.
The region must be overridden, and the nonempty path selects an existing finite
numeric leaf under that model's `parameters`, using string keys and integer
list indices. Boolean indices, nonnumeric targets, duplicate target leaves,
geometry-name collisions, unknown fields and unused aliases are rejected.
There must be one or two aliases, all present in the two ordered `variables`.
All bounds remain strictly positive even if a model separately allows zero or
signed values. This is the same binding contract used by material studies.

Version 1 remains fixed-material only and rejects the new field. Version 2 is
not silently downgraded. Loading copies and canonicalizes input; it validates
nominal geometry/material and all four corners through the study validator.
It also checks geometry and sampled material at the explicit initial point or
default midpoint before any field or optimizer call. Valid corners do not prove
that the interior is valid: diagonal principal-axis tensors at angles pi/2 and
pi have a tilted tensor at 3pi/4, which is rejected for symmetric-pair targets.
The unmeshed preflight is outside the solve-attempt budget.

Existing pitch/stack constraints still apply to geometry variables. For example,
a width alias-free geometry parameter and material strength can coexist with
fixed pitch; the derived gap must not also be independent. Geometry dielectric
parameters cannot compete with explicit material overrides.

## Execution and limits

`solve()` supplies the same ordered values to geometry and material factories.
Every completed history row retains its own geometry and encoded model; the
selected inputs are frozen for refinement without callback reuse. Execution
keeps current failed models and earlier rows' distinct models with stage,
cause and actual attempted count. Caller budget rejection precedes solving.
Save the goal JSON to repeat a search and each row's two snapshots to replay it.

Two aliases do not imply two identifiable material properties. For homogeneous
Debye material at its pole frequency, real permittivity is `eps_inf+strength/2`;
(2,4) and (3,2) therefore give the same two real impedances at fixed geometry.
No unique material estimate, automatic pole fitting or measured calibration is
claimed. Physical bounds and identifiability remain the caller's responsibility.

Acceptance checks strict schema/path parsing, ordering, copy isolation,
geometry constraints, initial and corner model validation, pre-solve budgets
and retained failure models. Actual saved execution equals the raw API on the
same canonical geometry and mesh. Requested/refined and independent Cohn values
meet (.5,.2) ohm gates for the thin fixture above. Distant-start recovery and
outer-domain convergence remain separately covered by the underlying API.
Older readers reject version 2; this does not update an application engine,
prove general accuracy or establish browser/Windows acceptance.

[Saved pair goals](pair_design_document.md) · [Execution](execution.md) ·
[한국어](../../locales/ko/pages/packages/sipi/pair_material_document.md)
