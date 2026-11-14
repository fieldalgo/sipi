# Explicit dual-cell surface currents

`sipi.dual_cell_conductor` offers an opt-in boundary-current reconstruction
from the existing shared P1 vacuum solve. Existing gradient APIs, saved line
documents and their defaults retain their original calculation.

```python
import numpy as np
from galerkin import rectangle_mesh
from sipi.dual_cell_conductor import dual_cell_surface_current_factors

mesh = rectangle_mesh(.002, .001, 8, 4)
result = dual_cell_surface_current_factors(
    mesh, {'signal': mesh.boundary['top']}, mesh.boundary['bottom'])
np.testing.assert_allclose(result.parts[:, 0, 0], [500., 500.], rtol=1e-10)
assert result.current_error < 1e-10
```

For voltage bases V and stiffness K, the weak nodal reaction is r=KV. At each
metal node, D is half the sum of incident metal edge lengths. Integrated
unit-current reactions are j=eps0*r*inv(C0); each boundary contributes
sum(j_i.T*j_i/D_i). `parts` has shape (N+1,N,N) in 1/m: signal boundaries in
`names` order, then the combined reference. `total`, `C0`, `L_external` and
`current_integrals` follow the existing surface-current result contract.

These are averages over boundary dual lengths. They are neither interpolated
normal derivatives nor an exact squared-flux integral. `current_error` checks
algebraic current conservation, with rejection above 1e-10; it does **not**
estimate resistance or field error. Approximate FEM reactions do not establish
a rigorous resistance bound. Resolve mesh, corners and outer boundaries for
each intended geometry, and inspect small mutual entries separately.

`dual_cell_conductor_loss_by_boundary(section, frequency, conductors=...,
reference=..., ground_thickness=..., **mesh_options)` applies the existing
`SurfaceMetal` or `LayeredSurfaceMetal` laws to these factors. It returns the
existing boundary loss result, including R, internal L and per-boundary power
parts. It checks finite cores and skin depth before creating one mesh and one
voltage basis. All reference surfaces share one material. Face-specific laws
and saved-document selection of this method are not included.

The exterior remains isotropic and nonmagnetic; open electric boundaries are
insulated. The surface-impedance approximation retains its high-frequency and
local-plane restrictions. This is not an interior eddy-current calculation.

Validation includes an exact plate, the coaxial polygon limit, independently
assembled scikit-fem P1 reactions, scale/reflection/permutation invariants,
and a matched-boundary panel observation for one coupled microstrip. In that
case the refined total matrix differs from the panel result by about 0.54%
in maximum-entry norm, while a small mutual entry is about 15.45/m versus
10/m. The total norm must not be interpreted as every entry's relative error.
These observations do not establish universal convergence or native platform
equivalence. The original gradient refinement failures remain separate.

[한국어](../../locales/ko/pages/packages/sipi/dual_cell_conductor.md)
