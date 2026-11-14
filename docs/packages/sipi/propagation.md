# Traveling-wave propagation and loss contributions

`rlgc_propagation(frequency, R=..., L=..., G=..., C=...)` accepts the same real
reciprocal passive RLGC matrices as `rlgc_network`, at strictly positive Hz.
It supports a single conductor or an exchange-symmetric pair. Every paired
matrix must have equal diagonals to relative `1e-12` of its matrix scale at
each sample. General asymmetric modes are rejected; finite-mesh near-symmetry
does not authorize implicit averaging. No eigensystem mode tracking is inferred.

```python
from sipi import rlgc_propagation

p = rlgc_propagation([1e6, 1e9], R=[[2]], L=[[400e-9]], G=[[.002]], C=[[100e-12]])
print(p.z_characteristic, p.gamma)
print(p.conductor_db_per_m, p.dielectric_db_per_m, p.attenuation_db_per_m)
```

Arrays are immutable `(frequency, mode)` samples. Modes are `single` or
`differential, common`. For pairs, Vd=V1−V2 and Id=(I1−I2)/2; Vc=(V1+V2)/2 and
Ic=I1+I2. Differential series R/L are twice the odd eigenvalues, shunt G/C half;
common series R/L are half the even eigenvalues, shunt G/C twice. Thus reported
impedances are physical differential/common impedances, not per-conductor odd/even
impedances. Positive-frequency `TransmissionLineResult.propagation()` and
`VolumeLineResult.propagation()` reuse existing extracted matrices without a new
field solve and retain all those extraction models' validity limits.

With exp(+jωt), z=R+jωL and y=G+jωC, the passive branches give
gamma=sqrt(z y), Zc=sqrt(z/y), alpha=Re(gamma), beta=Im(gamma).
Exact traveling-wave dissipated-power contributions are

```
alpha_conductor = R / (2 Re(Zc))
alpha_dielectric = G |Zc|² / (2 Re(Zc))
alpha_conductor + alpha_dielectric = alpha
```

These are Np/m. `*_db_per_m` multiply amplitude attenuation by 20/ln(10).
`phase_velocity` is ω/beta in m/s, not group or information velocity. This is
exact modal power balance, not the low-loss approximation. The contributions
use the **same total lossy mode**; separately setting R or G to zero would change
that mode. Finite-length `-20 log10|S21|` additionally includes port mismatch and
reflections and generally differs from propagation attenuation times length.

DC is deliberately excluded, including ambiguous zero-product traveling-wave
limits. Use existing network/volume APIs for DC circuit behavior. Invalid
matrices, unsupported modes and nonfinite intermediate scales are rejected.
The feature supplies no new material fit, roughness law or quasi-TEM guarantee.

Validation uses lossless impedance/phase, exact distortionless R/L=G/C,
single-loss zeros and high-loss power balance, at relative `1e-10` or tighter.
scikit-rf 2.2.0 DistributedCircuit gamma/Zc comparisons cover single and
differential/common modes at maximum relative error `1e-10`; optional records
use `OPENPHYSICS_CROSSCHECK_DIR`. Surface/volume extraction checks confirm reuse
of their RLGC and exclude DC; they do not establish new absolute field accuracy.

[Networks](network.md) · [한국어](../../locales/ko/pages/packages/sipi/propagation.md)

[Full-matrix forward-wave diagnostics](characteristic.md) support asymmetric reciprocal RLGC without changing the scalar-mode contract.

[Effective shunt-loss inference from known RLC](loss_inference.md)
