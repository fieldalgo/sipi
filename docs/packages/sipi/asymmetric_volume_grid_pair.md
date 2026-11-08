# Unequal-width finite traces over a ground-grid volume

**English** | [한국어](../../locales/ko/pages/packages/sipi/asymmetric_volume_grid_pair.md)

`asymmetric_volume_grid_pair_cell` and `extract_asymmetric_volume_grid_pair_capacitance` prepare and
solve two independent-width rectangular PEC traces over a square PEC ground grid, with both
metal thicknesses explicit. `AsymmetricVolumeGridPairCell` and `AsymmetricVolumeGridPairCapacitance`
retain geometry and **total bounded-cell Maxwell capacitance C[F]**, in
`left, right` order. The [equal-width pair API](volume_grid_pair.md) and its saved inputs remain unchanged.

```python
from sipi import asymmetric_volume_grid_pair_cell

inputs = dict(pitch=1e-3, grid_width=.5e-3, left_trace_width=.5e-3, right_trace_width=1e-3,
              trace_gap=.5e-3, height=.5e-3,
              top_clearance=1e-3, backside_depth=1e-3,
              ground_thickness=.125e-3, trace_thickness=.125e-3,
              eps_substrate=3.8, eps_above=1., eps_below=1.,
              transverse_periods=3, cells_per_pitch=4, cells_substrate=2,
              cells_above=4, cells_below=4, cells_grid=1, cells_trace=1)
cell = asymmetric_volume_grid_pair_cell(**inputs)
assert len(cell.inputs) == 20
assert cell.trace_metal_volume > 0 and cell.ground_metal_volume > 0
```

The box spans x=0..p and y=0..M*p, where M is odd. Traces run along x, with independent widths wL/wR extending outward from
a positive gap s centred about y=M*p/2.
Their y intervals are [M*p/2-s/2-wL, M*p/2-s/2] and
[M*p/2+s/2, M*p/2+s/2+wR]. Both occupy z=h..h+ts. Grid bars of width g cross
on integer-pitch lines and occupy -tg..0. Height h is the substrate gap;
bottom is -d and top h+ts+a. Relative eps values are explicit below0,0..h,
and aboveh outside metal. Unprescribed exterior faces are insulating/reflection
boundaries; a finite box does not automatically represent open space.

All twenty inputs are required. Dimensions and three eps values are finite
positive real scalars excluding booleans. Require0<tg<d,g<=p,2*max(wL,wR)+s<=M*p,
odd M1..9, even pitch cells n4..32. Half widths and half gap align with p/n
within relative1e-12 roundoff; requested and resolved values are retained.
Five explicit vertical integer counts1..128 cover -d..-tg,-tg..0,0..h,
h..h+ts,h+ts..h+ts+a. Trace top and top clearance must remain representable.
Uncut100000-node/500000-tetrahedron budgets apply before allocation.

Both traces and ground metal are removed from the dielectric mesh, unused
nodes are dropped, and indices remapped. Positive tetrahedron volumes must
match box minus both metal volumes within relative1e-12. Three material
regions and disjoint left/right/ground surfaces remain explicit. The
[partitioned extractor](partitioned_capacitance.md) checks anchored components
and a globally ground-referenced electrode network. It does not solve unknown
floating conductor voltages.

```python
import numpy as np
from sipi import extract_asymmetric_volume_grid_pair_capacitance

result = extract_asymmetric_volume_grid_pair_capacitance(**inputs)
assert result.field.names == ('left', 'right')
c = result.capacitance_matrix_f
assert c.shape == (2, 2) and np.min(np.linalg.eigvalsh(c)) > 0
voltage = np.array([1., -1.])
stored_energy_j = .5 * voltage @ result.field.energy_C @ voltage
assert stored_energy_j > 0
assert not result.to_dict()['fields_included']
assert len(result.to_dict(include_fields=True)['potential_v_per_basis']) == len(cell.nodes)
```

Column j excites trace j to1V while the other trace and ground are0V. Maxwell
C maps trace voltages to charges; its off-diagonal entries are negative.
`energy_C` gives quadratic electrostatic energy; `ground_charge` contains the
two ground-charge basis responses. Common or differential voltage vectors may
be applied to these matrices. They are not automatically transmission-line modes.

Geometry/material/node arrays are detached read-only copies; `to_mesh()` is a
detached Mesh3D without inferred tags. Compact cell output includes resolved
left/right width, gap and separate edge indices, uncut/removed counts, ground metal volume, total
trace metal volume and dielectric volume. `include_mesh=True` adds arrays.
Result `include_fields=True` adds the N×2 basis potentials. The capacitance
property returns a detached matrix. Direct dataclass construction does not
replace factory validation. The existing raw1e-8 gates, exact names/shapes,
positive-definite C/energy, Maxwell signs and prescribed potentials are checked.
A separate strict saved-input adapter is now available.

Four independent scikit-fem12.0.2 P1 weak forms compare the complete C, energy,
ground-charge and potential matrices within relative1e-10. Coordinate material
assignment, assembly and solutions are independent; the cleaned mesh is shared.
Analytical invariants include length/whole-eps scaling, electrode-order
permutation, quadratic energy and solid-ground backside screening. Geometry
tests cover both metal volumes, surface nodes, material partitions, unused-node
removal and traces reaching the transverse box walls. Unequal self-capacitances remain raw; mirror symmetry is not imposed or
repaired. Electrode-order permutation is a relabeling of the same mesh, not
a claim of exact mirror-mesh equivalence. Three equal-width cases match the
original geometry and all C/energy/ground/potential arrays exactly.

Registered pilot: p=1mm,g=wL=s=.5p,wR=.75p,h=.5p,tg=ts=.125p,
substrate3.8 and exterior1. Mesh n8/16/24 at M3,top/back .5p gives Frobenius
successive changes4.1330% then1.2633% (<5%). At n8,top/back p,M3/5/7 gives
3.6459% then0.2533% (<1%). At M5,n8,top .5p/p/2p gives2.0341% then0.6593%
(<1%); backside .5p/p/2p gives0.0003210% then0.00004344% (<0.1%). Other extents
stay p; vertical counts preserve p/n spacing. Each sequence changes one mesh
or exterior parameter. These are successive changes, not true-error bounds
or a combined open-boundary limit. Other geometries need their own assessment;
no arbitrary-remeshing thickness monotonicity is promised.

This is a bounded perfect-conductor electrostatic cell. No finite conductivity,
roughness, return-current inductance, line impedance/RLGC, frequency validity,
propagation, radiation or measured accuracy is inferred. Shared solvers and
existing APIs/schemas are unchanged; no new dependency or app/platform support.


[Saved independent-width volume inputs](asymmetric_volume_grid_pair_document.md) preserve both widths, resource budgets and full geometry identity.
