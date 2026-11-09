# Paired goals at finite frequency samples

[한국어](../../locales/ko/pages/packages/sipi/sampled_panel_pair_goal.md) ·
[Single-frequency panel goals](panel_pair_goal.md) · [Panel line contract](panel_line.md)

`sipi.sampled_panel_pair_goal.seek_sampled_panel_forward_pair_impedances`
varies two positive bounded parameters to meet both `Re(Zdd)` and `Re(Zcc)`
from the full complex characteristic matrix at each supplied frequency.
The mixed coordinates use the existing power-dual voltage/current convention;
coupling remains in the full matrix. This does not replace either existing goal API.

Supply 2..64 strictly increasing positive frequencies in Hz and exact `(N, 2)`
positive finite target and absolute tolerance matrices in ohms. Rows follow
frequency order; columns are differential then common. There is no broadcasting.
The factory returns a zero-length `PanelTransmissionLineDocument` with exactly
two ordered signals and exactly that grid. Signal names and panel controls stay
fixed across the search. Geometry, metal, dielectric, skin-depth and resource
admission limits remain those of the explicit panel line.

The bounded two-variable least-squares search uses frequency-first normalized
residuals. `max_evaluations` is an integer from 4 through 10000 counting uncached
frequency-batch attempts, including failed factories, extraction and probes.
Three attempts are reserved for verification. It does not bound internal field
solves, elapsed time or memory. A failed batch contributes no partially successful
frequency row. The cache returns copied residuals.

The selected input is frozen. Verification never calls the factory again:
halve volume edge/far size and grading, double conductor panels, then do both.
Ground modes and interpolation degree stay fixed. All future refinement inputs
are admitted before each search extraction. Every frequency and both quantities
must meet the original absolute tolerances at nominal and all three refined
inputs. Relative changes must also be at most 0.005 against nominal, and between
the joint refinement and each single-axis refinement. Optimizer success alone
does not certify a result. This is a bounded local search, not a global optimum.

`SampledPanelForwardPairDesign` retains frequencies, parameters, target/tolerance
matrices, completed history, selected input, full physical result and all three
refined results. `to_dict()` contains JSON-compatible inputs and residuals.
`SampledPanelForwardPairGoalError` retains the frequency vector, completed
history, attempted count, stage, failed parameters, available input and original
cause. Early invalid controls raise before the factory. No new saved request
schema or common-execution dispatch is introduced by this API.

## Reproducible material example

This example starts at a matched material point. Its independent constitutive
formula shares the geometric vacuum capacitance. It tests dispersive material
scaling and frozen verification, not geometric accuracy, parameter uniqueness
or optimizer recovery from an incorrect initial point.

```python
import numpy as np
from sipi import coupled_microstrip, CrossSectionDocument
from sipi.constants import mu_0, epsilon_0
from sipi.dielectric import DebyeDielectric
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_conductor import panel_surface_current_factors
from sipi.sampled_panel_pair_goal import seek_sampled_panel_forward_pair_impedances

frequencies = np.array([0.5e9, 1e9, 2e9])

def factory(strength, pole_hz):
    section = coupled_microstrip(width=0.3e-3, gap=0.2e-3,
        substrate_height=0.5e-3, eps_r=4, thickness=35e-6,
        air_height=2e-3, box_width=6e-3)
    material = DebyeDielectric(3.0, (strength,), (pole_hz,))
    line = TransmissionLineDocument(
        CrossSectionDocument(section,
            mesh=dict(edge_size=10e-6, far_size=0.2e-3, grade=0.1)),
        frequencies, materials=dict(substrate=material, air=material),
        length=0, conductor=dict(kind="perfect"),
        schema="sipi.transmission-line/6")
    return PanelTransmissionLineDocument(line)

# Uniform material invariant; the initial material already meets these targets.
c0 = panel_surface_current_factors(factory(0.7, 1e9).line.cross_section.section).C0
epsilon = 3.0 + 0.7 / (1 + 1j * frequencies / 1e9)
z = np.array([np.sqrt(mu_0 * epsilon_0 / e) * np.linalg.inv(c0) for e in epsilon])
a = np.array([[1.0, -1.0], [0.5, 0.5]])
targets = np.diagonal(a @ z @ a.T, axis1=1, axis2=2).real
goal = seek_sampled_panel_forward_pair_impedances(
    factory, [[0.5, 0.9], [0.8e9, 1.2e9]], frequencies, targets,
    tolerances=targets * 0.005, initial=[0.7, 1e9], max_evaluations=4)
report = goal.to_dict()
assert report["evaluations"] == 4
assert len(report["refinements"]) == 3
```

## Validation and limits

Tests include independent modal roots and live scikit-rf modal lines, parameter
unit rescaling, cache/Jacobian order, failed probes, atomic batch failures,
strict metadata, boundaries, budgets and every refinement acceptance gate.
An asymmetric lossy physical case starts from an incorrect width/gap and checks
110/40 ohm targets at 0.5/1/2 GHz, absolute limits 0.5/0.25 ohm, all three
refinements and independent balanced 2N eigenspaces within 1e-10. Three outer
domains retain those target limits, relative changes at most 0.005 and decreasing
successive absolute changes for all six sampled quantities. The uniform Debye
case checks the full complex analytic matrix within 1e-10 and C/G scaling within
1e-12, with zero conductor R. These are separate physical and material checks.

Finite samples do not certify the frequencies between them, arbitrary geometries,
measurement accuracy or manufacturing yield. Outer-domain convergence is a
separate validation study, not an automatic check on every API request. This API
adds no browser, Worker, desktop packaging, timeout or cancellation guarantee.
