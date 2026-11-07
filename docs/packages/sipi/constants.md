# Physical constants and runtime reproducibility

SIPI uses the **CODATA 2022 published rounded values** consistently in electric,
magnetic, surface-current and finite-metal extraction. They live in
`sipi.constants` and do not depend on the constants table bundled with SciPy.

| Symbol / Python name | Value | Unit | Standard uncertainty |
|---|---|---|---|
| ε₀ / `epsilon_0` | 8.8541878188e−12 | F/m | 1.4e−21 F/m |
| μ₀ / `mu_0` | 1.25663706127e−6 | H/m | 2.0e−16 H/m |
| c / `SPEED_OF_LIGHT` | 299792458 | m/s | exact |

Source: [NIST, 2022 CODATA complete table](https://physics.nist.gov/cuu/Constants/Table/allascii.txt),
retrieved 2026-11-07. `CODATA_REVISION` is 2022. These public reference numbers
are recorded directly; no reference-library source code is copied.

```python
from sipi.constants import CODATA_REVISION, epsilon_0, mu_0, SPEED_OF_LIGHT

print(CODATA_REVISION, epsilon_0, mu_0, SPEED_OF_LIGHT)
assert abs(epsilon_0*mu_0*SPEED_OF_LIGHT**2-1) < 2e-12
```

Only c is exact. Keeping the two published measured values independently gives
`epsilon_0*mu_0*c**2 - 1 ≈ 1.19e-12` from their tabulation rounding. Neither
value is adjusted to force an exactly unit product. This rounding is below the
published measurement uncertainties; it is not a solver error estimate.

Earlier SIPI builds inherited SciPy's table. A runtime with CODATA 2018 used
ε₀=8.8541878128e−12 F/m and μ₀=1.25663706212e−6 H/m. That changes a fixed-mesh
capacitance by about 6.78e−10 relative to the 2022 value even with identical
numerical algorithms. The explicit revision prevents this silent dependency
effect. It preserves values from the verified SciPy 1.18.1 environment, but
intentionally changes older runtimes' constant selection. Saved geometry and
material schemas remain unchanged; reproduce older results with their exact
original engine and dependency artifacts.

Fixed constants do not promise identical triangulations, library rounding or
floating-point outputs across operating systems. Record engine/wheel hashes,
runtime versions and mesh settings; compare the same mesh when separating
solver differences from mesh generation. Independent reference tools must use
the same stated physical constants for a strict algebraic comparison. Existing
field convergence and model-validity limits still apply.

Tests inject older/different SciPy constants before importing the engine in an
isolated interpreter, then check exact linear parallel-plate P1 fields and the
analytic good-conductor surface law. No shared galerkin/meshine implementation
or reference-tool constants are modified by the product.

[한국어](../../locales/ko/pages/packages/sipi/constants.md)
