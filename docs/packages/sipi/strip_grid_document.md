# Saved bounded thin trace/grid capacitance inputs

**English** | [한국어](../../locales/ko/pages/packages/sipi/strip_grid_document.md)

`StripGridCapacitanceDocument` stores the fourteen explicit inputs of the
[bounded three-region thin trace/grid cell](strip_grid.md) in
`sipi.strip-grid-capacitance/1`. This is an input schema for total static C[F],
not a line, frequency or wave model. The underlying physical scope, geometry,
material and refinement limits remain unchanged.

```python
from sipi import StripGridCapacitanceDocument

document = StripGridCapacitanceDocument(
    pitch=1e-3, grid_width=.5e-3, trace_width=.5e-3, height=.5e-3,
    top_clearance=1e-3, backside_depth=1e-3,
    eps_substrate=3.8, eps_above=1., eps_below=1.,
    transverse_periods=1, cells_per_pitch=4,
    cells_substrate=2, cells_above=4, cells_below=4)
saved = document.dumps()
reloaded = StripGridCapacitanceDocument.loads(saved)
assert reloaded.dumps() == saved
result = reloaded.analyze(max_evaluations=1)
assert result.capacitance_f > 0
```

The root has exactly fifteen keys: `schema`, `pitch_m`, `grid_width_m`,
`trace_width_m`, `height_m`, `top_clearance_m`, `backside_depth_m`,
`eps_substrate`, `eps_above`, `eps_below`, `transverse_periods`,
`cells_per_pitch`, `cells_substrate`, `cells_above`, `cells_below`.
SI geometry, positive real relative permittivity and strict integer counts
are required. Missing/extra keys, duplicate JSON keys, unsupported versions,
booleans, nonfinite values, alternate units and off-grid widths are rejected.
Three permittivities and all three vertical counts remain explicit.

`from_dict`, `loads`, `dumps`, `to_dict` and common normalization perform the
original scalar/alignment/node/tetrahedron/finite-volume/top-clearance checks
without generating a mesh or solving a field. Returned dictionaries are fresh
snapshots; canonical JSON uses sorted keys and excludes nonfinite numbers.
No geometry, counts or materials are rounded, reduced or inferred.

Direct `analyze(max_evaluations=1)` accepts integer budgets1..10000 and performs
one actual field evaluation, independently of the geometric resource limits.
The [common executor](execution.md) retains its existing2..10000 budget range;
passing2 still performs one field solve for this document. Budget values do not
request repeated solutions or convergence checks.

```python
from sipi.execution import normalize_saved, execute_saved

assert normalize_saved(saved) == saved
# Common execution keeps its existing minimum budget of 2.
# The new static document still performs exactly one field evaluation.
output = execute_saved(saved, max_evaluations=2)
assert output['status'] == 'complete'
assert output['result'] == result.to_dict()
assert not output['result']['fields_included']
```

Replay checks exact result/cell/field types and input identity; derived
node/tetrahedron/electrode counts; resolved widths and edge indices; material
and field array shapes. It also checks coordinate extents, index bounds,
electrode planes and the coordinate-defined three-region dielectric values.
These checks use returned geometry, without constructing another mesh. Original
field exceptions propagate, and the underlying numerical gates are unchanged.
Successful replay does not establish physical accuracy or an open-space limit.

Common output is compact. The direct `StripGridCapacitance` result can export
mesh/materials and potentials with `to_dict(include_fields=True)`. Input schema
and output serialization are distinct; expanded field output is not a saved
input file. Files are read/written by callers, not implicitly by the engine.

Verification in `tests/sipi/test_strip_grid_document.py` compares direct and
saved full-field results exactly for partial/solid grids, a wider transverse
domain, nonuniform vertical spacings with distinct dielectric regions and
roundoff-aligned requested widths. Strict keys/units/counts/budgets, copied
snapshots, result/geometry/material corruption, old-kind rejection and original
failures are covered. Independent field/analytic/refinement tests remain in the
physical API suite and are run alongside this adapter. This unit adds no
numerical approximation, new dependency or platform/measurement validation.
