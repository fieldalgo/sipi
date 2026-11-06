# Full-matrix forward-wave propagation

[Differential/common coordinates](mixed_characteristic.md) retain the full coupling matrix for a pair.

`rlgc_characteristic(frequency, R=..., L=..., G=..., C=..., names=None)` computes
forward-wave matrices in the **original conductor voltage/current coordinates**.
It supports asymmetric reciprocal multiconductor RLGC without projecting onto
an even/odd pair. Inputs are the same real symmetric PSD R/G and PD L/C used by
`rlgc_network`, either `(N,N)` or `(F,N,N)`. Frequencies must be strictly positive
and increasing; DC is excluded. SI units and `exp(+jωt)` apply.

With series impedance `Z=R+jωL` and shunt admittance `Y=G+jωC`, the result satisfies:

```
Gamma_v^2 = Z Y
Zc = Gamma_v^-1 Z,  Yc = Zc^-1
dV/dz = -Gamma_v V
I(z) = Yc V(z)
V(z) = exp(-Gamma_v z) V(0)
```

Here z is distance along the line, distinct from transverse mesh x/y. Current I
is positive toward +z; a finite network's far-port current points into the line
and therefore equals `-I(length)` under its port convention.

`LineCharacteristic` holds copied read-only `frequency`, conductor `names`, and
three `(F,N,N)` arrays: `gamma_voltage` in 1/m, `z_characteristic` in ohms and
`y_characteristic` in siemens. `voltage_transfer(length)` returns the read-only
matrix exponential for a finite nonnegative length in metres.

These are **matrices**, not scalar characteristic impedances for each conductor.
Their diagonal entries are not generally mode impedances or propagation constants.
The transfer assumes a pure forward wave; it is not S21, a terminal source solve,
or a reflected finite-line solution. Use `rlgc_network` for finite-port networks
with their explicit reference impedances. General matrix Zc is not a diagonal
load dictionary for the circuit termination API.

## Example

```python
import numpy as np
from sipi import rlgc_characteristic

result = rlgc_characteristic(
    [1e6, 1e8, 1e9],
    R=[[2, .2], [.2, 3]],
    L=np.array([[400, 60], [60, 300]])*1e-9,
    G=[[.002, -.0003], [-.0003, .003]],
    C=np.array([[100, -15], [-15, 80]])*1e-12,
    names=('first', 'second'),
)
transfer = result.voltage_transfer(.02)
initial_voltage = np.array([1+0j, 0j])
voltage = transfer @ initial_voltage
current = np.einsum('fij,fj->fi', result.y_characteristic, voltage)
power = .5*np.einsum('fi,fi->f', voltage.conj(), current).real
assert np.all(power >= 0)
```

`TransmissionLineResult.characteristic()` and `VolumeLineResult.characteristic()`
reuse the already extracted RLGC and conductor names. They perform no additional
field solve. A saved line with tilted principal-axis materials can use this API
even when its matrices fail the existing scalar mode symmetry contract.
The separate `propagation()`/`rlgc_propagation` API still accepts only single or
strictly exchange-symmetric paired modes and retains its scalar attenuation split.
This addition does not label or track general modes or assign per-mode loss shares.

## Branch, conditioning and passivity

The physical branch is evaluated as `Gamma_v = j sqrt(-Z Y)` after separately
scaling Z and Y. This avoids the negative-real branch cut of `sqrt(Z Y)` at an
exactly lossless line. The lossless root problem is kept real, so its propagation
matrix has exactly zero real part in the checked cases. No eigenvector sorting or
inversion is needed; repeated and nearby propagation roots are supported.

The implementation uses SciPy's matrix square root and linear solves. It rejects
condition numbers above `1e12`, nonfinite/unrepresentable values, and relative
square-root, constitutive, inverse or reciprocity residuals above `1e-10`.
Only accepted reciprocity roundoff is averaged. There is no pseudoinverse,
regularization, diagonal projection or implicit symmetrization of an asymmetric
line. The real parts of Zc/Yc must be positive definite. Forward eigenvalues need
positive phase and nonnegative attenuation within the stated numerical roundoff.
Very ill-conditioned or unrepresentable cases are rejected rather than certified.

For a pure forward wave, let `H=(Yc+Yc^H)/2`. Its average power is
`P=V^H H V/2` and the exact local power identity is

`Gamma_v^H H + H Gamma_v = Yc^H R Yc + G`.

The right side separates conductor and dielectric **power forms**. It is not an
entrywise or per-mode scalar attenuation decomposition. Voltage Euclidean norm
can increase through interference even when this physical power decreases.
The lossless case conserves this power metric under forward transfer.

## Independent verification and limits

```sh
python -m pytest -q -s tests/sipi/test_characteristic_matrix.py tests/sipi/test_propagation.py
```

Independent scikit-rf 2.2.0 `DistributedCircuit` scalar solutions are transformed
by a known nonorthogonal real T into asymmetric three-conductor problems:
`Z=T diag(z) T^T`, `Y=T^-T diag(y) T^-1`. The exact matrix results are
`Gamma=T diag(gamma) T^-1` and `Zc=T diag(zc) T^T`. Gamma, Zc and voltage transfer
must agree within normwise relative `1e-10`, for lossy and lossless cases.

Other checks cover scalar and differential/common normalization, repeated and
nearby roots, independent SPD forms, power conservation/dissipation, the full
block telegrapher exponential, transfer composition, conductor-coordinate changes,
permutations, per-frequency inputs, snapshots and rejection gates. Common RLGC
scales from `1e-200` to `1e200` check normalization without forming an overflowing
physical ZY product. These are numerical stress cases, not material validity ranges.
Actual asymmetric tensor shared-mesh and volume lines check diagnostic integration.

This is uniform-line RLGC algebra. It does not improve the underlying mesh,
material calibration, conductor approximation or quasi-TEM validity. It does not
model 3D transitions, radiation, nonreciprocal media, time-domain mode tracking,
new operating-system support or a browser/portable interface.

[Scalar mode propagation](propagation.md) · [Networks](network.md) ·
[Saved lines](line_model.md) · [한국어](../../locales/ko/pages/packages/sipi/characteristic.md)
