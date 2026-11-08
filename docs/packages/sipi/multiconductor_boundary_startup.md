# Multiconductor constant RLGC mixed boundaries

**English** | [한국어](../../locales/ko/pages/packages/sipi/multiconductor_boundary_startup.md)

`multiconductor_boundary_ladder_response` adds a separate three/four-signal
constant finite circuit with ideal/resistive voltage sources and open/short/
resistive loads. It preserves the original [positive-resistance model](multiconductor_startup.md)
and [two-signal mixed-boundary model](coupled_boundary_startup.md).

```python
import numpy as np
from sipi import multiconductor_boundary_ladder_response
t=np.linspace(0.,4e-9,41)
drive=np.minimum(t[:,None]/1e-9,1.)*np.array([1.,-.4,.2])
r=multiconductor_boundary_ladder_response(t,drive,signals=3,
    R=np.array([[20.,-20.,0.],[-20.,20.,0.],[0.,0.,0.]]),
    L=np.array([[450.,60.,0.],[60.,480.,60.],[0.,60.,510.]])*1e-9,
    G=np.array([[0.,0.,0.],[0.,.002,.002],[0.,.002,.002]]),
    C=np.array([[210.,-20.,0.],[-20.,220.,-20.],[0.,-20.,230.]])*1e-12,
    length=.1,cells=8,source_resistance=[0.,25.,0.],
    load_resistance=[None,0.,75.])
assert r.voltage.shape==r.current.shape==(41,6)
assert r.node_voltage.shape==(41,9,3) and r.segment_current.shape==(41,8,3)
np.testing.assert_array_equal(r.voltage[:,[0,2]],drive[:,[0,2]])
assert not np.any(r.current[:,3]) and not np.any(r.voltage[:,4])
assert r.current[0,0]!=0.  # A prescribed ramp includes endpoint displacement current.
```

Inputs use explicit signals3/4, cells1–128, uniform2–10000 time rows starting0,
and first-row-zero PWL voltage samples shaped(times,signals). Constant SI
R[ohm/m] and G[S/m] are exactly symmetric PSD; L[H/m] and C[F/m] are exactly
symmetric SPD with normalized eigenvalue ratio>1e-12. Zero/singular R/G are
allowed. Negative normalized eigenvalues are rejected without clipping,
symmetry repair or hidden rank thresholds; floating-point eigensign ambiguity
can conservatively reject a mathematical PSD matrix.

Each source resistance is finite>=0:0 means prescribed ideal voltage. Each
load entry is None=open,0=short,or finite>0. Vectors have exactly signals
entries; there is no scalar broadcast or source-None alias. External reactive
loads, current sources and dispersion are outside this contract.

The half-end pi circuit retains full mutual endpoint C/G. Fixed-voltage
coordinates are eliminated from the mass matrix; a free-state transform removes
prescribed-voltage derivative forcing before SciPy lsim. Reconstruction uses
right PWL slopes at knots and final slope0. Ideal and short terminal currents
include full endpoint displacement and shunt currents, not just segment current.
Both near N and far N currents enter the line. A zero initial stored-energy
state can still have nonzero initial ideal-source displacement current.

```python
import json
np.testing.assert_allclose(r.energy_rate,
    r.line_power-r.series_loss-r.shunt_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(r.source_power,
    r.source_resistor_loss+r.load_resistor_loss+r.line_power,rtol=1e-10,atol=1e-12)
assert max(r.power_balance_relative_error,r.total_power_balance_relative_error)<=1e-10
assert r.port_names==('near_0','near_1','near_2','far_0','far_1','far_2')
assert not r.current.flags.writeable
out=r.to_dict(include_states=True)
assert out['input']['source_resistance_ohm']==[0.,25.,0.]
assert out['input']['load_resistance_ohm']==[None,0.,75.]
json.dumps(out,allow_nan=False)
```

Stored energy and all passive losses must remain finite and nonnegative.
Line and source balances independently retain relative1e-10 acceptance.
Outputs are detached readonly arrays; source/load entries and declared PSD
matrices remain unchanged. Nonrepresentable cell/source scales and propagation
failures are explicit errors. No small resistor substitutes for an ideal end.

Independent original per-node charge KCL uses direct free voltages, prescribed
voltage derivatives and DOP853, splitting source knots. It does not reuse the
transformed state, mass matrix or propagation coefficients. Three/four-signal
noncommuting PSD/conditioned storage ramp/pulse cases meet1e-8V/1e-9A gates.
One-cell ideal/short ramp RL and pure-L solutions include mutual endpoint C
current. All1512 boundary combinations (216three-signal,1296four-signal) pass
boundary and power checks. Existing positive-boundary, zero-Debye-strength,
scalar diagonal and two-plus-one/two-plus-two references agree.

Lossless modal fixtures use length.1m,2ns ramp,12ns observation,1201samples,
Rs0/25ohm and load0/open/100ohm. For all12 conditions,32/64/128cells decrease
terminal error (exact prescribed voltages excepted) and final errors are
<=.02V and<=.0005A. Observed worst final errors are.00646841224V and
.000157794877A. Identical PWL knots at601/1201/2401samples preserve common
samples. These are explicit one-dimensional spatial/sampling checks, not
arbitrary-source, extracted-field or measured-interconnect accuracy.

The previous144 full-state outputs remain exact on source/installed artifacts;
all old numerical source and tests are unchanged. The separate response is
not implicitly accepted by saved or terminal-wave APIs. The registry remains
90schemas/37templates. No new dependency, browser/desktop update or platform
support is added. See [development validation](../../development.md).


[Explicit saved mixed-boundary inputs](multiconductor_boundary_startup_document.md) preserve ideal/open/short values without changing the numerical model; terminal-wave admission remains separate.
