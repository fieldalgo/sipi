# Coupled startup with an external series RL branch

`coupled_reactive_ladder_response` adds an explicit two-current **series RL branch**
in parallel with the load capacitance and per-conductor resistive terminations.
It returns `ReactiveRLGCLadderResponse`. The [capacitive API](coupled_capacitive_startup.md)
and its saved v3 retain their contracts; explicit saved v4 is documented in the link below.

```python
import numpy as np
from sipi import coupled_reactive_ladder_response

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((np.minimum(t/2e-9, 1.), -.4*np.minimum(t/3e-9, 1.)))
response = coupled_reactive_ladder_response(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_resistance=[0., 37.], load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12,
    load_branch_resistance=[[13., 1.], [1., 9.]],
    load_branch_inductance=np.array([[12., 2.], [2., 8.]])*1e-9)
assert response.voltage.shape == (121, 4)
assert response.load_branch_current.shape == (121, 2)
assert response.total_power_balance_relative_error <= 1e-10
assert np.all(response.load_branch_energy >= 0)
assert np.all(response.load_branch_resistor_loss >= 0)
assert not response.to_dict()['states_included']
```

## Physical contract and units

The line uses constant real exactly symmetric 2x2 R/G PSD and conditioned L/C
SPD matrices, length>0 and explicit 1..128 cells. Time has 2..10000 uniform
samples (relative spacing tolerance1e-10), starts at zero, and the two-column PWL
source starts with a zero row. Initial voltage and current are zero. Source
resistances are two finite nonnegative entries (0=ideal); each parallel load
resistance is nonnegative (0=short) or null/None (resistive path absent).

External `load_capacitance` [F], `load_branch_resistance` [ohm] and
`load_branch_inductance` [H] are all explicit exactly symmetric finite real 2x2
matrices. Capacitance and branch resistance are PSD, including zero/rank-one.
Branch inductance is SPD with eigenvalue ratio strictly above1e-12. Negative
eigenvalues are never repaired. A singular/zero inductance, scalar broadcasting,
bool/complex/nonfinite values, or asymmetric matrix is rejected. External C and
L are lumped values, separate from line C[F/m] and L[H/m]. This topology is not
an arbitrary RLC netlist or a model of initial inductor current.

With branch current `ib` leaving the line, the external equations are
`Lb*dib/dt = Vfar - Rb*ib` and capacitor current `ic = Cload*dVfar/dt`.
Far-node KCL includes `-ib`; fixed short nodes still retain physical line-port
currents from internal endpoint C/G and series flux. Mutual inductance can
produce nonzero branch current at a terminal held at zero voltage.

The finite mass-matrix circuit appends two branch current states, preserves
mixed-boundary elimination and uses PWL propagation. Ideal-source slopes are
right-hand slopes with final hold. Branch energy and losses are not inserted
into the internal-line diagnostics. Cell count and sampled source convergence
remain the caller's responsibility; the cell/sample caps do not certify accuracy.

## Response and power accounting

The copied read-only response retains node/segment states and four port currents
entering the line. `load_branch_current` points outward into the external RL
branch; `load_branch_energy`, `load_branch_energy_rate` and
`load_branch_resistor_loss` are totals over both conductors including mutual terms.

- Internal line `energy`, `energy_rate`, `series_loss`, `shunt_loss` and `line_power`
  retain their previous meaning.
- Capacitor energy/power remain separate. Branch energy is `ib.T*Lb*ib/2`, its
  rate is `ib.T*Lb*dib/dt`, and its resistor loss is `ib.T*Rb*ib`.
- `load_resistor_loss` is only the original parallel termination loss `V²/R`;
  it excludes branch resistance and never squares total capacitive/branch current.
- `total_energy` and `total_energy_rate` include line, external C and branch L.
  Source power minus source/parallel-load/branch/internal losses equals total
  energy rate. Branch terminal power equals branch energy rate plus branch loss.

Both internal and combined RHS power balances require relative error<=1e-10.
Nonfinite dynamics/diagnostics and negative passive energy/loss reject. Default
`to_dict()` omits interior line states but retains external branch currents and
all separated energy/power terms; `include_states=True` includes line states.
The result scope is `finite-passive-two-signal-reactive-load-rlgc-startup`.

## Independent checks and limits

One-cell lossless L-C-L ramp/hold formulas check voltages, currents and each
energy component at rtol1e-10/atol1e-12. A 500MHz scikit-rf modal ABCD comparison
uses `Yload=1/R+jwC+1/(Rb+jwLb)`, 20 cycles/256 samples per cycle and a final
four-cycle phasor. Errors decrease over32/64/128 cells to below1mV. An independent
asymmetric per-node KCL/DOP853 calculation checks voltage<=1e-8V and current<=1e-9A.
Other checks cover DC, lossless post-pulse energy exchange, mixed short/open
boundaries, mutual branch current, time/impedance/permutation/superposition
invariants, copied outputs, strict controls and original capacitive behavior.

These checks apply to the stated finite passive circuit. They do not establish
arbitrary frequency dispersion, nonlinear loads, more conductors, Maxwell time
simulation, general TDR/eye/BER, measured-board accuracy or browser/Windows parity.

[Capacitive load](coupled_capacitive_startup.md) · [Mixed boundaries](coupled_boundary_startup.md) ·
[한국어](../../locales/ko/pages/packages/sipi/coupled_reactive_startup.md)

[Saved reactive v4](coupled_reactive_startup_document.md)

[Explicit port-wave diagnostics](startup_waves.md)

[Current-driven Norton startup](norton_startup.md)

[Mixed voltage/current startup](mixed_startup.md)
