# Saved finite ground-grid thickness inputs

**English** | [한국어](../../locales/ko/pages/packages/sipi/thick_grid_strip_document.md)

`ThickGridStripCapacitanceDocument` stores all sixteen inputs of the
[finite-thickness ground-grid cell](thick_grid_strip.md) in
`sipi.thick-grid-strip-capacitance/1`. The model has a thin trace, three real
dielectric regions and explicit insulating boundaries. It computes total static
C[F]; geometry, material and qualified refinement limits remain unchanged.

```python
from sipi import ThickGridStripCapacitanceDocument

document = ThickGridStripCapacitanceDocument(
    pitch=1e-3, grid_width=.5e-3, trace_width=.5e-3, height=.5e-3,
    top_clearance=1e-3, backside_depth=1e-3, ground_thickness=.25e-3,
    eps_substrate=3.8, eps_above=1., eps_below=1.,
    transverse_periods=1, cells_per_pitch=4, cells_substrate=2,
    cells_above=4, cells_below=3, cells_grid=1)
saved = document.dumps()
reloaded = ThickGridStripCapacitanceDocument.loads(saved)
assert reloaded.dumps() == saved
result = reloaded.analyze(max_evaluations=1)
assert result.capacitance_f > 0
```

The root has exactly seventeen keys: `schema`, `pitch_m`, `grid_width_m`,
`trace_width_m`, `height_m`, `top_clearance_m`, `backside_depth_m`,
`eps_substrate`, `eps_above`, `eps_below`, `transverse_periods`,
`cells_per_pitch`, `cells_substrate`, `cells_above`, `cells_below`,
`ground_thickness_m`, `cells_grid`. All are required. SI geometry and positive
relative permittivities exclude booleans; six counts are strict integers.
Ground thickness must be positive and less than backside depth. Missing/extra
keys, duplicate keys, unsupported versions, alternate units, nonfinite values
and off-grid widths are rejected. Four vertical counts remain independent.

Canonicalization uses the original scalar/alignment/uncut-node/tet/finite-volume
and top-clearance checks without creating a mesh or solving a field. Inputs are
not reduced or inferred; dictionaries are detached, JSON sorted and finite.
`analyze(max_evaluations=1)` accepts integer1..10000 and performs one field solve.
The [common executor](execution.md) retains its existing2..10000 range; passing2
still performs one solve. A larger budget does not request refinement.

```python
from sipi.execution import normalize_saved, execute_saved

assert normalize_saved(saved) == saved
output = execute_saved(saved, max_evaluations=2)
assert output['status'] == 'complete'
assert output['result'] == result.to_dict()
assert not output['result']['fields_included']
```

Replay verifies exact result/cell/field types and inputs, uncut and remaining
node/tet counts, electrode counts, resolved widths/edge indices, metal/dielectric
volumes, material/field shapes and the original volume-error limit. After index
and finite-coordinate checks it verifies extents, complete coordinate-defined
ground/trace labels, absence of unused nodes and the three dielectric regions.
It does not generate a second mesh. Original field failures propagate.

Compact common output omits arrays. Direct results can include mesh, materials
and1V potentials with `to_dict(include_fields=True)`. Expanded results are not
input documents. File access belongs to callers; the engine performs no implicit
file writes. Existing thin-grid and other saved schemas remain distinct.

Tests replay all field values exactly for partial/solid grids, a wider domain,
nonuniform vertical layers and roundoff-aligned widths. All keys, units, counts,
geometry/resource budgets, copies, one-solve accounting,37 result/geometry/
material corruptions, old kinds and original errors are checked. Physical
independent-field, analytic and refinement checks remain in the original suite
and run alongside this adapter. No numerical gate or physical solver changes.

The original changing-mesh thin-limit failure and its qualified common-spacing
comparison remain documented in the physical API. Saved replay does not certify
arbitrary-remeshing monotonicity, physical accuracy or open boundaries. No line
RLGC, return inductance, frequency, measurement, application or platform support
is added. There is no new dependency.
