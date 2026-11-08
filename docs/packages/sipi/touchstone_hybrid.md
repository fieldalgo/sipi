# Touchstone2 physical hybrid input

**English** | [한국어](../../locales/ko/pages/packages/sipi/touchstone_hybrid.md)

`sipi.touchstone.loads_touchstone_hybrid(text, *, z_ref, ports=None, port_names=None)`
reads explicit physical H/G from a strict single-ended Touchstone2.0 subset.
It is a separate module API; existing [S and physical Y/Z readers](touchstone_parameters.md)
keep their accepted kinds and behavior. Exactly two ports are required.

```python
import numpy as np
from sipi import hybrid_network
from sipi.touchstone import loads_touchstone_hybrid

text = """[Version] 2.0
# Hz H RI R 123
[Number of Ports] 2
[Two-Port Data Order] 12_21
[Number of Frequencies] 1
[Reference] 40 90
[Network Data]
0 80 0 .2 0 -.1 0 .01 0
[End]
"""
network = loads_touchstone_hybrid(text, z_ref=[31., 73.],
                                 port_names=['input', 'output'])
expected = hybrid_network([0.], np.array([[[80., .2], [-.1, .01]]]),
                          z_ref=[31., 73.])
np.testing.assert_array_equal(network.s, expected.s)
```

[The IBIS Touchstone2.0 specification](https://ibis.org/touchstone_ver2.0/touchstone_ver2_0.pdf)
defines version2 H/G as physical values unaffected by R/[Reference] (pages7/10),
and limits H/G to two ports (page13). Its triangular formats represent numeric
transpose symmetry (page11). The explicit target `z_ref` selects the output
power-wave references; file references are syntax-checked and do not scale data.

H means[V1,I2]=H[I1,V2], with H11 in ohms/H22 in siemens; G means
[I1,V2]=G[V1,I2], with G11 in siemens/G22 in ohms. Off-diagonals are dimensionless
and currents enter both ports. Parsed matrices go once to
[direct physical hybrid conversion](hybrid_parameters.md), retaining its
finite, conditioning and residual gates. No H/G or individual entry is inverted.

RI/MA/DB, Hz/kHz/MHz/GHz, both explicit two-port orders21_12/12_21, line splits,
ASCII comments/information blocks, and Full/Lower/Upper matrices use the shared
strict parser. Triangular reconstruction uses ordinary transpose, not conjugate
transpose. It is independent of the full-matrix two-port order. Symmetric numeric
H/G does not imply reciprocity: reciprocal hybrid off-diagonals have opposite signs.

```python
changed = text.replace('R 123', 'R 701').replace('[Reference] 40 90', '[Reference] 2 900')
same = loads_touchstone_hybrid(changed, z_ref=[31., 73.])
np.testing.assert_array_equal(same.s, network.s)
np.testing.assert_array_equal(same.z_ref, [31., 73.])
assert not same.s.flags.writeable
```

The version, H/G option, number of ports/frequencies, two-port order, network
data and end blocks must follow the supported strict syntax. `ports`, if given,
must match2. Target references are required positive real scalar/two values;
caller names must be two valid unique strings, and a single string is rejected.
Returned frequency/S/reference arrays are detached/read-only. File I/O remains
the caller's responsibility. Comments do not assign physical port pairing.

Reject version1, default/S/Y/Z kinds, non-two-port data, mixed mode, noise,
unsupported keywords, duplicate/misordered metadata, invalid units/numbers,
incomplete records, invalid references and original conversion failures. No
normalization of version1, automatic interpolation, passivity, causality,
measurement provenance or material fitting is inferred.

Validation compares parsed physical matrices exactly with direct API inputs;
zero H/G boundaries, ideal transformers and rank-one inverse-hybrid equations
use1e-12 analytic gates. File reference changes do not change results at a fixed
target. Both triangular orders reconstruct identical results, and all legacy
110 S plus124 Y/Z fixtures preserve exact array/metadata hashes.

Twenty same-file independent scikit-rf2.2.0 checks use12 full cases (H/G,
RI/MA/DB, both orders) plus8 lower/upper RI/MA cases encoded as12_21. The original
21_12 triangular comparison failed: that reference parser transposes a partly
filled matrix before mirroring the originally declared triangle, losing its
off-diagonal data. Original files/results are preserved; those eight comparisons
are not counted as passing. The qualified order checks use the same physical
matrices and retain the1e-12 absolute S gate (pilot maximum4.64e-15). Both orders
also undergo direct raw-value reconstruction tests. This qualification does not
change the product parser or imply arbitrary reference-reader accuracy.

The [rank-one G reference limitation](hybrid_parameters.md) also remains: some
reference paths construct a nonexistent finite Z, while direct wave equations
are valid. The corresponding file test uses its independent closed form.
Reference scikit-rf remains test-only with its existing BSD-3-Clause notices.
No runtime dependency, saved schema, physical field model, application or
platform support is added. Network algebra has no spatial convergence claim.
