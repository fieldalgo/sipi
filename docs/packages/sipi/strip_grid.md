# Bounded thin trace above a square ground grid

**English** | [한국어](../../locales/ko/pages/packages/sipi/strip_grid.md)

`strip_grid_cell` prepares a conforming tetrahedral cell and
`extract_strip_grid_capacitance` solves its **total static C in farads** using
the shared [3D capacitance extractor](capacitance3d.md). `StripGridCell` and
`StripGridCapacitance` retain the geometry, dielectric values and field result.
This extends the [broad-plate reference cell](grid_plate.md) to a finite-width
thin trace and three dielectric regions. It does not infer per-length RLGC,
characteristic impedance, return-current inductance, propagation or radiation.

```python
from sipi import strip_grid_cell

inputs = dict(pitch=1e-3, grid_width=.5e-3, trace_width=.5e-3,
              height=.5e-3, top_clearance=1e-3, backside_depth=1e-3,
              eps_substrate=3.8, eps_above=1., eps_below=1.,
              transverse_periods=3, cells_per_pitch=4,
              cells_substrate=2, cells_above=4, cells_below=4)
cell = strip_grid_cell(**inputs)
mesh = cell.to_mesh()  # detached shared Mesh3D; electrode node sets stay explicit
assert cell.relative_permittivity.shape == (len(cell.tets),)
```

The x extent is one pitch p, and y spans M pitches, from0 to M*p. M is odd.
The zero-thickness ground grid lies at z=0: strips of width g intersect on
integer-pitch x/y lines. A zero-thickness trace at z=h runs across all x and is
centred at y=M*p/2 with width w. The trace is driven to1V and grid to0V.
The dielectric extends down to z=-backside_depth and up to h+top_clearance.
Below0, between0..h and aboveh use eps_below, eps_substrate and eps_above,
respectively. Interfaces are exactly aligned to the mesh.

All unprescribed exterior faces are insulating. The x ends lie on grid-centre
reflection planes. Transverse sides, top and bottom are finite chosen boundaries;
they are not automatically open space or periodic wave ports. The transverse
extent and both vertical clearances must be assessed separately from mesh size.
No finite conductor thickness, oblique trace, offset trace or varying pitch is
inferred. A successful solve is not a full interconnect model or measurement
validation.

```python
from sipi import extract_strip_grid_capacitance

result = extract_strip_grid_capacitance(**inputs)
assert result.capacitance_f > 0
compact = result.to_dict()
assert compact['stored_energy_j_at_one_volt'] == .5*result.field.energy_C[0, 0]
assert not compact['fields_included']
expanded = result.to_dict(include_fields=True)
assert len(expanded['potential_v_at_one_volt']) == len(result.cell.nodes)
```

All fourteen inputs are required. Dimensions and relative permittivities are
finite positive real scalars, excluding booleans. Require grid_width<=pitch and
trace_width<=M*pitch. M is an odd integer1..9; cells_per_pitch is even4..32.
Each vertical region has an independent integer1..128 cell count. The top
coordinate must remain finite and strictly above h at floating-point precision.
Both half-widths must coincide with lateral mesh nodes within relative1e-12
roundoff. Off-grid geometry is rejected rather than rounded as a modeling
approximation; requested and resolved widths are retained separately.

Before mesh allocation, require at most100000 nodes and500000 tetrahedra and
finite positive box volume. Actual tetrahedron volumes must be finite/positive
and sum to the box volume within relative1e-12. Explicit electrode planes and
piecewise dielectric assignments are preserved. These resource limits do not
establish numerical accuracy; very small representable geometry may still fail
field assembly or solving.

`cell.inputs` returns a fresh14-key SI snapshot. Nodes, tetrahedra, trace/ground
node sets and `relative_permittivity` are copied and read-only. `to_mesh()`
returns a detached shared Mesh3D with no inferred face tags; pass electrode sets
and per-tetrahedron permittivity explicitly to other solvers. `to_dict()` is
compact; `include_mesh=True` adds those arrays. Direct dataclass construction is
not a substitute for factory validation.

The result exposes `capacitance_f`, original raw energy/charge/Maxwell diagnostics
and the `Capacitance3D` field. Serialization reports energy capacitance in F,
stored energy at1V as half that value in J, and ground charge at1V in C.
`include_fields=True` includes mesh/materials and the1V potential. Compact output
is the default. This API adds no versioned saved-input schema. Original field
gates at1e-8 remain unchanged; exact result identity, shapes, finite positive
capacitance/energy, negative ground charge and prescribed potentials are checked.

Verification in `tests/sipi/test_strip_grid.py` includes three solid/full-width
parallel-plate limits, C=eps0*eps_substrate*p*(M*p)/h within relative1e-11, nested
grid/trace width monotonicity and length/all-region-permittivity scaling1e-10.
Four independent scikit-fem12.0.2 P1 weak-form cases use the same explicit mesh,
coordinate-based material assignment and separate assembly/solve; C, energy and
ground charge must agree within relative1e-10. This is independent field assembly,
not independent meshing. The homogeneous full-width bridge to the old broad-plate
API is recorded separately from independent evidence.

For p=1mm, g=w=.5p, h=.5p, substrate eps3.8 and exterior eps1, the registered
successive-change checks are:

| Change | Held fixed | Final change in pilot | Required gate |
|---|---|---|---|
| Mesh8/16/24 cells per pitch | M1, top/back clearances p, vertical spacing p/n |1.2840%|decreasing and <3%|
| Transverse M3/5/7 | n8, top/back p |0.0569%|decreasing and <1%|
| Top clearance .5p/p/2p | n8, M5, backside p, fixed spacing |0.6739%|decreasing and <1%|
| Backside .5p/p/2p | n8, M5, top p, fixed spacing |0.000393%|decreasing and <0.1%|

These are successive changes for separate sequences, not bounds on true error
or a combined open-boundary limit. Reassess other geometries/materials and coupled
refinement. Strict inputs, preallocation budgets, layer volumes, electrode labels,
readonly copies, field corruption and original solver failures are also tested.
The BSD-3-Clause reference remains test-only; no new dependency is introduced.
