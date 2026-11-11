# Element energy in electrostatic extraction

`capacitance_matrix` uses the same galerkin P1 stiffness, Dirichlet solve,
conductor order and material coefficients. It evaluates the resulting Maxwell
capacitance through the equivalent element integral

`C_ij = epsilon_0 sum_T area_T grad(V_i)^T eps_T grad(V_j)`.

The gradients come from galerkin's public `element_gradient`. Real and imaginary
contributions are summed separately with `math.fsum`. This avoids the cancellation
between diagonal and off-diagonal terms in the assembled `V.T @ K @ V` evaluation.
It changes floating-point extraction arithmetic, not the mesh or finite-element
approximation. Reciprocity is explicit; the complex bilinear form does **not**
conjugate either field. Conjugation would change the lossy capacitance problem.

Scalar, per-element and transverse tensor coefficients retain their existing
validation and units. Public arguments, JSON inputs, vacuum extraction, loss
convention and target-search tolerances are unchanged. Output values can differ
in their last digits, so retain the exact engine artifact with numerical results.
Mesh and exterior-boundary convergence remain separate requirements.

Independent checks integrate three affine fields over uniform and two-region
rectangles with scalar and tensor coefficients, including complex fields that
distinguish bilinear from Hermitian energy. They require relative agreement
within `1e-13` and exact invariance under triangle-order permutation. Six
parallel-plate cases compare against `epsilon_0*width*eps/height` within `1e-10`.
Existing analytical, independent FEM, material, asymmetric-line and impedance
search checks retain their original tolerances. These are bounded numerical
checks, not a guarantee of identical arithmetic on every platform or of physical
accuracy for an unconverged geometry.

[Overview](overview.md) · [Tensor electrostatics](tensor_electrostatics.md) ·
[한국어](../../locales/ko/pages/packages/sipi/element_energy.md)
