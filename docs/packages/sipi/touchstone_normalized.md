# Touchstone1 normalized parameter input

**English** | [한국어](../../locales/ko/pages/packages/sipi/touchstone_normalized.md)

`sipi.touchstone.loads_touchstone_normalized(text, *, ports, z_ref, port_names=None)`
reads explicit Y/Z/H/G in a strict Touchstone1.0 subset. Port count and output
reference resistance are required. H/G requires exactly two ports; Y/Z supports
the existing parser's positive port counts. Existing S, physical v2 Y/Z and
[physical v2 H/G](touchstone_hybrid.md) readers keep their accepted kinds.

```python
import numpy as np
from sipi import hybrid_network
from sipi.touchstone import loads_touchstone_normalized

text = '# Hz H RI R 100\n0 .8 0 -.1 0 .2 0 1 0\n'
network = loads_touchstone_normalized(text, ports=2, z_ref=[31., 73.],
                                     port_names=['input', 'output'])
physical = np.array([[[80., .2], [-.1, .01]]])
expected = hybrid_network([0.], physical, z_ref=[31., 73.])
np.testing.assert_array_equal(network.s, expected.s)
```

The scalar option R (default 50 ohms) describes input normalization. It is
independent of `z_ref`, the required positive-real scalar/per-port output target.
Restore physical matrices as follows:

| Input | Physical conversion |
|---|---|
| Z | Z = R Zn |
| Y | Y = Yn / R |
| H | H11 = R Hn11; H22 = Hn22 / R |
| G | G11 = Gn11 / R; G22 = R Gn22 |

Hybrid off-diagonals remain dimensionless. H means [V1,I2]=H[I1,V2], and G means
[I1,V2]=G[V1,I2], with currents entering both ports. These dimensional formulas
follow those physical definitions and scalar-reference normalization. They are
not verbatim formulas from the [IBIS Touchstone2.0 specification](https://ibis.org/touchstone_ver2.0/touchstone_ver2_0.pdf):
page7 specifies the role of R for v1, and pages14–15 illustrate normalized v1 Z
converted into physical v2 Z. The reader recovers finite physical values before
one call to the existing [Y/Z](touchstone_parameters.md) or
[H/G](hybrid_parameters.md) conversion, retaining their numerical gates.

```python
# Same physical H, with input normalized at a different resistance.
other = '# Hz H RI R 50\n0 1.6 0 -.1 0 .2 0 .5 0\n'
same = loads_touchstone_normalized(other, ports=2, z_ref=[31., 73.])
np.testing.assert_array_equal(same.s, network.s)
np.testing.assert_array_equal(same.z_ref, [31., 73.])
assert not same.s.flags.writeable
```

Supported syntax is RI/MA/DB, Hz/kHz/MHz/GHz, ASCII comments and split data lines.
One/two-port files contain one full frequency record per line; two-port data
uses 11,21,12,22 order. Larger matrices use the existing v1 row layout. No file
extension is inspected: `ports` is always explicit. The default parameter kind
S is rejected, including an option line that omits Y/Z/H/G. R must be one
positive finite real value. Output references may differ by port; input R may not.
Names must be a sequence of valid unique strings, not a single string.

Reject v2, version1.1 multiple reference values, mixed mode, noise, unsupported
keywords, malformed/incomplete records, nonfinite decoded or recovered values,
invalid counts/references/names and the original conditioning/residual failures.
Arrays are detached/read-only. No file I/O, interpolation, material fitting,
passivity/causality, measurement provenance or full format conformance is inferred.

Validation covers all four parameters, three value formats, four frequency units,
Y/Z with one through four ports, R invariance, mixed output references, zero/ideal
transformer/diagonal closed forms, strict failures and one physical converter call.
All 290 prior S/Y/Z/H/G fixtures preserve exact array/metadata hashes.

Independent scikit-rf2.2.0 same-file checks are qualified: v1 Z at R=1/50/100/10000
and Y/H/G at R=1 are valid reference paths. Its v1 parser multiplies every raw
Y/H/G element by R, which does not preserve the physical units above when R is
not1. Those discrepant observations are retained, not accepted as accuracy
evidence. Equivalent physical v2 files provide a separate reference for all16
parameter/R cases; the preregistered absolute S gate is1e-12 (pilot maximum
2.36e-14). Product tests also use21 qualified same-file cases across three formats
and12 equivalent v2 cases at nonunit R. No criterion is relaxed to match a failing
reference path. scikit-rf remains test-only with existing BSD-3-Clause notices.
No runtime dependency, saved schema, spatial model, application or platform
support changes; algebraic conversion has no spatial convergence claim.
