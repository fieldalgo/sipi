# Named connections and ideal junctions

`connect_networks(left, right, connections)` joins explicit pairs of port names
from two single-ended `LineNetwork` objects. Each pair is `(left_name, right_name)`;
each port may be connected once. There must be at least one connection and one
external port. There is no inferred wiring from names or near/far order.

Frequencies and the positive real references of connected ports must match
**exactly**. Use `renormalized(...)` explicitly first if required. Output order is
the remaining left ports followed by the remaining right ports, retaining their
references. Supply `port_names=[...]` for the output if retained names collide.
Inputs remain unchanged and result arrays are read-only. Mixed-mode inputs,
same-network connections, frequency interpolation and implicit reference changes
are outside this API.

`ideal_junction(frequency, port_names=[...], z_ref=...)` creates a zero-length node
with at least two single-ended ports. All terminals share the same electrical
ground and voltage, and currents directed into the node sum to zero. References
can differ. Its real symmetric scattering matrix is `S=2uuᵀ−I`, where
`uᵢ=(1/sqrt(Zᵢ))/sqrt(sum(1/Z))`. It is reciprocal and lossless, but a junction
with three or more equal-reference ports is **not matched** at each port.

## Example: a one-dimensional open shunt stub

```python
from sipi import ideal_junction, connect_networks, rlgc_network, terminate_ports

frequency = [0, 1e9, 5e9, 10e9]
junction = ideal_junction(frequency, port_names=['input', 'output', 'branch'])
stub = rlgc_network(
    frequency, R=[[0]], L=[[250e-9]], G=[[0]], C=[[100e-12]],
    length=.01, z_ref=50, names=['stub'],
)
joined = connect_networks(junction, stub, [('branch', 'near:stub')])
result = terminate_ports(joined, {'far:stub': 'open'})
# result.port_names == ('input', 'output')
touchstone_text = result.touchstone()
```

Here the line velocity is 2e8 m/s: the open 1 cm stub presents a shunt short at
5 GHz and a shunt open at 10 GHz. Changing the termination to `'short'` reverses
these limits. Finite passive complex impedances use the existing
`terminate_ports` contract. Eliminating the stub end before joining gives the
same circuit. A junction adds no physical parasitics, delay, radiation, pad,
via or return-current transition model. This is a **one-dimensional line circuit**,
not a three-dimensional via/stub field solution. Use line parameters only over
their material and quasi-TEM validity range.

## Numerical contract and validation

The combined input scattering matrix is block diagonal. Internal outgoing waves
are swapped into their connected partners: `(I−P Sii)ai = P Sie ae`. Linear solves
eliminate those internal waves without inverting S. Feedback condition number
must be at most `1e12`; normalized reconstruction residual at most `1e-10`.
Singular loops, nonfinite/unrepresentable outputs and incompatible metadata raise
errors, without regularization. These guards do not establish physical accuracy
or correct measurement noise. No passivity is inferred for arbitrary input S.

Tests compare unequal-reference junctions and simultaneous crossed connections
against scikit-rf 2.2.0 splitter/connect/innerconnect with maximum absolute S
difference `1e-10`. KCL, common voltage, reciprocity, unitarity, joined-node
equivalence and lossless open/short shunt-stub closed forms use `1e-12`. Stub
checks include DC, quarter-wave and half-wave limits for several line impedances.
A lossy finite-load stub is checked against its analytic input admittance and
independent network composition. Near/far wiring recovers existing cascade and
uniform-line length addition. Port order, references, immutable copies, invalid
wiring, singular/ill-conditioned loops and floating-point overflow are covered.
These are network-algebra checks; no FEM mesh-convergence or measured-board claim
is attached to an ideal junction.

The Python functions can consume networks from existing saved line inputs and
produce Touchstone. [NetworkAssemblyDocument](network_assembly.md) saves ordered
named wiring and ideal nodes, and feeds the existing transformations and circuits.

[Near/far composition](connection.md) · [Port loads](port_reduction.md) ·
[Network model](network.md) · [한국어](../../locales/ko/pages/packages/sipi/named_connections.md)
