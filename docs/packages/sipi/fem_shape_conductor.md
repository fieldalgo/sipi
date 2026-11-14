# Explicit FEM geometry-energy currents

`fem_shape_current_factors(mesh, signals, ground)` calculates whole-boundary
current energies from the geometric derivative of a vacuum P1 field. It uses
external galerkin assembly, Dirichlet and capacitance APIs. It is an explicit
alternative; existing surface-current APIs and saved-line defaults are unchanged.

For unit longitudinal signal currents, each returned matrix has units 1/m.
`parts` follows signal-name order and then one group containing every reference
surface. Both reference planes and finite grounded traces can belong to that
group. Separate foil faces or separate ground materials are not resolved here.

```python
import numpy as np
from galerkin import rectangle_mesh
from sipi import fem_shape_current_factors

mesh = rectangle_mesh(.002, .001, 8, 4)
current = fem_shape_current_factors(
    mesh, {'signal': mesh.boundary['top']}, mesh.boundary['bottom'])
np.testing.assert_allclose(current.parts[:, 0, 0], [500., 500.], rtol=1e-10)
assert len(current.samples) == 16
```

The dielectric domain moves with unit outward normal velocity on the selected
metal group and zero normal velocity on other boundaries. At an ordinary
boundary vertex, a symmetric normal bisector avoids the spurious tangential
motion that a rank decision on almost parallel normals can introduce. The
boundary must be manifold with two incident boundary edges per vertex. Each
conductor node must belong to its own dielectric boundary; internal zero-thickness
strips are rejected. Inputs allow 1–4 signals, at most 300,000 nodes and 600,000
triangles. Vacuum is isotropic and nonmagnetic; open boundaries are insulating.

Two positive harmonic extensions carry the prescribed motion through the domain.
The second coefficient is `1 + 0.5*r²/R²`, about the node centroid and normalized
by the largest node radius. Each contracts the geometry derivative of the field
energy, normalized by the same vacuum capacitance. The primary extension supplies
`parts`; the two results are retained in `extension_parts`, without averaging or
positive-semidefinite projection.

Every call also recomputes vacuum capacitance on both signed offsets at
`h = min_edge * 1e-3` and `h/2`, for both extensions and every group. All offset
triangles must have positive signed area before any offset field solve starts.
There are `8*(N+1)` capacitance requests, two original voltage-basis calls, and
`4*(N+1)` scalar velocity solves. A capacitance request solves N voltage bases;
these counts are not a claim that one request is one scalar linear solve.

Both finite-difference observations must agree with the energy derivative
entrywise to 1e-4, with no denominator floor. The step observations obey the same
gate. Extension disagreement is at most 1e-3 separately for each whole boundary
matrix. Normal velocity has a 1e-12 residual gate; velocity residual, reciprocity
and scaled positive semidefiniteness use 1e-10. Total energy must be positive
definite. These checks are numerical consistency checks. They do not establish
mesh or outer-domain convergence, small mutual-entry accuracy, measured-board
accuracy, or the validity of a later metal/roughness law.

`base` retains the original P1 gradient energies, signed flux integrals and C0.
`current_integrals` and `current_error` still refer to that original gradient
calculation. They are not signed currents reconstructed from the new energies,
and a small flux error does not bound resistance error. `L_external` uses the same
C0. Check mesh resolution and the finite outer domain independently.

`FEMShapeCurrentError` preserves the stage, completed original base when available,
energy arrays, partial finite differences, completed capacitance samples, failed
sample address, and available diagnostics. The address is
`(extension, group, level, sign, displacement_m)`. Geometry admission errors occur
before field solves. Interrupts propagate. Nonfinite failed observations remain
in the exception for diagnosis; they are not accepted results or JSON data.

The associated tests compare plate/coax analytical limits, independent scikit-fem
12.0.2 P2 potential and volume-energy integration, geometric transformations,
closed-pair refinement and three/four signal ordering. scikit-fem is a BSD-3-Clause
test dependency, not a runtime dependency. Reference agreement is distinct from
mesh/outer convergence. Validation on another operating system or in a browser
Worker/portable executable must be performed separately for the exact artifact.

[한국어](../../locales/ko/pages/packages/sipi/fem_shape_conductor.md)
