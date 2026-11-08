# Capacitance across partitioned dielectric domains

**English** | [한국어](../../locales/ko/pages/packages/sipi/partitioned_capacitance.md)

`extract_partitioned_capacitance_3d(mesh, *, eps_r=1., conductors, ground)`
returns the existing `Capacitance3D` total Maxwell C[F] result for explicitly
separated dielectric domains. A finite conductor can separate dielectric above
and below it. The exterior region may touch only that signal electrode, whose
prescribed voltage still fixes its field. This API supports such domains when
the complete electrode network has a global ground reference.

The original [extractor and saved input](capacitance3d.md) retain their stricter
requirement that every connected mesh component contains ground. The new API
is explicit; it does not alter existing saved schemas or infer conductor aliases.

```python
import numpy as np
from galerkin.mesh3d import Mesh3D, box_mesh

lower = box_mesh(1e-3, .8e-3, .4e-3, 2, 2, 2)
upper = box_mesh(1e-3, .8e-3, .3e-3, 2, 2, 2)
upper.nodes[:, 2] += .8e-3
offset = lower.num_nodes
mesh = Mesh3D(np.vstack([lower.nodes, upper.nodes]),
              np.vstack([lower.tets, upper.tets + offset]))
signal = np.r_[lower.boundary['z1'], offset + upper.boundary['z0']]
ground = lower.boundary['z0']
relative = np.r_[np.full(lower.num_tets, 3.8), np.ones(upper.num_tets)]
```

Here the lower dielectric lies between ground and signal; the upper dielectric
touches only the same prescribed signal. The gap represents excluded metal;
there are no fictitious dielectric tetrahedra inside it. The caller explicitly
groups the two signal surfaces. Unprescribed faces are insulating, so the upper
domain has constant signal potential and contributes zero energy in the exact
solution. This is a bounded geometry, not an automatic open-space boundary.

```python
from sipi import extract_partitioned_capacitance_3d
from sipi.constants import epsilon_0

result = extract_partitioned_capacitance_3d(
    mesh, eps_r=relative, conductors={'signal': signal}, ground=ground)
exact = epsilon_0 * 3.8 * 1e-3 * .8e-3 / .4e-3
assert abs(result.C[0, 0] / exact - 1) < 1e-11
assert np.max(abs(result.potentials[offset:, 0] - 1)) < 1e-10
assert not result.C.flags.writeable
```

Two structural conditions are checked before assembly: every connected mesh
component contains at least one prescribed electrode node, and every named
signal reaches ground in the electrode/component incidence graph. Graph edges
mean a shared dielectric region, not an electrical short. Signal-only and
ground-only components are valid when their electrode is referenced elsewhere.
An unanchored dielectric or globally isolated signal group is rejected.

For positive permittivity, zero field energy requires constant potential in
each connected domain. The incidence condition propagates that constant to
ground0V, making the global signal capacitance positive definite. Single-electrode
domains have a known constant field, so they do not introduce an unknown gauge.
No floating-electrode voltage, charge constraint, alias or geometry is inferred.

Inputs retain the original conforming positive-tetrahedron, finite real node,
nonmanifold/duplicate/unused-node, positive scalar or per-tet relative-permittivity,
nonempty disjoint electrode and ordered-name checks. Mesh coordinates are metres.
Input arrays are copied; result arrays are read-only. Column j drives signal j
to1V, other signals and ground to0V. The result contains C, energy-derived C,
potentials and ground charge for those unit drives.

The numerical assembly/solve/charge/energy body is shared byte-for-byte with the
original extractor. Raw residual, charge balance, energy agreement, symmetry,
Maxwell sign and positive-eigenvalue gates are unchanged; no symmetrization,
clipping or pseudoinverse is introduced. No new input schema is added here.

Tests include nine analytic plate/capacitor-network discretizations within1e-11,
including a layered plate with series-dielectric capacitance. Single-electrode
domain potentials agree with1V/0V within1e-10. Uniform cases use n2/3/4 and the
layered case n2/4/6 with an aligned material interface; these exactly represented
piecewise-linear fields test discretization invariance, not arbitrary-field
convergence. Length/permittivity scaling, electrode permutation and mesh/component
renumbering use1e-10. Three independent scikit-fem12.0.2 P1 weak forms on the same
mesh compare C, energy, ground charge and potential within1e-10 using separate
coordinate material assignment and assembly/solve.

The boxes and insulating exterior are explicitly fixed, so these checks do not
establish an open-boundary limit. Other geometries need mesh and boundary
convergence. Existing grounded cases have exact output parity;48 pre-change
legacy snapshots also retain exact array/diagnostic hashes. Input failures,
unreferenced groups, original strict API/JSON behavior, detached outputs and
operator/solver/raw-gate failures are covered. The reference remains test-only.
This API adds no line RLGC, inductance, loss, propagation, radiation, measurement
accuracy, platform support or dependency.
