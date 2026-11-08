# Bounded 3D static capacitance

[한국어](../../locales/ko/pages/packages/sipi/capacitance3d.md)

`sipi.capacitance3d.extract_capacitance_3d` computes a Maxwell capacitance
matrix **in farads** in an explicitly supplied tetrahedral dielectric domain.
It reuses galerkin's P1 3D stiffness assembly and a grounded sparse solve.
This is a static field API, not a transmission-line parameter set or a complete
via/transition model. It does not generate geometry, L, R, loss, radiation,
impedance, propagation or S-parameters. Strict JSON replay is available through
`Capacitance3DDocument`; no geometry-editor or application support is implied.

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

## Saved explicit-mesh input

`sipi.capacitance3d_document.Capacitance3DDocument` stores schema
`sipi.capacitance-3d/1`, `length_unit="m"`, and the required
`unprescribed_boundary="insulating"`. `mesh.nodes` contains coordinates and
`mesh.tetrahedra` contains zero-based integer node indices. `eps_r` is a real
positive scalar or an array following tetrahedron order. `ground` is a node
list; `conductors` is an **ordered list** of `{name, nodes}` objects so sorting
JSON keys never changes the matrix order. Mesh boundary tags are not saved:
only the explicit PEC node sets determine the prescribed potentials.

```python
from sipi.capacitance3d_document import Capacitance3DDocument
from sipi.execution import normalize_saved, execute_saved

document = Capacitance3DDocument(
    mesh, eps_r=3.8, conductors={"top": mesh.boundary["z1"]},
    ground=mesh.boundary["z0"],
)
text = normalize_saved(document.dumps())
restored = Capacitance3DDocument.loads(text)
assert restored.dumps() == text
output = execute_saved(text)
assert output["result"]["model"] == "bounded-static-3d"
assert output["result"]["capacitance_f"][0][0] == restored.analyze().C[0, 0]
```

Constructors and loaders snapshot and validate the mesh, material and boundary
sets without assembling a field operator or solving. Unknown/missing keys,
versions or units, repeated object keys/names, bool/fractional node indices,
nonfinite numbers and exponent overflow are rejected. No remeshing, unit
conversion, filesystem or code execution occurs. `to_dict()` returns a detached
copy. `analyze()` returns the same full `Capacitance3D` result as the direct API.

[Shared execution](execution.md) preserves the entire input for replay but its
result omits the nodal field and a second mesh copy. It includes C/energy-C in F,
ground charge in C for one-volt drives, node/tetrahedron counts and the four
numerical consistency ratios. It does not infer transmission-line quantities.
The input-byte limit can reject large meshes; increasing it does not limit
sparse-solver memory or runtime. Callers still need process isolation and their
own budgets. This explicit mesh is not a parametric geometry or a study/goal
input. Existing application candidates must update and validate their exact
engine pin before claiming this schema is supported.

## Shared layered meshing: a closed coaxial limit

The existing meshine extrusion can provide an explicit conforming volume.
For inner radius `a`, outer radius `b` and insulating ends, the bounded coaxial
solution is `C = 2*pi*epsilon_0*sum(eps_i*length_i)/log(b/a)`. The layers here
are along the axis, not radial series layers. The outer cylinder is grounded;
there is no open-end fringing or wave port.

```python
import numpy as np
from galerkin.mesh import annulus_mesh
from galerkin.mesh3d import Mesh3D
from meshine.mesh import TriMesh
from meshine.extrude import extrude

base = annulus_mesh(.14e-3, .4e-3, 16, 128)
footprint = TriMesh(base.nodes, base.triangles,
                   np.zeros(len(base.triangles), dtype=int),
                   ["dielectric"], base.boundary_edges)
raw = extrude(footprint, [0, 1e-3], divisions=2)
coax = extract_capacitance_3d(
    Mesh3D(raw.nodes, raw.tetrahedra), eps_r=3.8,
    conductors={"inner": raw.boundary_nodes["inner"]},
    ground=raw.boundary_nodes["outer"],
)
exact = 2*np.pi*epsilon_0*3.8*1e-3/np.log(.4/.14)
assert abs(coax.C[0, 0]/exact-1) < .005
```

Regression refines radial/angular divisions `(4,32)`, `(8,64)`, `(16,128)`
for uniform and aligned axial-layered dielectrics, requiring decreasing
analytical error and a final error below 0.5%. Separately, one/two/four axial
subdivisions at `(8,64)` must differ by less than `1e-4` relative to their
largest C. P1 tetrahedral subdivision can affect axial invariance at finite
resolution; exact equality is not assumed. These are fixture-specific gates.
Curvature polygonization changes the domain, so this is not a proof of
monotonicity on nested spaces of one fixed geometry. The example is not a
finite via, connector transition, or complete 3D geometry generator.

[Thin-grid/plate reference cells](grid_plate.md) add explicit geometry, mesh alignment and bounded static boundaries.
