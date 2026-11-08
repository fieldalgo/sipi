# Physical two-port hybrid parameters

**English** | [한국어](../../locales/ko/pages/packages/sipi/hybrid_parameters.md)

`hybrid_network(frequency, hybrid, *, z_ref, names=None)` converts physical H
samples. `inverse_hybrid_network(frequency, inverse_hybrid, *, z_ref, names=None)`
converts physical G samples directly. Both return a single-ended `LineNetwork`.
The existing [physical Z/Y APIs](parameter_network.md) remain unchanged.

Currents enter both ports; phasors use exp(+jωt):

| Kind | Defining equation | 11 units | 12/21 units | 22 units |
|---|---|---|---|---|
| H | [V1,I2]ᵀ = H[I1,V2]ᵀ | ohms | dimensionless | siemens |
| G | [I1,V2]ᵀ = G[V1,I2]ᵀ | siemens | dimensionless | ohms |

These are physical mixed units, not normalized file values. G is independently
specified; the implementation does not form it by inverting H.

```python
import numpy as np
from sipi import hybrid_network, inverse_hybrid_network

frequency = [0., 1e6]
through_h = np.array([[[0., 1.], [-1., 0.]]]*2)
network = hybrid_network(frequency, through_h, z_ref=[31., 73.],
                         names=['input', 'output'])
assert network.s.shape == (2, 2, 2)
np.testing.assert_allclose(network.s[0].T @ network.s[0], np.eye(2), atol=1e-12)
```

Inputs require exact shape(F,2,2), finite numeric entries without booleans,
finite nonnegative strictly increasing Hz, and an explicit positive-real
scalar or two-element reference vector. Constant matrices are not broadcast.
Names default to port1/port2 or must be two distinct, nonempty, single-line
strings. Complex or frequency-dependent references are not accepted. Returned
frequency, S and reference arrays are detached/read-only; names are copied.

Let d1,d2 be square roots of the two references. Dimensionless H entries are
H11/d1², H12*d2/d1, H21*d2/d1, H22*d2². Dimensionless G entries are
G11*d1², G12*d1/d2, G21*d1/d2, G22/d2². With normalized v=a+b and i=a-b,
form B*b+A*a=0. For either dimensionless matrix Q:

```
A   = [[1-Q11, -Q12], [-Q21, 1-Q22]]
B_H = [[1+Q11, -Q12], [ Q21,-1-Q22]]
B_G = [[-1-Q11, Q12], [-Q21, 1+Q22]]
S   = -solve(B, A)
```

Before addition, divide Q and the identity terms by
max(1,max(abs(Re(Q))),max(abs(Im(Q)))) independently at each frequency.
Reject nonfinite normalization/intermediates/results, scaled singular value
s_min<=1e-12*max(1,s_max), or normalized B*S+A residual>1e-10. There is no
pseudoinverse, conditioning repair or inverse of H/G/individual entries.
These numerical gates are explicit implementation limits, not a physical
accuracy certificate. H/G can be singular while the wave denominator is valid.

```python
zero_g = inverse_hybrid_network([0.], np.zeros((1, 2, 2)), z_ref=50.)
np.testing.assert_array_equal(zero_g.s[0], np.diag([1., -1.]))
new_reference = network.renormalized([50., 50.])
np.testing.assert_allclose(new_reference.s[0], [[0., 1.], [1., 0.]], atol=1e-12)
assert not network.s.flags.writeable
```

Zero H means short port1/open port2; zero G means open port1/short port2.
Ideal through and transformer equations are accepted without constructing an
infinite Z matrix. Active matrices remain active; conversion does not infer
passivity, reciprocity, causality, material properties or physical extraction.

Validation includes24 ideal transformer cases at equal/unequal references,
exact zero/singular boundary relations, row-wise physical voltage/current
constraints, passive RC/RLC loaded KCL, reference changes and consistent unit
scaling. Analytical and S comparisons use1e-12, physical VI residual1e-10;
strict shape/frequency/reference/name, scaling and solver-failure gates are
tested. This is network algebra with no spatial mesh or outer-boundary
convergence claim and no frequency interpolation.

Independent scikit-rf2.2.0 checks comprise28 `h2s`/`g2s` cases and four direct
`y2s` cases. The latter start from rank-one physical Y: `g2s` first forms H and
then divides by H22 to construct Z, which is not a finite representation for
this case. The original comparison produced NaN or incorrect finite S and
remains a recorded reference-path failure. The four qualified comparisons use
the original Y directly plus closed form S=I-2α/(1+5α)*[[1,2],[2,4]] and the
physical constraints. No tolerance was relaxed or candidate calculation changed.
The32 qualified comparisons have maximum absolute S difference1.93e-15 in the
recorded pilot; this is agreement on these algebraic cases, not measured accuracy.

The BSD-3-Clause scikit-rf reference is test-only; its copyright/conditions/
disclaimer are retained in validation records. No runtime dependency, saved
schema, application or platform support is added. Physical Touchstone2 files
use the separate [H/G reader](touchstone_hybrid.md).
