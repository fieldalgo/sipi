# Explicit passive port reduction

`terminate_ports(network, loads)` connects named ports to passive loads and
returns a `LineNetwork` for the remaining ports. The inputs are unchanged.
Unlike the driven terminal solver, this operation returns S-parameters for a
smaller network; it does not compute source voltages or terminal currents.

```python
from sipi import rlgc_network, terminate_ports
line = rlgc_network([0, 1e9, 5e9], R=[[0]], L=[[250e-9]], G=[[0]],
                    C=[[100e-12]], length=.01, z_ref=50, names=['trace'])
open_end = terminate_ports(line, {'far:trace': 'open'})
reflection = open_end.s[:, 0, 0]
```

Each `loads` entry is `'open'`, `'short'`, or a finite passive complex impedance
in ohms. Numeric values can be scalars or one-dimensional arrays with one value
per frequency; their real part must be nonnegative. Numeric zero is a short.
No implicit matched termination is added: unlisted ports are retained. The map
must load at least one port and leave at least one port. Unknown names, unknown
strings, negative resistance, boolean/nonfinite values and mismatched shapes
are rejected. Infinity is not an encoding for open.

Remaining ports keep the input order, frequency grid, positive real reference
impedances and `basis`. Mapping insertion order is irrelevant. Loads apply in
the stated basis: a load on a mixed-mode port is a modal load, not an inferred
pair of physical single-ended resistors. Returned arrays are copied/read-only.
References are not changed and frequency samples are not interpolated.

For loaded indices L and retained indices R, the reflection matrix Γ is diagonal
and the solve is `(I − Γ S_LL) a_L = Γ S_LR a_R`. The reduced matrix is
`S_RR + S_RL (I − Γ S_LL)^−1 Γ S_LR`; the implementation uses a linear solve,
not an explicit inverse. An open has Γ=1, a short Γ=−1 and a finite load uses
`Γ=(Zload−Zref)/(Zload+Zref)` with scaled evaluation to avoid overflow.
Singular feedback, 2-norm condition number >1e12, nonfinite solutions and
normalized residual >1e-10 are errors. There is no regularization or hidden
loss added to close an isolated resonance. Input S may be active; specifying
passive loads does not certify its passivity or causality.

`tests/sipi/test_port_reduction.py` separates the numerical checks:

- Matched lossless uniform line: `Γin=Γload exp(−2jβl)` to absolute 1e-12,
  including DC and quarter/half-wave open/short transformations.
- Ideal three-port junction: an open branch becomes through, a short branch
  becomes two isolated shorts, and a matched shunt has the analytic S matrix.
- Nonreciprocal five-port networks with unequal references and three simultaneous
  loads agree with sequential `scikit-rf.network.connect` (2.2.0) to absolute
  1e-10, in both declared bases. Passivity, order, snapshots, extreme finite
  scales, invalid inputs and singular/ill-conditioned feedback are checked.

These are sampled network and one-dimensional line identities, with no mesh to
refine. They do not resolve a 3D via, pad, antipad, return-current transition,
radiation or a physical stub discontinuity. Geometry-based line extraction
still needs its separate mesh and physical validity checks. This Python API
does not introduce a saved-input schema or change existing circuit JSON.

[Driven terminations](termination.md) · [Network connection](connection.md) ·
[한국어](../../locales/ko/pages/packages/sipi/port_reduction.md)
