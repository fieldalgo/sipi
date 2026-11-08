# Thin trace over a finite-thickness ground grid

**English** | [한국어](../../locales/ko/pages/packages/sipi/thick_grid_strip.md)

`thick_grid_strip_cell` prepares a bounded tetrahedral geometry;
`extract_thick_grid_strip_capacitance` computes its **total static C in farads**.
`ThickGridStripCell` and `ThickGridStripCapacitance` retain the geometry and field.
The [thin-grid model](strip_grid.md) remains unchanged. Both reuse the shared
[3D capacitance extractor](capacitance3d.md), with three real dielectric regions.

```python
from sipi import thick_grid_strip_cell

inputs = dict(pitch=1e-3, grid_width=.5e-3, trace_width=.5e-3,
              height=.5e-3, top_clearance=1e-3, backside_depth=1e-3,
              ground_thickness=.25e-3, eps_substrate=3.8, eps_above=1., eps_below=1.,
              transverse_periods=3, cells_per_pitch=4, cells_substrate=2,
              cells_above=4, cells_below=3, cells_grid=1)
cell = thick_grid_strip_cell(**inputs)
assert cell.to_dict()['removed_num_tets'] > 0
assert cell.relative_permittivity.shape == (len(cell.tets),)
```

x spans one pitch p; y spans odd M pitches. Ground bars of width g intersect
along integer-pitch x/y lines and occupy -t<=z<=0 at0V. A centred thin trace of
width w runs across x at z=h and1V. The bottom is -d, top h+a. Dielectric values
are eps_below for z<0, eps_substrate for0<z<h, eps_above for z>h. All other
faces are insulating/reflection boundaries, not automatic open space or wave ports.

All sixteen inputs are required: finite positive SI dimensions and relative
permittivities;0<t<d, g<=p, w<=M*p; odd M1..9; even pitch cells4..32. Each of
the four vertical segments has an independent integer count1..128: `cells_below`
for -d..-t, `cells_grid` for -t..0, `cells_substrate` for0..h, `cells_above` for
h..h+a. Booleans are rejected. Both lateral half-widths must align within
relative1e-12 roundoff; requested and resolved widths remain separate.

The uncut mesh must fit100000 nodes and500000 tetrahedra before allocation.
Finite positive box volume and a representable top clearance are required.
PEC-volume tetrahedra are removed, unused nodes are dropped and indices remapped;
metal is not filled with a fictitious dielectric. Every retained tetrahedron
has positive volume, and the sum matches box minus metal within relative1e-12.
Surface ground nodes are explicit. A solid ground sheet separates two dielectric
components, each grounded; the field extractor's component checks are unchanged.

```python
from sipi import extract_thick_grid_strip_capacitance

result = extract_thick_grid_strip_capacitance(**inputs)
assert result.capacitance_f > 0
compact = result.to_dict()
assert compact['stored_energy_j_at_one_volt'] == .5*result.field.energy_C[0, 0]
assert not compact['fields_included']
expanded = result.to_dict(include_fields=True)
assert len(expanded['potential_v_at_one_volt']) == len(result.cell.nodes)
```

`cell.inputs` returns a fresh16-key snapshot. Geometry, electrodes and per-tet
permittivities are detached and read-only; `to_mesh()` returns a detached Mesh3D
without inferred face tags. Compact output includes uncut/removed counts and
metal/dielectric volumes in m³. `include_mesh=True` adds arrays; result
`include_fields=True` also adds the1V potential. Direct dataclass construction
does not replace factory validation. Result identity, shapes, finite positive
C/energy, negative ground charge and prescribed potentials are checked alongside
the unchanged raw field gates1e-8. No versioned saved-input adapter is added here.

Tests cover three solid/full-trace analytic limits C=eps0*eps_substrate*p²M/h
within1e-11; width monotonicity; length and all-eps scaling1e-10; disconnected
grounded components; surface labels, volume/material partitions, node cleanup,
strict inputs/budgets, copies and original failures. Four independent scikit-fem
12.0.2 P1 comparisons use the same explicit cleaned mesh with separate coordinate
material assignment, assembly and solve; C/energy/ground charge agree within
1e-10. They validate field assembly, not independent mesh generation or measurement.

Registered separate refinement at p=1mm, g=w=.5p, h=.5p, t=.25p, substrate3.8
and exterior1 gives final changes: mesh8/16/24 **1.2373%** (<3%), transverse
M3/5/7 **0.0568%** (<1%), top .5p/p/2p **0.6738%** (<1%), backside .5p/p/2p
**0.0000123%** (<0.1%). Each sequence decreases; exterior sequences keep p/8
spacing and M5 for top/back. Mesh uses M1 and top/back p. These are successive
changes, not true-error bounds or a combined open-boundary limit.

Thickness comparisons require a common finite-element space. The initial pilot
used a thin8-layer baseline and independently remeshed thick8+2-layer cases;
three of four differences were negative, reaching -0.01511%. That monotonicity
check failed and is retained as a limitation, not relabeled as passing. Solving
each matching mesh without metal thickness separates a positive metal effect
from a larger negative mesh-baseline shift.

A qualified comparison keeps below spacing p/32 and the same thin32-layer
baseline. For t/p=.25,.125,.0625,.03125, use `(cells_below,cells_grid)` =
`(24,8),(28,4),(30,2),(31,1)`, n8/substrate4/above8. Relative differences decrease
from0.05638% to0.02376%, remain nonnegative within1e-10 and end below1%.
No monotonicity across arbitrary remeshing is promised; assess other geometries
and discretizations separately. The original solver and numerical gates are unchanged.

This bounded electrostatic model does not infer finite trace thickness,
return-current inductance, per-length RLGC, impedance, conductor loss, propagation,
radiation or measured accuracy. The reference tool stays test-only; no runtime
dependency, website or executable change is included.
