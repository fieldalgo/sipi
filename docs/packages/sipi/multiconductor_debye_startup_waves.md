# Multiconductor Debye port waves

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_debye_startup_waves.md)

The existing `startup_port_waves(response, *, z_ref)` explicitly accepts
`MulticonductorDebyeRLGCLadderResponse` from the
[three/four-signal Debye circuit](multiconductor_debye_startup.md). It converts
the response's six/eight terminal voltage/current samples once, without
repropagating the circuit or changing its physical model.

```python
import numpy as np
from sipi import multiconductor_debye_rlgc_ladder_response, startup_port_waves

t = np.linspace(0., 4e-9, 41)
response = multiconductor_debye_rlgc_ladder_response(
    t, np.minimum(t/1e-9, 1.)[:, None]*[1., -.4, .2], signals=3,
    R=np.diag([20., 23., 26.]), L=np.diag([450., 480., 510.])*1e-9,
    G=np.diag([.002, .0022, .0024]), C_inf=np.diag([210., 220., 230.])*1e-12,
    delta_C=np.array([np.diag([130., 143., 156.])])*1e-12,
    relaxation_hz=[8e7], length=.1, cells=4,
    source_resistance=[25.]*3, load_resistance=[100.]*3)
waves = startup_port_waves(response, z_ref=[35., 45., 55., 65., 75., 85.])
assert waves.incident.shape == waves.reflected.shape == (41, 6)
assert waves.source_kind == 'MulticonductorDebyeRLGCLadderResponse'
np.testing.assert_array_equal(waves.voltage, response.voltage)
np.testing.assert_array_equal(waves.current, response.current)
```

References must be an explicit positive finite real vector of length2N,
constant in time. No scalar broadcasting, complex reference or inferred modal
impedance is accepted. Port order is all N near signals followed by all N far
signals; both terminal currents enter the line. Internal node/segment/source
arrays cannot substitute for terminal current. Existing response types keep
their prior admitted port counts.

The original formulas and relative1e-10 reconstruction/power gates are unchanged:
`a=(V/sqrt(Z)+I*sqrt(Z))/2`, `b=(V/sqrt(Z)-I*sqrt(Z))/2`, in sqrt(W).
Reconstructed V/I use each port's original maximum signal scale; power uses
the maximum wave-power scale rather than net power near cancellation.
Nonrepresentable values or failed reconstruction raise without clipping.

```python
np.testing.assert_allclose(
    waves.port_power.sum(axis=1),
    response.total_energy_rate + response.series_loss
    + response.shunt_loss + response.relaxation_loss,
    rtol=1e-10, atol=1e-12)
changed = startup_port_waves(response, z_ref=2*waves.z_ref)
np.testing.assert_array_equal(changed.port_power, waves.port_power)
assert max(waves.voltage_reconstruction_relative_error,
           waves.current_reconstruction_relative_error,
           waves.power_balance_relative_error) <= 1e-10
```

Total terminal power includes instantaneous and polarization energy rate plus
series, shunt and relaxation losses. Near power is source power minus source
resistor loss; far power is negative load resistor loss. External source
losses are not part of the line wave-power balance. A changed reference alters
waves but preserves physical V/I and port power. Arrays and exported values
are detached/read-only, with the original time, names and explicit source kind.

Validation covers12 coupled/diagonal/zero-RG ramp/pulse cases across3/4 signals,
independent scalar Debye modal reconstruction, signal/pole permutations,
one/zero strengths, unchanged fields, references, finite scales and no repeated
propagation. Two independent scikit-rf2.2.0 power Z-to-S cases use synthetic
six/eight-port sinusoidal V/I fixtures and retain1e-10 absolute wave error;
they validate conversion algebra, not a propagated line or startup solution.
Sixty pre-edit wave exports (15 source variants, two drives, two references)
preserve exact hashes in source and installed checks. scikit-rf is test-only
with existing BSD-3-Clause notices.

This adapter does not infer propagation modes, TDR inversion, b/a or V/I
ratios, delay alignment, gating, FFT or frequency-dependent references.
[Saved circuit input](multiconductor_debye_startup_document.md) is available,
and [explicit saved wave version10](startup_waves_document_v10.md) now admits
this kind; versions1–9 still reject it. Wave conversion adds no numerical
solver, runtime dependency, application or platform support. See the [general wave contract](startup_waves.md).
