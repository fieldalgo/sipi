# Bounded thin-grid and broad-plate capacitance

`grid_plate_cell` prepares a conforming static reference cell without solving
a field. `extract_grid_plate_capacitance` takes the same explicit inputs and
returns total capacitance in **farads**, using the existing
[bounded 3D P1 extractor](capacitance3d.md). This is a square thin ground grid
below a broad PEC plate, not a transmission-line or return-current model.

The homogeneous dielectric fills a square pitch-by-pitch cell. At z=0, the
grounded zero-thickness sheet is the union of strips centred on the cell's
four side edges, each with full periodic width `width`. The complete top
face z=`height` is driven at1V. The bottom z=−`backside_depth` and lateral
faces are insulating (zero normal displacement). Lateral reflection symmetry
assumes the uniform broad plate and symmetric grid. The finite bottom is not
an automatically open boundary; inspect backside-depth convergence separately.

All eight inputs are required. `pitch`, `width`, `height`, `backside_depth`
are finite positive metres, `width<=pitch`, and `eps_r` is a finite positive
real constant. `cells_xy` is an even integer4..64. `cells_above` is integer1..64
and `cells_below` integer1..128; both vertical intervals are explicit.
Each half strip width must be an integer number of lateral cells within
relative1e-12 roundoff. Off-grid widths are rejected. Both requested and
resolved widths are retained; this roundoff rule is not a geometric accuracy
allowance. No input or refinement count is inferred.

Before mesh allocation, reject more than100000 nodes or500000 tetrahedra
and nonrepresentable total volume. Shared `galerkin.box_mesh` connectivity
is mapped to the two vertical intervals without introducing a new solver or
mesher. Prescribed planes remain exact, every tetrahedron has positive finite
volume, and total mesh volume agrees with pitch²*(height+backside_depth)
within relative1e-12. These bounds do not guarantee accuracy or runtime.

```python
from sipi import grid_plate_cell, extract_grid_plate_capacitance

inputs = dict(pitch=1e-3, width=.25e-3, height=.5e-3, backside_depth=1e-3,
    eps_r=3.8, cells_xy=8, cells_above=4, cells_below=8)
cell = grid_plate_cell(**inputs)
assert cell.resolved_width == inputs['width']
assert cell.nodes.shape == (1053, 3)
assert cell.tets.shape == (4608, 4)
assert cell.to_dict()['input']['width_m'] == inputs['width']
```

```python
result = extract_grid_plate_capacitance(**inputs)
assert 0 < result.capacitance_f < 6.73e-14
summary = result.to_dict()
assert not summary['fields_included']
assert summary['stored_energy_j_at_one_volt'] > 0
assert summary['ground_charge_c_at_one_volt'] < 0
field = result.to_dict(include_fields=True)
assert len(field['potential_v_at_one_volt']) == len(result.cell.nodes)
```

`GridPlateCell` copies its node/tetrahedron/electrode arrays and exposes them
read-only; `inputs` returns a fresh SI snapshot. `to_mesh()` creates a detached
shared `Mesh3D` without exterior tags; use the explicit `plate_nodes` and
`ground_nodes` when passing it to an extractor. Geometry output is compact
unless `to_dict(include_mesh=True)` is requested.

`GridPlateCapacitance.cell` retains the geometry and `.field` retains the
original `Capacitance3D` result. Extraction uses plate1V/grid0V and keeps the
raw energy/charge/Maxwell checks at1e-8. It checks result type, electrode name,
tetrahedron count, all field shapes, finite diagnostics and prescribed
potentials. Negative ground charge is retained. `capacitance_f` is the cell's
single Maxwell coefficient. At1V the stored energy is half the energy
capacitance; it is not the entire C value in joules. `to_dict(include_fields=True)`
adds mesh and potential samples. This serialization is not a saved-input schema.

Validation uses the solid-sheet analytic limit eps0*eps_r*pitch²/height at
relative1e-11, nested-width monotonicity and solid upper bound, length and
permittivity scaling at1e-10, and an independent scikit-fem12.0.2 P1 weak form
on the **same** explicit mesh. The latter compares plate charge, ground charge
and energy at1e-10; it verifies independent assembly/solution, not meshing.

For the specific pitch1mm/width.25mm/height.5mm/eps3.8 fixture, lateral
8/16/32 refinement (matching vertical spacing) reduces successive C changes
from about1.93% to1.07%, with the final change below1.5%. This is not an error
bound. Increasing the backside from one to two pitches at fixed spacing
changes C by less than1e-3 relative. Three additional independent fixtures,
including unequal vertical spacing, exercise other permitted shapes.
Strict scalar/count/alignment/budget/copy/result-identity and original-failure
tests accompany the numerical checks. Input-specific refinement remains required.

Finite trace or sheet thickness, an actual signal trace, return-current L,
RLGC, loss, wave ports, radiation, frequency validity, general flex geometry
and measured accuracy are outside this contract. A static cell C cannot be
substituted for a validated grid-return transmission-line model.

[Saved bounded grid/plate inputs](grid_plate_document.md) preserve SI geometry, explicit cell counts and one static field evaluation.
