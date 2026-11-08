# Saved unequal-width trace and ground-grid volume inputs

**English** | [한국어](../../locales/ko/pages/packages/sipi/asymmetric_volume_grid_pair_document.md)

`AsymmetricVolumeGridPairCapacitanceDocument` stores all twenty inputs of the
[finite trace and ground-grid cell](asymmetric_volume_grid_pair.md) in
`sipi.asymmetric-volume-grid-pair-capacitance/1`. The model has two finite traces and a finite PEC ground grid, three real
dielectric regions and explicit insulating boundaries. It computes total static
2×2 Maxwell C[F]; geometry, material and qualified refinement limits remain unchanged.

```python
from sipi import AsymmetricVolumeGridPairCapacitanceDocument

document = AsymmetricVolumeGridPairCapacitanceDocument(
    pitch=1e-3, grid_width=.5e-3, left_trace_width=.5e-3, right_trace_width=1e-3, trace_gap=.5e-3, height=.5e-3,
    top_clearance=1e-3, backside_depth=1e-3, ground_thickness=.25e-3, trace_thickness=.25e-3,
    eps_substrate=3.8, eps_above=1., eps_below=1.,
    transverse_periods=3, cells_per_pitch=4, cells_substrate=2,
    cells_above=4, cells_below=3, cells_grid=1, cells_trace=1)
saved = document.dumps()
reloaded = AsymmetricVolumeGridPairCapacitanceDocument.loads(saved)
assert reloaded.dumps() == saved
result = reloaded.analyze(max_evaluations=1)
assert result.capacitance_matrix_f.shape == (2, 2)
assert result.field.names == ('left', 'right')
```

The root has exactly twenty-one keys: `schema`, `pitch_m`, `grid_width_m`,
`left_trace_width_m`, `right_trace_width_m`, `height_m`, `top_clearance_m`, `backside_depth_m`,
`eps_substrate`, `eps_above`, `eps_below`, `transverse_periods`,
`cells_per_pitch`, `cells_substrate`, `cells_above`, `cells_below`,
`ground_thickness_m`, `cells_grid`, `trace_thickness_m`, `cells_trace`, `trace_gap_m`. All are required. SI geometry and positive
relative permittivities exclude booleans; seven counts are strict integers.
Ground thickness must be positive and less than backside depth. Missing/extra
keys, duplicate keys, unsupported versions, alternate units, nonfinite values
and off-grid widths/gap are rejected. Positive gap and2*max(left_width,right_width)+gap<=M*p are required. Five vertical counts remain independent.

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
node/tet counts, separate left/right electrode counts, resolved widths/gap and edge indices, metal/dielectric
volumes, material/field shapes and the original volume-error limit. After index
and finite-coordinate checks it verifies extents, complete coordinate-defined
ground/left/right labels, absence of unused nodes and the three dielectric regions.
It does not generate a second mesh. Original field failures propagate.

Compact common output omits arrays. Direct results can include mesh, materials
and the N×2 basis potentials with `to_dict(include_fields=True)`. Expanded results are not
input documents. File access belongs to callers; the engine performs no implicit
file writes. The existing equal-width pair, thin-grid and other saved schemas remain distinct.
Previous92 canonical documents retain exact source/installed hashes. An actual
fixture preserves exact registry equality:93schemas/37templates at this addition.

Tests replay all field values exactly for partial/solid grids, a wider domain,
nonuniform vertical layers, roundoff-aligned widths/gap and traces touching
either or both transverse walls, and the equal-width limit. All keys, units, counts,
geometry/resource budgets, copies, one-solve accounting,46 result/geometry/
material corruptions and three requested-width substitutions, old kinds and original errors are checked. Physical
independent-field, analytic and refinement checks remain in the original suite
and run alongside this adapter. No numerical gate or physical solver changes.

Original left/right widths are preserved independently; no width broadcast,
equal-width schema conversion or material inference is performed. Separate
left/right edge counts and one-sided wall contacts are checked explicitly.
The physical API retains raw left/right Maxwell matrices without imposing
finite-mesh mirror symmetry. Both trace top and its clearance must remain
representable. Prescribed common/differential excitations are voltage vectors,
not automatically line modes. Saved replay does not certify
arbitrary-remeshing monotonicity, physical accuracy or open boundaries. No line
RLGC, return inductance, frequency, measurement, application or platform support
is added. There is no new dependency.
