# Distinct forward modes and sampled-frequency tracking

`rlgc_modes` uses the existing [full-matrix characteristic solution](characteristic.md)
to find distinct forward modes of reciprocal passive RLGC. It normalizes each
mode to **one watt of forward time-averaged power**, separates its conductor and
dielectric attenuation, and tracks labels across the supplied frequencies.

```python
import numpy as np
from sipi import rlgc_modes

result = rlgc_modes(
    np.logspace(4, 9, 21),
    R=[[2, .2], [.2, 3]], L=np.array([[400, 60], [60, 300]])*1e-9,
    G=[[.002, -.0003], [-.0003, .003]], C=np.array([[100, -15], [-15, 80]])*1e-12,
    names=("first", "second"),
)
print(result.gamma[-1])
print(result.alpha_conductor[-1], result.alpha_dielectric[-1])
print(result.overlap.min())
voltage = result.voltage[-1, :, 0]  # conductor voltages for tracked mode zero
current = result.current[-1, :, 0]
assert abs(.5*np.vdot(voltage, current).real-1) < 1e-10
```

Inputs have the characteristic API's real symmetric PSD R/G, PD L/C and strictly
positive increasing frequencies. SI units, peak phasors and `exp(+jωt)` apply.
`TransmissionLineResult.modes()` and `VolumeLineResult.modes()` reuse extracted
RLGC without another field solve. Geometry, material and line JSON are unchanged.

## Arrays, power and interpretation

`LineModes` copies and freezes its arrays. `frequency` is in Hz; `names` identifies
**conductor coordinates**, not mode labels. A column index identifies a mode:

| Array | Shape | Meaning |
|---|---|---|
| `gamma` | (F,N) | amplitude attenuation + j phase constant, 1/m |
| `voltage`, `current` | (F,N,N) | conductor rows, mode columns; V/A at reference section |
| `alpha_conductor`, `alpha_dielectric` | (F,N) | single-mode amplitude attenuation contributions, Np/m |
| `overlap` | (F,N) | assigned adjacent-sample power overlap |
| `assignment_gap` | (F,) | best minus second-best total assignment score |

For each column, `Gamma_v V = gamma V`, `I = Yc V` and
`P = Re(V.conj().T @ I)/2 = 1 W`. The exact single-mode identity is

```text
alpha_conductor = Re(I^H R I)/(4 P)
alpha_dielectric = Re(V^H G V)/(4 P)
alpha_conductor + alpha_dielectric = Re(gamma)
```

Use `20/log(10)` to convert amplitude Np/m to dB/m. The split is for the **same
loaded traveling mode**; it is not the difference between two independent
conductor-only/dielectric-only network insertion losses. Modes need not be
orthogonal under power, so superposed modes can have interference terms. Do not
sum their individual powers as if all cross terms vanished. No unique scalar
modal impedance or differential/common identity is assigned to an asymmetric mode.
Finite-terminal networks and reflections still use the network/circuit APIs.

## Label continuation and rejection gates

At the first frequency, sort by increasing imaginary gamma, then real gamma.
The largest voltage entry fixes the initial phase to real positive. Thereafter,
let `H = (Yc+Yc^H)/2` and use the mean of adjacent H matrices. The normalized
absolute H inner product defines the overlap of each old/new voltage vector.
An optimal one-to-one assignment maximizes their total score. Each new phase
makes its assigned complex overlap real positive; power normalization follows.
This metric is invariant under a fixed real power-dual conductor-coordinate
change. The first overlap/gap entries are one because there is no prior sample.

Repeated or near roots (minimum separation at most `1e-8*max(abs(gamma))`),
eigenvector condition above `1e10`, overlap below 0.7, or best/second-best total
score gap at most `1e-6` raise `ModeTrackingError` with `index` and `frequency`.
Refine the frequency grid for an unresolved assignment. No result silently
chooses a label through degeneracy. The full-matrix characteristic API remains
available for degenerate cases. Its original branch/conditioning gates still apply.

Modal equation and power-balance residuals are checked to `1e-10` relative to
their full equation/propagation scale. Nonrepresentable normalization or negative
computed loss is rejected without clipping. Input PSD acceptance near roundoff
does not guarantee that this stricter opt-in modal calculation will accept it.
One-watt power error must remain below `1e-10`.

Tracking describes **the supplied samples**. It does not prove unique physical
mode identity between samples, detect every unsampled crossing, track a degenerate
subspace, fit materials, certify mesh accuracy or provide time-domain evolution.
The first ordering need not remain phase-speed order after a crossing.

## Independent validation

Scikit-rf 2.2.0 scalar `DistributedCircuit` modes are transformed with a known
nonorthogonal real matrix into an asymmetric three-conductor line. Lossy and
lossless gamma, modal power/loss split and reconstructed forward transfer agree
within `1e-10`. A separate full block-telegrapher exponential checks noncommuting
RLGC forms. Tests cover crossings between samples, rejected degeneracies and
ambiguous/low-overlap rotations, successful finer sampling, phase alignment,
power-dual coordinate changes and exact lossless contributions. Actual asymmetric
tensor-dielectric shared-mesh and finite-metal results verify that diagnostics do
not start another field solve. These are algebra and adapter checks, not new
physical geometry or measured-device validation. No runtime dependency is added.

[한국어](../../locales/ko/pages/packages/sipi/modes.md)
