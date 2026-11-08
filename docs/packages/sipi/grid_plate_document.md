# Saved bounded grid/plate capacitance inputs

`GridPlateCapacitanceDocument` stores the explicit
[bounded thin-grid/broad-plate cell](grid_plate.md) as
`sipi.grid-plate-capacitance/1`. Total capacitance is in farads. This does not
convert an arbitrary explicit 3D mesh, infer an open boundary or add a line
propagation model.

Exactly nine root keys are required: `schema`, `pitch_m`, `width_m`,
`height_m`, `backside_depth_m`, `eps_r`, `cells_xy`, `cells_above`, `cells_below`.
The four lengths are metres; permittivity is a real homogeneous constant.
Both requested width and its roundoff-only resolved mesh width remain in the
physical result. No thickness, frequency, anisotropy or extra unit conversion
is inferred. Missing/extra/duplicate keys, unsupported versions, nonfinite
JSON, Boolean numbers, off-grid widths and wrong integer counts are rejected.

Normalization validates original scalar/alignment/finite-volume and mesh
node/tetrahedron budgets without generating a mesh or solving a field. It
copies canonical inputs and leaves all geometry and counts unchanged.

```python
from sipi import GridPlateCapacitanceDocument
from sipi.execution import normalize_saved, execute_saved

document = GridPlateCapacitanceDocument(pitch=1e-3, width=.5e-3,
    height=.5e-3, backside_depth=1e-3, eps_r=3.8,
    cells_xy=4, cells_above=2, cells_below=4)
text = document.dumps()
assert normalize_saved(text) == text
assert document.to_dict()['schema'] == 'sipi.grid-plate-capacitance/1'
assert len(document.to_dict()) == 9
```

```python
loaded = GridPlateCapacitanceDocument.loads(text)
result = loaded.analyze(max_evaluations=1)
# Common execution retains its existing minimum budget of two.
out = execute_saved(text, max_evaluations=2)
assert out['result'] == result.to_dict()
assert out['input'] == document.to_dict()
assert not out['result']['fields_included']
assert result.to_dict(include_fields=True)['fields_included']
```

One analysis performs one static field evaluation. The document's direct
`analyze` accepts integer `max_evaluations=1..10000` (default1). Common
`execute_saved` retains its existing integer2..10000 budget contract, so use
at least2 there; it still performs exactly one field solve for this input.
These budgets do not change lateral/upper/lower cell counts or replace the
physical node/tetrahedron limits. Input-byte and unrelated-diagnostic checks
also occur before field work in common execution.

Replay requires exact result and cell types, identical canonical inputs,
resolved width/edge metadata, expected node/tetrahedron/electrode counts and
all C/energy/ground-charge/potential shapes. Common execution returns the
compact physical result. Direct results can include mesh and fields through
`to_dict(include_fields=True)`. Original field failures are propagated rather
than turned into partial success.

Tests replay partial/solid/nonuniform-vertical/roundoff-aligned cells exactly,
including full geometry and potential arrays. Strict keys/units/scalars,
pre-mesh resource and scale rejection, copies, one-solve budgeting, identity
corruption and original failures are covered. The physical API's independent
weak-form, analytic and convergence tests remain separate evidence. Old
explicit-mesh/line/wave schemas do not accept this geometry object implicitly.
Storage support does not establish line RLGC, frequency validity, measurement
accuracy, app integration or platform support.

[Common execution](execution.md) · [Physical API](grid_plate.md)
