# Network connection and known-fixture removal

`cascade_networks(left, right)` connects left far ports to right near ports in
conductor order. Inputs are single-ended `LineNetwork` objects with **all near
then all far** 2N-port ordering. Names label ports; they do not determine wiring.
Frequency arrays and connected references must match exactly. Use
`renormalized(...)` explicitly before connection when needed.

```python
from sipi import cascade_networks, deembed_network

# left_fixture, device and right_fixture are known LineNetwork objects.
measured = cascade_networks(cascade_networks(left_fixture, device), right_fixture)
recovered = deembed_network(
    measured, left=left_fixture, right=right_fixture,
    port_names=device.port_names,
)
```

`deembed_network` removes one or both supplied **known** fixtures in the order
left fixture → device → right fixture. The right fixture must already have this
orientation; it is not reversed implicitly. Fixture outer references must match
the measured ends. Recovered references come from fixture inner ports, or the
measured end without a fixture. This is not fixture estimation or calibration.

Names default to retained outside ports for cascade and exposed inside ports for
removal. Provide unique `port_names` when names collide. Arrays are copied and
immutable; inputs are unchanged. Mixed-mode inputs are rejected: their documented
d-near/d-far/c-near/c-far order is not all-near/all-far. No interpolation,
automatic renormalization, passivity correction or noise suppression occurs.

## Numerical contract and checks

Cascade solves scattering feedback directly. Removal uses wave-chain matrices
defined by `[a_near; b_near] = T [b_far; a_far]` and linear solves on both sides.
It does not invert S: a series resistance of twice the port reference has
singular S but is removable. Forward-transmission, wave-chain and recovered
incident systems must be finite, nonsingular and have 2-norm condition <= `1e12`.
Cascade feedback has the same guard. This conservative floating-point check is
**not an accuracy guarantee**. Strong attenuation and measurement uncertainty
can destroy information below this limit too. Deep attenuation and singular
fixtures are rejected, without regularization; absent information is not restored.

Analytic series-resistance addition/ideal throughs use `1e-12`; uniform RLGC
length addition and known-device recovery use `1e-10`. Nonreciprocal/noncommuting
2-/4-port samples are compared with scikit-rf 2.2.0 cascade/inverse operations at
maximum absolute S difference `1e-10`. Tests cover unequal real references,
left/right/both removal, metadata rejection, opaque fixtures and singular
feedback. `OPENPHYSICS_CROSSCHECK_DIR` enables independent comparison records.
These validate network algebra, not measured fixture or material accuracy.

[Network model](network.md) · [Touchstone input](touchstone.md)
