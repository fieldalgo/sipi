# Symmetric-pair modal projection

`LineParameters.even_odd()` uses the real, lossless quasi-TEM matrices `C`,
`C0` and `L`. For each matrix `M`, the even and odd projections are

```text
M_even = (M00 + M11)/2 + M01
M_odd  = (M00 + M11)/2 - M01
Z_mode = sqrt(L_mode / C_mode)
eps_eff_mode = C_mode / C0_mode
```

The implementation sums the three terms `M00/2`, `M11/2` and `±M01`
together with compensated summation. Rounding the diagonal mean before
adding the mutual term can lose a significant part of a small projection.
This change reduces that arithmetic error; it does not change the field
solution, mesh, material model or inverse-design residual definition.

The existing two-conductor and equal-self-term checks still apply. The
method retains `z_diff = 2*z_odd` and `z_common = z_even/2`. It does not
turn an asymmetric pair into a symmetric one or replace a general
multiconductor characteristic-matrix calculation.

`tests/sipi/test_modal_projection.py` compares the returned quantities
with exact rational projections of the input floating-point matrices and
200-digit decimal square roots/ratios, including positive-definite matrices
with near cancellation, signal permutation and input preservation. These
checks isolate arithmetic; they do not establish physical accuracy,
mesh/outer-boundary convergence or identical inverse-search paths across
platforms. Existing field/reference and inverse-design checks remain needed.

[Overview](overview.md) · [한국어](../../locales/ko/pages/packages/sipi/modal_projection.md)
