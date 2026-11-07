# Bounded 3D static capacitance

[한국어](../../locales/ko/pages/packages/sipi/capacitance3d.md)

`sipi.capacitance3d.extract_capacitance_3d` computes a Maxwell capacitance
matrix **in farads** in an explicitly supplied tetrahedral dielectric domain.
It reuses galerkin's P1 3D stiffness assembly and a grounded sparse solve.
This is a static field API, not a transmission-line parameter set or a complete
via/transition model. It does not generate geometry, L, R, loss, radiation,
impedance, propagation or S-parameters. It has no saved JSON/UI adapter yet.

```python
from galerkin.mesh3d import box_mesh
from sipi.capacitance3d import extract_capacitance_3d
from sipi.constants import epsilon_0

mesh = box_mesh(.004, .003, .002, 4, 4, 4)  # metres
result = extract_capacitance_3d(
    mesh, eps_r=3.8,
    conductors={"top": mesh.boundary["z1"]},
    ground=mesh.boundary["z0"],
)
expected = epsilon_0 * 3.8 * .004 * .003 / .002
assert abs(result.C[0, 0] / expected - 1) < 1e-11
```

The four side faces in this example are **insulating**, so an affine potential
and the ideal parallel-plate formula are exact for this bounded problem. The
example does not include the fringing of finite plates in open space.

## Inputs and boundary meaning

- `mesh` is a conforming `galerkin.mesh3d.Mesh3D` in metres. Tetrahedra must
  have finite positive volume. Repeated/duplicate elements, unused nodes and
  nonmanifold faces are rejected. The shared tagged-face checks also apply.
  These checks do not establish geometric nonintersection or detect every
  hanging interface; the caller must supply a conforming dielectric mesh.
- `eps_r` is finite positive **real**: a scalar or one value per tetrahedron.
  Tensor, complex, dispersive and conductive materials are not supported by
  this API. A per-element array must follow the mesh's tetrahedron order.
- `conductors` maps nonempty names to nonempty distinct integer node sets.
  Its insertion order sets the matrix/field column order. Ground and all
  signal sets must be disjoint. These sets impose equipotential PEC nodes;
  the API does not infer electrode surfaces or their physical connectivity.
- Every connected mesh component needs explicit `ground` nodes. Unprescribed
  exterior faces have zero normal electric displacement (natural Neumann).
  Grounding an enclosing box models that enclosure. Leaving it insulating
  models a different boundary. Neither is automatically an infinite domain.

## Results and numerical gates

Column `j` sets signal `j` to one volt and all other prescribed nodes to zero.
The returned read-only arrays preserve those raw solves:

| Field | Meaning |
|---|---|
| `names` | Signal names in input order |
| `C` | Total conductor reaction charges per one-volt excitation, F |
| `energy_C` | Independent discrete evaluation `U.T @ K @ U`, F |
| `potentials` | Nodal unit-voltage basis, shape `(nodes, signals)`, V |
| `ground_charge` | Summed ground reaction for each one-volt drive, C |
| `num_tets` | Number of supplied tetrahedra |

`free_residual_relative`, `charge_balance_relative`, `energy_charge_relative`
and `symmetry_relative` normalize their maximum absolute discrepancy by
`max(abs(C))`. A discrepancy above `1e-8`, nonfinite values, nonpositive
capacitance eigenvalues or positive mutual/ground charge beyond the same
normalized tolerance is rejected. The matrix is not symmetrized or clipped
to hide a failed check. These numerical consistency gates are **not** an
error estimate for the continuous field or an accuracy guarantee for small
couplings. Check mesh conditioning, material contrast and convergence.

## Validation and limits

Uniform and aligned layered plate cases compare with analytical affine/series
solutions at relative `1e-11`. A nonuniform two-electrode field also compares
with separately assembled scikit-fem 12.0.2 tetrahedral P1 fields and energy
at `1e-10`. Geometry scaling gives `C -> scale*C`; material scaling and
conductor permutation are checked. A fixed grounded enclosure with two
internal electrode sheets is refined at 8, 16 and 24 cells per axis, requiring
decreasing changes. That trend does not assign an error bar to the final mesh.

Choose and converge the boundary for the intended physical problem. No
unbounded-space extrapolation, pad/antipad mesher, full-wave reference,
measurement agreement or frequency-validity range is established here.
In particular, a static C matrix alone does not establish via or stub behavior.
