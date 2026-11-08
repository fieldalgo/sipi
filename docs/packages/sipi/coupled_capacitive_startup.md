# Explicit capacitive loads on a two-signal startup circuit

`coupled_capacitive_ladder_response` adds a passive **far-load capacitance
matrix in farads** to the [mixed-boundary finite circuit](coupled_boundary_startup.md).
This matrix is separate from the line's per-length C [F/m]. Source, line and
external capacitor initially store zero energy. No capacitor value is inferred
from geometry, waveform bandwidth or a resistor.

```python
import numpy as np
from sipi import coupled_capacitive_ladder_response

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((np.minimum(t/2e-9, 1.), -.4*np.minimum(t/3e-9, 1.)))
r = coupled_capacitive_ladder_response(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_resistance=[0., 37.], load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12)
assert r.power_balance_relative_error <= 1e-10
assert r.total_power_balance_relative_error <= 1e-10
np.testing.assert_array_equal(r.total_energy, r.energy+r.load_capacitor_energy)
assert r.load_capacitor_current.shape == (121, 2)
record = r.to_dict()
assert 'load_capacitance_f' in record['input'] and not record['states_included']
```

## Model and boundary conditions

`load_capacitance` is a finite real exactly symmetric positive-semidefinite2x2
matrix. Zero and rank-one matrices are allowed; negative eigenvalues, numeric
booleans, nonfinite values, scalar shortcuts or asymmetric matrices are rejected.
No negative-eigenvalue repair or component-topology extraction is performed.
The matrix is constant and represents a linear passive constitutive relation.

All mixed-boundary line controls remain: constant exactly symmetric2x2 PSD
R/G, conditioned SPD L/C, explicit1..128 cells, uniform2..10000 times starting0,
zero-first `(samples,2)` PWL source and final hold. Source resistance entries
are finite>=0, zero=ideal; each load entry is finite>=0, zero=short, orNone=open.
Here open means **no parallel load resistor**; an explicitly supplied capacitor
still draws current. A short fixes that conductor voltage even with a capacitor
attached. This API has no arbitrary inductive, nonlinear, active or dispersive
external load, and does not extend existing positive/mixed saved versions.

Cload is added to the full far-node mass block before fixed-voltage elimination.
The same free-state transform retains mutual line and load capacitance. Finite/
open far-port current into the line is -V/R-Cload*V_dot (omit V/R for open).
At a short, line-port current comes from the internal line endpoint C/G and
segment flux, including coupling. Capacitor current is reported separately,
positive **from the line into the external capacitor matrix**. Individual
capacitor currents can have either sign. Right PWL slopes/final-zero-slope
conventions and all four into-line port signs remain unchanged.

## Separate internal and external energy

`CapacitiveRLGCLadderResponse` inherits copied/read-only port and internal-state
arrays and optional interior-state serialization. Its input retains
`load_capacitance_f`; its scope identifies the capacitor-loaded model.
Inherited `energy`, `energy_rate`, `series_loss`, `shunt_loss` and `line_power`
refer to the internal line alone. New arrays are `load_capacitor_current`
(two columns), `load_capacitor_energy` and `load_capacitor_power` (totals).

Eload=.5*Vfar^T*Cload*Vfar and Pload=Vfar^T*Cload*Vfar_dot. The read-only
`total_energy` and `total_energy_rate` properties add these external terms to
the line values. Resistive load loss is sum(V**2/R), excluding capacitive
current; using total port current squared times R would incorrectly count
reactive current as dissipation. Short/open branches dissipate no resistor power.

Both balances are checked with relative residual<=1e-10:
line E_dot = line port power - internal R/G losses;
total E_dot = source power - source/load resistor losses - internal R/G losses.
Each residual is normalized by the largest magnitude of its rate/input/total-loss
terms; an all-zero response has zero relative residual. Internal/external stored
energies and internal losses remain nonnegative. Negative return power is kept.
Nonfinite mass matrices, states or diagnostics raise without partial results.
A balance check alone is not a convergence or real-material accuracy certificate.

## Independent evidence and settling

Cload0 reproduces mixed-circuit states. With both far nodes shorted, any supplied
matrix has zero voltage, current and energy and leaves line states unchanged.
Rank-one matrices with one short preserve cross-terminal capacitive current.
Time/impedance scaling, conductor permutation, zero input, separate resistor
loss and lossless trapped-energy exchange are also checked. Twelve full-state
ramp/pulse replays of the original API match its prior installed build exactly.

Independent one-cell LC ramp solutions use length1m, L=I H/m, C=.4I F/m,
R=G=0, ideal sources, no load resistors and Cload=diag(.3,.7)F. Each far-node
capacitance is .2+Cload, so omega**2=1/(L*(.2+Cload)). At401 samples over0..4s,
a0..1s ramp to[1,-.4] matches port voltage/current and separate line/load energy
within rtol1e-10/atol1e-12. This checks source half-capacitor current as well.

Independent scikit-rf2.2.0 continuous modal ABCD plus Yload=1/100+jw*Cload_mode
checks exchange-symmetric matrices at500MHz. For the positive-resistance API's
RLGC example, .1m, Rs25/RL100 each, Cload[[30,-5],[-5,30]]pF, first-source
sinusoid,20cycles/256samplespercycle and final4-cycle phasor,32/64/128-cell
errors are .002345/.000593/.000154V. They decrease and meet .001V at128 cells;
PWL interpolation error is retained. Separate asymmetric per-node KCL/DOP853
at16 cells with the code example's matrices/ends/Cload passes1e-8V/1e-9A
(rtol1e-10,atol1e-12,max step minimum line-mode delay/(5*cells)). This compares
propagation algorithms for the same circuit, not distinct spatial discretizations.
Existing SciPy1.18.1 and test-only scikit-rf2.2.0 retain BSD-3-Clause usage.

The DC check initially failed at200ns with a1.515e-8V residual. Time refinement
and an independent state-coordinate transformation left that residual unchanged;
a stable slow mode has26.24ns decay time. At300/400/500ns, residuals decrease
3.724e-10/2.514e-12/9.515e-14V; capacitor currents decrease
9.895e-12/9.575e-14/2.577e-15A. The400/500ns outputs meet the unchanged DC
rtol1e-10/atol1e-12 and capacitor-current1e-13A gates. The original200ns failure
is retained; the test now explicitly reaches500ns. The API never extends the
user's requested horizon. Later600/1000ns voltages plateau at roundoff, so
strict tail decay is checked before that floor. No formula or tolerance changed.

This remains a finite constant two-signal circuit. Check spatial/source/time
convergence and settling for each input. Saved capacitor inputs, application
forms, browser/Windows integration and measured-board accuracy are separate work.

[Mixed resistive boundaries](coupled_boundary_startup.md) · [Positive two-signal circuit](coupled_startup.md) ·
[한국어](../../locales/ko/pages/packages/sipi/coupled_capacitive_startup.md)

[Saved capacitive v3](coupled_capacitive_startup_document.md)

[External series RL branch](coupled_reactive_startup.md)
