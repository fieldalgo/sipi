# Current sources and open terminal boundaries

[Mixed terminal boundaries](mixed_termination.md) combine ideal voltage/short and open/current ports in one solve.

[Saved Norton circuits](norton_circuit.md) add a separate versioned input and shared execution contract.

`terminate_norton_network` solves explicit Norton sources on a `LineNetwork`,
retaining voltage and current at **every** port, including opens. It accepts
the network's actual port names, ordering, basis and positive real references.
No source location, victim port or topology is inferred.

The terminal condition is `I + Y*V = Is`, where I points **into the network**,
Is is source current in amperes, Y is parallel source/load admittance in siemens,
and V is terminal voltage in volts. Inputs are finite complex scalars or one
sample per network frequency. `source_currents` must be a nonempty mapping;
omitted source currents are zero. `termination_admittances` defaults each
omitted port to `1/Zref`. Admittance must be passive at each sample (`Re(Y)>=0`).

- `Y=0, Is=0` is an open terminal, with its voltage retained.
- `Y=0, Is!=0` is an ideal current source.
- Finite nonzero Y is externally equivalent to Thevenin `Vs=Is/Y, Zt=1/Y`.
- A short/ideal voltage source uses the existing [Thevenin API](termination.md)
  with zero series impedance. Infinite admittance is not accepted.

No large impedance substitutes for an open. Open current is obtained from the
solved waves and checked by the circuit residual; it is not clipped to zero.
Reactive admittance samples are accepted, but per-sample passivity does not
certify causality or stability of a supplied network/load model.

```python
import numpy as np
from sipi import rlgc_network, terminate_norton_network

network = rlgc_network([1e8, 2e8, 5e8], R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length=.1)
result = terminate_norton_network(network,
    source_currents={'near:1': .002},
    termination_admittances={'near:1': .02, 'far:1': 0.})
assert result.port_names == ('near:1', 'far:1')
assert np.max(abs(result.current[:, 1])) < 1e-12
assert np.max(abs(result.source_power-result.network_power-result.termination_power)) < 1e-12
```

## Solution and power contract

`NortonTerminatedNetwork` contains a snapshot of the network and read-only
`source_currents`, `termination_admittances`, `a`, `b`, `voltage` and `current`
arrays with shape `(frequencies, ports)`. The condition number, KCL residual and
wave residual have one value per frequency. Power properties also return
read-only per-frequency arrays in watts:

| Property | Sum over ports, before frequency weight |
|---|---|
| `network_power` | `Re(V*conj(I))` |
| `termination_power` | `Re(V*conj(Y*V))`, the parallel dissipation |
| `source_power` | `Re(V*conj(Is))`, the ideal current-source delivery |

DC weight is 1; positive-frequency **peak phasors** use 1/2. Conservation is
`source_power = network_power + termination_power`. A supplied active S matrix
can have negative network power; this API does not certify its passivity.

Source conversion preserves external V/I, waves and network power. It **does
not** preserve internal ideal-source power or series-versus-parallel resistor
dissipation: Thevenin and Norton internal power properties must be interpreted
in their own circuit topologies. They each satisfy their own conservation law.

The solver uses `a=gamma*b+drive`, with
`gamma=(1-Y*Zref)/(1+Y*Zref)` and `drive=Is*sqrt(Zref)/(1+Y*Zref)`.
It rejects singular/floating feedback, condition number above `1e12`, or
normalized KCL/wave residual above `1e-10`. It does not repair inconsistent
ideal-source constraints. Finite inputs whose intermediate values, solutions
or requested power exceed floating-point representability are also rejected.
An all-zero drive still requires a uniquely solvable boundary problem.

## Validation scope

Analytical checks cover RC current division, an ideal current source, a
lossless line with an open far end (`Zin=-j Z0 cot(beta*l)`), superposition,
DC/positive-frequency power weights, and the external Thevenin equivalence.
Actual coupled RLGC networks are checked in conductor and mixed bases, with
reference changes preserving V/I. Gates are absolute/relative `1e-12` as
appropriate for the explicit synthetic fixtures.

Independent SciPy 1.18.1 (BSD-3-Clause) nodal solves use the physical RLC pi
circuit's analytical admittance; scikit-rf 2.2.0 (BSD-3-Clause) separately
converts S to Y and solves the loaded circuit. Maximum V/I differences are
below `3.470e-17 V`/`1.698e-18 A`, within the `1e-12` absolute gate. Tests
retain invalid inputs, singular/floating and ill-conditioned boundaries,
numeric/power overflow and read-only input snapshots.

This is a circuit-algebra API, with no new field mesh or extraction model.
The API itself adds no saved schema, time-domain integration, measured
accuracy or application/platform acceptance. Existing finite Thevenin inputs
and the separate port-reduction API remain supported.

[Network](network.md) · [한국어](../../locales/ko/pages/packages/sipi/norton_termination.md)
