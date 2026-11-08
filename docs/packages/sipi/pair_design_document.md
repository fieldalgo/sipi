# Saved two-parameter impedance goals

`PairImpedanceDesignDocument` saves `sipi.pair-impedance-design/1` for geometry
variables and fixed materials. [Version 2](pair_material_document.md) adds
explicit material-leaf bindings. It connects
named template parameters to the [two-target API](pair_design.md), without
serializing callables or running code from JSON. Targets and absolute tolerances
are objects with exactly `z_diff` and `z_common` keys, in ohms; JSON key order
never selects a mode. The meaning remains real electrostatic symmetric-pair
impedance, not complex lossy, asymmetric-launch or terminal impedance.

```python
from sipi import PairImpedanceDesignDocument
from sipi.execution import normalize_saved, execute_saved

goal = PairImpedanceDesignDocument('coupled_grounded_coplanar',
    dict(width=.5e-3, gap=.3e-3, ground_gap=.2e-3, ground_width=1e-3,
         substrate_height=.5e-3, eps_r=1., box_width=12e-3, air_height=6e-3),
    variables=['width', 'gap'], bounds=[[.3e-3, .7e-3], [.1e-3, .5e-3]],
    targets={'z_diff':172.45677879183611, 'z_common':65.9597000672247},
    tolerances={'z_diff':1.5, 'z_common':.5}, max_evaluations=2,
    mesh=dict(edge_size=2e-6, far_size=.125e-3, grade=.15))
text = goal.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=2)
assert output['status'] == 'complete'
assert output['result']['quantities'] == ['z_diff', 'z_common']
assert output['result']['evaluations'] == 2
```

This example's midpoint is already close to the independent thin-conductor
reference target. Its two attempts are the requested and refined meshes. A
search from a more distant initial point needs a larger saved budget, such as
64 with `initial=[.35e-3,.45e-3]`. The callable API's probe cost and mesh/physical
limits apply unchanged. Older readers reject the new schema; this contract does
not update a browser or native application engine automatically.

## Exact input contract

Required top-level fields are `schema`, `template`, `parameters`, `variables`,
`targets_ohm`, `tolerances_ohm`, `initial`, `max_evaluations`, `mesh`,
`fixed_pitch_m`, `fixed_plane_spacing_m`, `material_evaluation`. Each of the two
ordered `variables` has exactly `name` and `bounds`; names must be distinct.
Each bound is a strictly increasing positive finite pair in that parameter's
units. `initial` is null (midpoint) or two in-bound values in variable order.
Targets/tolerances are strictly positive, and the attempt budget is 2..10000.
Unknown fields, duplicate keys, nonfinite values and unsupported versions fail.
Constructor input and dictionary accessors are detached copies.

The existing symmetric-pair study registry validates nominal, four corner and
initial geometries, and resolves nominal mesh settings. It performs no field
solve, statistical study or optimizer call while loading. Initial material
validity is also checked when overrides are present. This unmeshed geometry
preflight is outside the solve-attempt budget; corner validity neither proves
validity of every interior point nor bounds impedance. Interior errors remain
failures in the solver history.

`fixed_pitch_m` and `fixed_plane_spacing_m` reuse study constraints. For example,
width and one layer height can vary while gap and the other layer height are
derived. A derived gap cannot also be an independent variable. Version 1
does not save material-leaf aliases: optional fixed-frequency scalar/principal
models use the exact `material_evaluation` object (`frequency_hz`, `materials`)
or null. Existing override and transverse-symmetry restrictions remain active.

## Execution and replay

`solve()` returns the API's `PairImpedanceDesign`. `execute_saved()` uses the
existing `sipi.execution/1` envelope. The caller's `max_evaluations` must cover
the saved budget before solving; it is never silently clamped. A successful
result contains ordered variables' values, both modal targets/tolerances,
requested/refined values and input snapshots, completed history and the frozen
material evaluation. Save the goal JSON to repeat the search; the selected
geometry alone does not describe its original bounds or constraints.

A failed goal has `status='failed'`, `result=None` and preserves attempted count,
stage, failed parameters, cause type, available input, completed history and
fixed materials. Malformed inputs and an insufficient caller budget raise
before solving. A failure does not become a partial success. The transport
adapter does no file/network/process operations or application deployment.

Acceptance checks strict parsing without fields, variable/mode order, composed
constraints, fixed-material replay, caller isolation, budget rejection and
failure serialization. The thin image-panel fixture checks real saved/direct
execution equality and both mesh outputs against 1.5/.5 ohm goals; a separate
160-panel Green calculation at the selected geometry meets the same goals.
The underlying API tests cover a search from a distant initial point, mesh and
outer-domain verification. These gates do not establish measured-board,
global optimization, browser or Windows acceptance.

[Execution](execution.md) · [Two-target API](pair_design.md) ·
[한국어](../../locales/ko/pages/packages/sipi/pair_design_document.md)
