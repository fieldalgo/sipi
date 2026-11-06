# Differential/common characteristic coordinates

`LineCharacteristic.mixed_mode()` expresses the complete forward-wave matrices
of a two-conductor pair in differential/common coordinates. The first conductor
is positive and the second negative; names do not infer polarity. The method
requires two single-ended coordinates and rejects repeated conversion.

```python
import numpy as np
from sipi import rlgc_characteristic

line = rlgc_characteristic([1e6, 1e9],
    R=[[6, .4], [.4, 11]], L=np.array([[400, 80], [80, 310]])*1e-9,
    G=[[.004, -.001], [-.001, .006]], C=np.array([[100, -20], [-20, 130]])*1e-12,
    names=('plus', 'minus'))
mixed = line.mixed_mode()
assert mixed.basis == 'mixed-mode'
assert mixed.names == ('differential', 'common')
mixed.z_characteristic      # Full (F,2,2) impedance, including coupling.
mixed.voltage_transfer(.01) # Forward voltage transfer over 1 cm, not finite-line S21.
```

The voltage and forward-current definitions are:

```
Vd = V1 - V2          Id = (I1 - I2)/2
Vc = (V1 + V2)/2      Ic = I1 + I2
```

They preserve complex power: `V1 conj(I1)+V2 conj(I2) = Vd conj(Id)+Vc conj(Ic)`.
For voltage transform A and current transform B=A^(-T), the matrices are
`Gamma_m=A Gamma_v A^(-1)`, `Z_m=A Zc A^T`, `Y_m=B Yc B^T`.
The output obeys the same `dV_m/dz=-Gamma_m V_m`, `I_m=Y_m V_m` and
`V_m=Z_m I_m` laws, in differential/common order. Units, positive-frequency
requirement, +z current direction and `exp(+j omega t)` are unchanged.

This is a **coordinate change**, not eigenmode extraction or tracking. An
asymmetric pair can have nonzero off-diagonal Z/Y/Gamma: a pure differential
current launch may produce common voltage, and differential/common content can
mix along the line. No off-diagonal entry is discarded or symmetry inferred.
`Z_m[0,0]` is the differential voltage/current ratio at a forward-wave launch
with `Ic=0`; it is not generally an isolated differential eigenmode impedance.
Only an exchange-symmetric pair reduces to the existing diagonal differential
and common modes, with `Zdiff=2 Zodd` and `Zcommon=Zeven/2`.

`LineCharacteristic.basis` defaults to `single-ended`, preserving the existing
five-argument constructor. `mixed-mode` requires two coordinates. Arrays are
copied/read-only and new output names are `differential`, `common`; the source
keeps its conductor names and arrays. Existing finite, reciprocity, positive-real,
inverse-residual, forward-root and condition-number gates validate the converted
matrices too. Unrepresentable conversion raises an error without rescaling the
physical outputs or returning a partial result.

Both shared-mesh and finite-volume line results support
`result.characteristic().mixed_mode()` without another field solve. Saved line
JSON is unchanged. The scalar `propagation()` API still rejects asymmetric pairs;
this coordinate view does not turn them into independent even/odd modes.
Study/goal `z_diff` retains its existing symmetric quasi-static definition.
The separate `LineNetwork.mixed_mode()` converts finite-line S and uses its own
four-port ordering; this method works on two forward voltage/current coordinates.

Independent scikit-rf generalized mixed-wave conversion of the same impedance
matrices checks Z/Y to normwise relative `1e-10`, for lossy and lossless asymmetric
pairs. Symmetric scalar-mode limits, complex-power conservation, constitutive
laws, polarity reversal and forward-transfer checks use `1e-12`; separately
transformed RLGC reproduces all matrices within `1e-10`. Tests retain nonzero
cross terms, reject unsupported counts/bases and verify both line extraction
results without new meshing. These check normalization and algebra; the original
field, mesh/domain, RLGC and material validity requirements still apply. No
measured laminate, modal tracking, new physical solver or platform is validated.

[Full matrices](characteristic.md) · [한국어](../../locales/ko/pages/packages/sipi/mixed_characteristic.md)
