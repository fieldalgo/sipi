# Finite-thickness trace and ground-grid volumes

**English** | [한국어](../../locales/ko/pages/packages/sipi/volume_grid_strip.md)

`volume_grid_strip_cell` and `extract_volume_grid_strip_capacitance` prepare and
solve a bounded static cell containing two finite PEC volumes: a rectangular
trace and a square ground grid. `VolumeGridStripCell` and
`VolumeGridStripCapacitance` retain geometry/materials and **total C[F]**.
The [thin trace over thick ground](thick_grid_strip.md) remains a separate API.

```python
from sipi import volume_grid_strip_cell

inputs = dict(pitch=1e-3, grid_width=.5e-3, trace_width=.5e-3,
              height=.5e-3, top_clearance=1e-3, backside_depth=1e-3,
              ground_thickness=.25e-3, trace_thickness=.25e-3,
              eps_substrate=3.8, eps_above=1., eps_below=1.,
              transverse_periods=3, cells_per_pitch=4, cells_substrate=2,
              cells_above=4, cells_below=3, cells_grid=1, cells_trace=1)
cell = volume_grid_strip_cell(**inputs)
assert cell.ground_metal_volume > 0 and cell.trace_metal_volume > 0
assert cell.relative_permittivity.shape == (len(cell.tets),)
```

x spans one pitch p; y spans odd M pitches. Ground bars of width g intersect
on integer-pitch x/y lines and occupy -tg..0 at0V. The centred trace of width w
runs across x and occupies h..h+ts at1V. **height h is the dielectric gap**;
the top is h+ts+top_clearance and bottom -backside_depth. Positive real relative
permittivities apply below0, between0..h and aboveh outside the removed metal.
All unprescribed faces are insulating/reflection boundaries. Finite chosen
extents are not automatically open space or wave ports.

All eighteen inputs are required. Dimensions/eps are finite positive real
scalars excluding booleans;0<tg<backside_depth, g<=p, w<=M*p, odd M1..9 and
even pitch cells4..32. Half-widths align within relative1e-12 roundoff and both
requested/resolved widths are retained. Five vertical integer counts1..128 are
explicit: `cells_below` for -d..-tg, `cells_grid` for -tg..0, `cells_substrate`
for0..h, `cells_trace` for h..h+ts, `cells_above` for h+ts..h+ts+a. Trace top
must be finite and strictly above h, with a representable positive top clearance.

Uncut budgets are100000 nodes and500000 tetrahedra before allocation. Positive
finite box volume is required. Both PEC volumes are removed, unused nodes are
dropped and indices remapped. No metal surrogate dielectric is used. Positive
tetrahedron volumes must sum to box minus both metals within relative1e-12.
Electrode surfaces and three material regions are explicit. A full grid and
full-width trace split the dielectric into three components; the upper one
touches only trace and has constant1V. The
[partitioned-domain extractor](partitioned_capacitance.md) checks that every
domain has a prescribed electrode and the global electrode network reaches ground.

```python
from sipi import extract_volume_grid_strip_capacitance

result = extract_volume_grid_strip_capacitance(**inputs)
assert result.capacitance_f > 0
compact = result.to_dict()
assert compact['stored_energy_j_at_one_volt'] == .5*result.field.energy_C[0, 0]
assert not compact['fields_included']
expanded = result.to_dict(include_fields=True)
assert len(expanded['potential_v_at_one_volt']) == len(result.cell.nodes)
```

Inputs are detached18-key snapshots. Geometry, node sets and per-tet materials
are copied and read-only. `to_mesh()` returns a detached Mesh3D without inferred
face tags. Compact serialization includes uncut/removed counts, separate
`ground_metal_volume_m3` and `trace_metal_volume_m3`, dielectric volume and
resolved widths/edge indices. `include_mesh=True` adds arrays; result
`include_fields=True` also adds the1V potential. Direct dataclass construction
does not replace factory validation. Raw field1e-8 gates, result identity,
shapes, finite positive C/energy, negative ground charge and prescribed potentials
are checked. Versioned inputs use the separate [saved-input adapter](volume_grid_strip_document.md).

Verification includes three solid/full-width limits C=eps0*eps_substrate*p²M/h
within1e-11, constant upper/lower potentials within1e-10, nested width monotonicity,
length/all-eps scaling1e-10, both volume/material partitions and electrode
surfaces, node cleanup, disconnected components, strict input/resource guards,
copies and original errors. Four independent scikit-fem12.0.2 P1 weak forms on
the same cleaned mesh compare C/energy/ground within1e-10 using separate
coordinate material assignment and assembly/solve; they are not independent meshes.

For p=1mm,g=w=.5p,h=.5p,tg=ts=.25p,substrate3.8 and exterior1, separate registered
refinements give final changes: mesh8/16/24 **1.0299%** (<3%), transverse M3/5/7
**0.1806%** (<1%), top .5p/p/2p **0.6933%** (<1%), backside .5p/p/2p
**0.00001154%** (<0.1%). Changes decrease in each sequence. Mesh uses M1/top/back p;
exterior studies hold p/8 spacing and top/back studies M5. These are successive
changes, not true-error bounds or a combined open-boundary limit.

The thin-trace comparison fixes the absolute top h+p and above spacing p/128:
n8,substrate4,below6,grid2; the thin-trace reference has128 above cells.
For ts/p=1/16,1/32,1/64,1/128, use trace counts8/4/2/1 and above counts
120/124/126/127, with top_clearance=p-ts. C/Cthin-1 decreases from0.31088% to
0.05165%, remains nonnegative within1e-10 and ends below1%. Keeping an absolute
top and common FE space separates thickness from boundary/remeshing effects.
No arbitrary-remeshing monotonicity is promised; other geometries need assessment.

This is a rectangular perfect-conductor electrostatic model. It does not infer
finite conductivity, roughness, return-current inductance, line RLGC, impedance,
propagation, radiation or measured accuracy. Existing APIs/schemas and shared
solvers remain unchanged; no new dependency, application or platform support.


[Paired finite-volume traces](volume_grid_pair.md) provide a separate two-signal Maxwell capacitance matrix.
