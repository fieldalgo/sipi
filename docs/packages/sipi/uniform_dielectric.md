# Uniform scalar dielectric reuse

Frequency-dependent extraction reuses the vacuum capacitance on a resolved
mesh when **every actual element has exactly the same scalar permittivity**
at that frequency. This applies to scalar and multiconductor cross-sections,
including different region names that evaluate to the same scalar value.

For a constant scalar coefficient, the stiffness matrix is `K=eps*K0`.
Dirichlet potentials with fixed conductor voltages are unchanged, so the
complex energy gives `C_complex=eps*C0`. The external inductance remains
`L=mu0*eps0*inv(C0)`; it is not scaled by the material. Dielectric conductance
remains `G=-2*pi*f*Im(C_complex)` with the existing positive-time convention.
This is an identity of the discrete problem, not an effective-material model.

```python
import numpy as np
from sipi import stripline
from sipi.dielectric import DebyeDielectric, dispersive_line

material = DebyeDielectric(2., [4.], [1e9])
frequencies = [0., 1e8, 1e9, 1e10, 1e12]
section = stripline(width=.5e-3, plane_spacing=1e-3, eps_r=1., box_width=8e-3)
sweep = dispersive_line(section, frequencies, materials={'dielectric': material},
    edge_size=1e-6, far_size=.125e-3, grade=.1)
expected = material.permittivity(frequencies)[:, None, None]*sweep.C0
np.testing.assert_allclose(sweep.C_complex, expected, rtol=1e-12, atol=0)
assert not sweep.C_complex.flags.writeable
assert sweep.G[0, 0, 0] == 0
```

## Exact selection and shared composition

The existing region-to-element mapping is evaluated at every frequency. The
shortcut requires a nonempty scalar vector with finite passive coefficients,
positive real part, and exact equality of every entry. It does not compare
region names, use `allclose`, round material values, or reuse a decision from
another frequency. A difference of 1e-12 still takes the general solver.
Unused scalar region samples cannot change the actual field coefficients.

Tensor samples retain the existing general solve, including isotropic tensors.
Nonuniform scalar samples also retain the complex solve. Material preflight,
unknown-region rejection in the public API, conductor/reference boundaries,
signal ordering, read-only outputs and saved inputs are unchanged.

The internal shared-mesh line composition can supply its already extracted
vacuum C0. Reuse does not modify that matrix or change conductor models. An
all-uniform frequency sweep therefore needs one capacitance-matrix extraction
for C0, or zero additional extractions when composition supplies C0. These are
matrix-extraction counts, not counts of internal linear solves, meshing calls,
optimizer attempts or elapsed-time guarantees. General samples still require
their existing extractions. No new dependency, public API or schema is added.

## Independent acceptance and scope

`tests/sipi/test_uniform_dielectric.py` compares scalar stripline, symmetric
pair and identical-material two-region pair results with direct complex FE,
with/without supplied C0, at 0/.1/1/10/1000 GHz. The maximum per-entry relative
complex-C difference must be at most 1e-10. A separate scikit-fem 12.0.2 complex
P1 assembly/Dirichlet-energy calculation on the paired mesh uses the same gate.
This independent implementation shares the mesh and does not establish mesh
convergence by itself.

Complex parallel-plate series capacitance checks near-but-unequal layers,
coefficients equal at only one frequency, and diagonal/isotropic tensor paths.
Invalid samples retain rejection. Vacuum L, G, sample copies, signal order
and matrix-extraction counts are checked separately.

A thin paired stripline uses width .5 mm, gap .1 mm, plane spacing 1 mm and
box width 8 mm; edge/far/grade are 1 micrometre/.125 mm/.1. Requested mesh,
halved edge/far/grade, and a separate 16 mm box must each keep differential
and common impedances within .5 ohm of independent Cohn expressions at all
five material samples. Existing material, tensor, shared-line, conductor-face,
reference and sampled-goal tests retain their previous gates. Finite meshes
still need application-specific convergence checks.

This does not change the quasi-TEM approximation, characterize an actual
laminate, certify full-wave behavior at these test frequencies, or establish
general application speedups. Runtime and platform acceptance belong to the
exact built revision and remain separate from source/installed engine checks.

[Dielectrics](dielectrics.md) · [Sampled goals](sampled_design.md) ·
[한국어](../../locales/ko/pages/packages/sipi/uniform_dielectric.md)
