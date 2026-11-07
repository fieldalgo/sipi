# Bounded 3D TEM-port fields

[한국어](../../locales/ko/pages/packages/sipi/ports3d.md)

`sipi.ports3d.solve_tem_ports_3d` solves a homogeneous, lossless Maxwell
boundary problem on an explicit conforming tetrahedral mesh. Two planar
annular ports use a **local TEM-admittance boundary**; every other exterior
face is PEC. The returned `LineNetwork` is the power-normalized projection
onto the two port TEM modes. This is a bounded field primitive, not a complete
via model, geometry generator or general multimode radiation solver.

```python
import numpy as np
from galerkin.mesh import annulus_mesh
from galerkin.mesh3d import Mesh3D
from meshine.mesh import TriMesh
from meshine.extrude import extrude
from sipi.ports3d import TEMPort3D, solve_tem_ports_3d

base = annulus_mesh(.25e-3, 1e-3, 2, 24)
footprint = TriMesh(base.nodes, base.triangles,
    np.zeros(len(base.triangles), dtype=int), ["dielectric"], base.boundary_edges)
raw = extrude(footprint, [0., .005], divisions=4)
mesh = Mesh3D(raw.nodes, raw.tetrahedra)
faces = mesh.boundary_faces()
ports = []
for name, z in [("near", 0.), ("far", .005)]:
    selected = faces[np.all(mesh.nodes[faces, 2] == z, axis=1)]
    nodes = np.unique(selected)
    ports.append(TEMPort3D(name, selected,
        np.intersect1d(nodes, raw.boundary_nodes["inner"]),
        np.intersect1d(nodes, raw.boundary_nodes["outer"])))
result = solve_tem_ports_3d(mesh, ports=ports, frequency=[5e8, 1e9], eps_r=4.)
assert result.network.s.shape == (2, 2, 2)
assert result.power_balance.max() < 1e-8
assert abs(result.network.s[1, 0, 0]) < .02
```

## Contract and boundary equation

- Coordinates are metres, frequency is a nonempty strictly increasing array
  of positive Hz. `eps_r` is one finite positive real scalar, and `mu_r=1`.
  There is no material dispersion, conduction, tensor or per-element material.
- Supply exactly two `TEMPort3D(name, faces, signal, ground)` objects with
  unique names. Faces are distinct exterior triangles in global node indices.
  Each port must be planar, connected and annular with two closed perimeter
  loops. Signal and ground must each cover one entire distinct loop. Port
  nodes must be disjoint, and PEC walls must meet ports exactly on their rims.
- The volume must be connected. Duplicate or degenerate tetrahedra, unused
  nodes, invalid indices and nonmanifold faces are rejected. As with the
  [static API](capacitance3d.md), this does not detect all geometric overlap or
  hanging interfaces; the caller remains responsible for conforming geometry.
- A surface P1 Laplace solve sets signal to one volt and ground to zero.
  Its negative tangential gradient defines the TEM edge mode `e_p`.
  There is no inferred port orientation from a global axis: reversing the
  supplied face winding does not change the electrical signal/ground polarity.

For `exp(+j omega t)`, shared galerkin Whitney-edge curl-curl and mass matrices
give `K - beta**2 M + j beta (B0+B1)`, where `beta=omega*sqrt(mu0*eps0*eps_r)`
and `Bp` is the exact tangential edge mass on port p. Excitation q is
`2j beta Bq e_q`. PEC edge degrees of freedom are zero. This local boundary is
exact for a continuous uniform TEM wave; it does **not** impose each higher
mode's propagation-dependent admittance as a full waveguide port would.

## Returned values and limits

`port_norm[p] = e_p.T @ Bp @ e_p` is dimensionless. A unit-voltage incident
wave has power `sqrt(eps/mu)*port_norm[p]/2`. Therefore the calculated port
reference resistance is `sqrt(mu/eps)/port_norm[p]` ohms. TEM projections are
normalized by the square root of these power ratios, and port order/names
follow the input. Use `result.network.renormalized(...)` for a different real
reference impedance; do not relabel the raw matrix as 50 ohms.

All result arrays are read-only snapshots. Per frequency:

| Field | Meaning |
|---|---|
| `linear_residual` | Frobenius norm of the free-system residual divided by RHS norm |
| `power_balance` | Maximum absolute full outgoing/incident boundary power minus one |
| `reciprocity` | Maximum absolute entry of `S-S.T` |
| `projected_unitarity` | Maximum absolute entry of `S.conj().T@S-I` |
| `unprojected_port_power[f,q]` | Full outgoing boundary power minus TEM-projected power, normalized by drive q |

Finite fields and diagnostics, and residual/power balance/reciprocity at most
`1e-8`, are required. A failed solve raises `ValueError` and returns no partial
network. The TEM-only matrix need not be unitary: boundary power orthogonal to
the TEM mode is retained separately, **not interpreted as material loss**.
Raw values are never clipped or symmetrized. These algebraic checks do not
establish mesh accuracy, port-placement convergence or a physical error bar.

Validation covers a PEC coax with radii 0.25/1 mm, length 5 mm, eps_r=4 and
1 GHz. Radial/angular/axial refinement `(1,12,2)`, `(2,24,4)`, `(4,48,8)` must
reduce complex transmission error against `exp(-j beta length)`; finest
transmission and reflection errors must be below .02. Same-mesh independent
scikit-fem edge FEM must agree within `1e-9`. Rotation, port order and combined
geometry/frequency scaling must preserve S within `1e-9`. The outer conductor
is the actual fixed PEC wall, not an artificial open-space truncation.

No arbitrary transition, pad/antipad, via/stub, radiation, higher-mode cutoff,
or conductor-loss accuracy is established by these tests. For a new geometry,
independent references and mesh/port-distance studies are still needed; a small
algebraic residual alone is insufficient. Application support is separate
from this Python API. Runtime dependencies remain the pinned
external galerkin/meshine and NumPy/SciPy; scikit-fem is test-only.

## Saved input and shared execution

`sipi.ports3d_document.TEMPorts3DDocument` stores `sipi.tem-ports-3d/1`.
Using the mesh and ports from the example above:

```python
import json
from sipi.ports3d_document import TEMPorts3DDocument
from sipi.execution import normalize_saved, execute_saved

document = TEMPorts3DDocument(mesh, ports=ports, frequency=[5e8, 1e9], eps_r=4.)
text = normalize_saved(document.dumps())
replayed = TEMPorts3DDocument.loads(text).analyze()
np.testing.assert_allclose(replayed.network.s, result.network.s, rtol=0, atol=1e-10)
output = execute_saved(text, max_evaluations=2)
assert output["result"]["model"] == "bounded-homogeneous-3d-local-tem-admittance"
assert output["result"]["network"]["port_names"] == ["near", "far"]
json.dumps(output, allow_nan=False)
```

The exact top-level fields are `schema`, `length_unit="m"`,
`unprescribed_boundary="pec"`, `port_boundary="local-tem-admittance"`, `mesh`,
`eps_r`, `frequency_hz` and `ports`. `mesh` contains only `nodes` and
`tetrahedra`; `ports` is an ordered list of exactly two objects containing
only `name`, `faces`, `signal` and `ground`. Integer indices are checked before
Mesh3D can coerce them. Unknown/missing fields, duplicate JSON keys, booleans
in numeric fields, nonfinite/overflowing numbers and unsupported boundary
labels are rejected. Data is detached from the caller and `to_dict()` returns
a copy. Normalization validates geometry/topology without a port or volume
field solve; it does not certify conformity or physical accuracy.

Shared execution counts **one evaluation per frequency** against
`max_evaluations`, before any field work. Its usual input-byte limit also
applies. Neither limit bounds sparse-solve memory or elapsed time; callers
must provide process/Worker isolation and cancellation. Solver errors propagate
without returning a successful partial network. Selected output preserves
the boundary-model label, network, port norms, node/tet/edge counts and all
six consistency/power diagnostics. Volume fields are not serialized. This
engine contract does not advance an application's pinned engine or establish
Windows/Worker support for that application.
