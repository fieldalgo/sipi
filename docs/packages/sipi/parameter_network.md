# Physical impedance and admittance samples

**English** | [한국어](../../locales/ko/pages/packages/sipi/parameter_network.md)

`impedance_network(frequency, impedance, *, z_ref, names=None)` and
`admittance_network(frequency, admittance, *, z_ref, names=None)` convert
explicit physical Z or Y matrices to the immutable [LineNetwork](network.md).
Z is in ohms, Y in siemens and frequency in Hz. Currents point into the network;
phasors use exp(+j omega t). The caller supplies the physical port order.

```python
import numpy as np
from sipi import impedance_network

frequency = [0., 1e6, 1e8]
impedance = np.array([[[120.]], [[120.+2j]], [[120.+200j]]])  # ohms
network = impedance_network(frequency, impedance, z_ref=50., names=['terminal'])
assert network.s.shape == (3, 1, 1)
assert abs(network.s[0, 0, 0] - 70/170) < 1e-12
```

Each input requires exact shape `(F,N,N)` with N positive. There is no constant
matrix broadcasting or scalar shortcut, including for one port. Frequencies
must be finite, nonnegative and strictly increasing. Entries may be real or
complex, finite and nonsymmetric; booleans and strings are rejected.
`z_ref` is required: a finite positive real scalar or one value per port,
constant across frequency. Complex and frequency-dependent references are not
accepted. Names are unique nonempty single-line strings, one per port; default
names are `port1`, `port2`, etc. Output basis is single-ended, with detached
read-only arrays. Successful conversion does not certify passivity, reciprocity,
causality, measurement provenance or a line/material model. Active inputs can
produce S magnitudes above one.

```python
from sipi import admittance_network

# A resistor between two terminals has a rank-one admittance matrix.
y = np.array([[[1., -1.], [-1., 1.]]])/37.  # siemens
series = admittance_network([0.], y, z_ref=[50., 50.], names=['left', 'right'])
assert abs(series.s[0, 1, 0] - 100/137) < 1e-12
opened = admittance_network([0.], np.zeros((1, 2, 2)), z_ref=50.)
assert np.array_equal(opened.s[0], np.eye(2))
```

With `D = diag(sqrt(z_ref))`, the normalized physical matrix is
`A = D^-1 Z D^-1` for impedance or `A = D Y D` for admittance. Conversion uses
`S = (A-I)(A+I)^-1` or `S = (I-A)(I+A)^-1`, respectively. A right solve uses
ordinary transpose, not conjugate transpose. Neither Z nor Y is inverted, so
rank-deficient physical matrices can remain valid: zero Z gives exact shorts
and zero Y gives exact opens. The independent definitions are documented by
[scikit-rf z2s](https://scikit-rf.readthedocs.io/en/latest/api/generated/skrf.network.z2s.html)
and [y2s](https://scikit-rf.readthedocs.io/en/latest/api/generated/skrf.network.y2s.html).

At each frequency, scale A and I by
`max(1, max(abs(Re(A))), max(abs(Im(A))))` before forming the wave denominator.
Reject its smallest singular value when it is at most
`1e-12 * max(1, largest singular value)`. This gate detects a nearly cancelling
scalar denominator as well as matrix ill-conditioning. It is conservative;
some extreme but finite passive inputs are refused. Nonfinite normalization,
solutions or residuals are rejected, as is a normalized solve residual above
1e-10. There is no pseudoinverse, eigenvalue clipping or data repair. Large
finite inputs are supported only when these intermediate scales remain
representable. Conversion gates are not a bound on measurement error.

These functions do not parse [Touchstone](touchstone.md). In particular, do not
pass normalized file entries as physical ohms or siemens. The existing
Touchstone importer continues to accept only its documented S subset.

Verification in `tests/sipi/test_parameter_network.py` includes 1–4 ports,
nonreciprocal, reciprocal, diagonal and rank-one matrices at unequal references:
32 independent scikit-rf 2.2.0 comparisons require absolute S difference <=1e-12.
Physical V=ZI / I=YV wave reconstruction requires relative residual <=1e-10.
Scalar R/L/C limits, independent loaded KCL, exact open/short, permutation,
reference change, consistent unit scaling, copied arrays and strict failure
gates are covered separately. This algebraic conversion has no mesh or exterior
boundary to refine. Existing field and propagation solvers are unchanged.
The BSD-3-Clause reference remains test-only; no runtime dependency is added.
