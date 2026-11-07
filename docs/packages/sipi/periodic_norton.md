# Periodic current sources and open terminals

`periodic_norton_response` applies real current-source waveforms to a
`LineNetwork` with finite passive parallel admittances. It combines the
[Norton boundary solver](norton_termination.md) with the existing
[periodic grid and wave convention](periodic.md). Every port voltage/current,
including open terminals, is retained in the actual input network basis.

The frequency grid contains exactly real DC S and uniformly spaced harmonics
`f[k]=k*df`, with at least two frequency samples. For F frequencies, the real
waveform has odd length `N=2*F-1`, period `T=1/df` and spacing `dt=T/N`.
All supplied positive-frequency phases are retained; there is no Nyquist bin,
interpolation, window, missing-DC estimate or causality repair.

`source_currents` maps named ports to real scalar DC constants or N samples
in amperes. It must be nonempty; omitted sources are zero. Complex time samples
are rejected. `termination_admittances` maps ports to finite passive complex
scalars or F samples in siemens. Omitted admittances are `1/Zref`; the DC
admittance must be exactly real. `Y=0` is an ideal current source, or an open
when its source waveform is zero. Infinite admittance and string load names
are not accepted. Source/load definitions use the network's actual port basis.

```python
import numpy as np
from sipi import rlgc_network, periodic_norton_response

frequency = np.arange(5)*1e8
network = rlgc_network(frequency, R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length=.1)
t = np.arange(9)/9
source = .0008+.0004*np.cos(2*np.pi*t)+.0001*np.sin(4*np.pi*t)
result = periodic_norton_response(network, source_currents={'near:1': source},
    termination_admittances={'near:1': .02, 'far:1': 0.})
assert np.max(abs(result.response.current[:, 1])) < 1e-12
assert np.max(abs(result.source_currents-result.response.current-result.termination_currents)) < 1e-12
```

## Harmonics, currents and power

Real source samples are transformed to DC means and positive-frequency **peak
phasors**. Each harmonic uses the existing Norton relation `I+YV=Is` and its
condition/residual gates. Inverse synthesis returns real incident/reflected
waves, V/I and the shunt current from `Y(f)V(f)`. Reactive admittance is not a
pointwise multiplier of time samples. For a shunt G+C, its time current is
`G*V + C*dV/dt` for the supplied harmonic waveform.

`PeriodicNortonResponse` contains:

- `source_currents`: real N×P source samples [A].
- `termination_currents`: real N×P parallel-load current samples [A].
- `response`: the existing read-only `PeriodicResponse` time, waves, V/I,
  references, port names and basis.
- `frequency_solution`: `NortonTerminatedNetwork` with DC means, positive peak
  phasors, original admittances, diagnostics and per-frequency powers.

All computed arrays are read-only snapshots. At each time sample,
`source_currents = response.current + termination_currents`. Time-average
`sum(V*I)` equals the sum of harmonic network powers; analogous identities hold
for source and shunt powers. DC has power weight 1 and positive peak phasors
have weight 1/2. This harmonic sum is justified by this periodic grid; unrelated
frequency samples in a general Norton circuit are not summed this way.

The previous Thevenin periodic API retains its voltage-source and series-load
contract. Norton internal source/shunt powers describe a different topology
from Thevenin source/series powers even when external terminal behavior agrees.

## Acceptance and limits

Tests cover DC/AC resistor current division, ideal current sources, a shunt
capacitor's time derivative, the lossless open-line transmission identity
including DC, coupled RLGC in conductor/mixed bases, direct finite-harmonic
synthesis, superposition, circular shift, time/frequency power and snapshots.
Absolute/relative `1e-12` gates apply to the stated synthetic fixtures.

Independent SciPy 1.18.1 (BSD-3-Clause) analytical RLC nodal equations and
scikit-rf 2.2.0 (BSD-3-Clause) S→Y nodal circuits use explicit finite DFT and
synthesis, independently of the API FFT path. Maximum time V/I differences are
`2.429e-17 V`/`5.693e-19 A`, below the `1e-12` absolute gate. Source/sample
shape, passive admittance, exact-real DC, missing/nonuniform grid, floating
open and numeric overflow guards remain explicit. Harmonic feedback condition
above `1e12` or normalized residual above `1e-10` is rejected.

This is **periodic steady state**, not switching startup or an isolated pulse.
Circular wrapping, sampled bandwidth and original network/model validity still
apply. No causality, stability, measured-board accuracy or new field extraction
is established. This API adds no saved schema (43 remain) and no application
or Windows acceptance for the new path.

[Thevenin periodic sources](periodic_termination.md) · [한국어](../../locales/ko/pages/packages/sipi/periodic_norton.md)
