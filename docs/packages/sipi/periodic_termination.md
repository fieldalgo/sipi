# Periodic Thevenin sources and finite terminations

[Saved circuits and common execution](periodic_circuit.md) preserve sources, loads and diagnostics together.

`periodic_terminated_response` solves named real periodic source voltages with
finite source/load impedances. It uses the existing harmonic
`terminate_network` feedback solve and the [periodic grid contract](periodic.md).
Unlike a supplied incident wave, a Thevenin voltage does not prescribe the
incident wave independently of reflected waves and source impedance.

## Inputs and normalization

- `network`: a `LineNetwork` with exactly real DC S and uniform frequencies
  starting at 0 Hz. There are `F >= 2` harmonics and `N = 2*F-1` real time samples.
  The same `1e-12*f[-1]` grid tolerance and representable period checks apply.
- `source_voltages`: a nonempty mapping from actual port names to real constants
  or real arrays of length N, in V. A constant means a DC source throughout the
  period; omitted ports have zero source voltage. Booleans/nonfinite/complex
  time values and unknown ports are rejected.
- `terminations`: finite passive impedances, in ohms, keyed by actual port
  names. A value is a complex scalar or F complex frequency samples; every
  sample must have nonnegative real part and **DC must be exactly real**.
  Omitted values use each port's real reference impedance. A zero impedance
  is allowed; infinite/open loads are not. Use an explicitly modeled source
  network or port reduction when an open boundary is needed.

Every impedance includes the series source/load impedance at that port.
Current is positive into the network, so `Vs = V + Vdrop`. Mixed-mode inputs
apply to the mode ports and their actual references; they do not automatically
infer a physical single-ended source circuit.

The source transform uses `rfft(..., norm='forward')`, then doubles **only**
positive-frequency coefficients. This produces DC means and positive-frequency
**peak phasors**, exactly the existing harmonic circuit convention. Inverse
transforms halve positive-frequency phasors and use the odd N. There is no
Nyquist bin. DC factors are unchanged. Thus harmonic power at DC uses no
factor of one half, while positive-frequency peak power does.

## Example: DC plus AC voltage divider

```python
import numpy as np
from sipi import LineNetwork, periodic_terminated_response

frequency = np.arange(5)*1e6
count = 2*len(frequency)-1
source = .2+np.cos(2*np.pi*np.arange(count)/count)
# A 100-ohm one-port at a 50-ohm wave reference.
network = LineNetwork(frequency, np.full((5, 1, 1), 1/3), 50., ('port',))
result = periodic_terminated_response(network,
    source_voltages={'port': source}, terminations={'port': 50.})
np.testing.assert_allclose(result.response.voltage[:, 0], source*2/3,
                           atol=1e-12, rtol=0)
mean_power = np.mean(result.response.voltage*result.response.current)
np.testing.assert_allclose(mean_power,
    result.frequency_solution.network_power.sum(), atol=1e-12, rtol=0)
```

## Results and validation limits

`PeriodicTerminatedResponse` retains:

- `source_voltages` and `termination_voltages`: read-only real arrays [V],
  time by port. For frequency-dependent Z, the series drop is reconstructed
  from `Z[k]*I[k]`; it is not a pointwise product of a frequency table and a
  time waveform.
- `response`: the read-only `PeriodicResponse` time grid, incident/reflected
  real power waves [sqrt(W)], V/I, references, names and basis.
- `frequency_solution`: the original `TerminatedNetwork`, including DC/peak
  source and solution phasors, actual impedance table, condition numbers and
  normalized KVL/wave residuals. Its power properties are per-frequency
  averages. **Sum across frequencies**, not average across them, to compare
  with time-average source/network/termination powers over one period.

The existing `1e12` circuit condition-number and `1e-10` normalized residual
gates are unchanged. Singular feedback, complex DC, invalid numeric scales
and other failures raise; no partial frequency subset is returned. An all-zero
drive does not excuse an ill-defined circuit. The source/network snapshots and
output arrays are retained without modifying the caller's arrays.

Tests check DC and DC-plus-AC dividers, matched-line delay, ideal zero source
impedance, zero drive, coupled RLGC single/mixed bases, superposition and shift.
An analytic RL termination checks `Vdrop = R*I + L*dI/dt` for represented
harmonics. Time KVL, `V*I = a*a-b*b` and time/harmonic power balance agree to
absolute `1e-12`. Independent finite harmonic sums and SciPy 1.18.1
(BSD-3-Clause) V/I block systems, plus scikit-rf 2.2.0 (BSD-3-Clause) impedance
circuits, check nonreciprocal multiports with unequal references and complex
RL loads to `1e-12` V/A. These comparisons do not validate field extraction.

This is sampled periodic steady state. Neither real DC nor passive impedance
samples prove a causal/stable broadband load. There is no missing-frequency
inference, isolated startup transient, TDR/eye/BER result, automatic crosstalk
peak definition or new measured/material/geometry accuracy claim. JSON and
application support are separate; this unit adds a Python API.

[Periodic saved inputs](periodic_document.md) · [한국어](../../locales/ko/pages/packages/sipi/periodic_termination.md)
