# Saved paired goals at finite frequency samples

[한국어](../../locales/ko/pages/packages/sipi/sampled_panel_pair_goal_document.md) ·
[Direct finite-frequency API](sampled_panel_pair_goal.md) · [Single-frequency saved goals](panel_pair_goal_document.md)

`SampledPanelForwardPairDesignDocument` saves an explicit panel-current request
as `sipi.sampled-panel-forward-pair-design/1`. It reuses the direct finite-frequency
API and the existing template/material input contract. It does not serialize callbacks.

The exact root keys are `schema`, `study`, `conductor`, `panel`, `frequency_hz`,
`targets_ohm`, `tolerances_ohm`, `initial` and `max_evaluations`. The nested study
must be study/3 or /4, paired `z_diff_forward`, with corners sampling and exactly
two ordered positive bounded variables. Geometry/material leaves, fixed pitch
and fixed plane spacing retain their existing meanings. Corners specify search
bounds here, not a preliminary tolerance or statistical calculation.

`frequency_hz` has 2..64 strictly increasing positive Hz samples. The nested
study's `material_evaluation.frequency_hz` must equal the first sample exactly.
This explicit anchor preserves the original study contract; it is never silently
changed. Every candidate line and material model is evaluated on the entire
requested grid. Out-of-range material tables are rejected before fields.

Targets and tolerances each have exactly the named keys
`differential_forward_impedance_real` and `common_forward_impedance_real`.
Each value is a positive finite array with one entry per frequency, in ohms.
No scalar broadcasting or dictionary-order interpretation is used. `initial`
is null for the midpoint or two values in variable order. The attempt budget is
an integer 4..10000. The panel object has exactly `panels_per_edge`, `ground_modes`
and `interpolation_degree`; all previous capability/resource restrictions remain.

Normalization checks nominal, initial/midpoint and all four corner full-grid
line inputs, plus the volume/panel/joint refinement inputs, without meshing or
field solves. This does not establish validity everywhere inside the bounds or
physical skin-depth applicability. Preflight is outside the attempt budget.

`solve()` retains the direct API's full history, frozen selected input and three
verification results. `execute_saved()` first rejects a saved budget above its
caller budget, without clamping it. Counts are frequency-batch attempts, including
failures and probes; they do not bound internal field work, time or memory.
A successful execution contains the direct report. A failed goal returns
`status="failed"`, `result=null`, both quantity names, units, the full frequency
vector, original stage/cause/attempts/failed parameters, available input and all
completed batches. It does not report partial frequencies as a successful batch.
Malformed saved inputs raise before solving. Diagnostic options remain limited
to top-level line requests. All previous saved schemas retain their contracts.

## Reproducible saved material example

This starts at matched uniform Debye parameters and changes two regional
`eps_inf` leaves independently. The analytical material formula shares geometric
vacuum capacitance; it is not an independent geometry or parameter-uniqueness
reference. All four nominal/refinement batches still run.

```python
import numpy as np
from sipi import coupled_microstrip
from sipi.constants import mu_0, epsilon_0
from sipi.dielectric import DebyeDielectric
from sipi.study import ImpedanceStudyDocument
from sipi.panel_conductor import panel_surface_current_factors
from sipi.sampled_panel_pair_goal_document import SampledPanelForwardPairDesignDocument
from sipi.execution import normalize_saved, execute_saved

frequencies = np.array([0.5e9, 1e9, 2e9])
parameters = dict(width=0.3e-3, gap=0.2e-3, substrate_height=0.5e-3,
    eps_r=4, thickness=35e-6, air_height=2e-3, box_width=6e-3)
material = DebyeDielectric(3.0, (0.7,), (1e9,))
study = ImpedanceStudyDocument("coupled_microstrip", parameters,
    quantity="z_diff_forward", frequency=float(frequencies[0]),
    materials=dict(substrate=material, air=material),
    mesh=dict(edge_size=10e-6, far_size=0.2e-3, grade=0.1),
    material_variables={
        "eps_substrate": dict(region="substrate", path=["eps_inf"]),
        "eps_air": dict(region="air", path=["eps_inf"])},
    sampling=dict(kind="corners", variables=[
        dict(name="eps_substrate", lower=2.0, upper=4.0),
        dict(name="eps_air", lower=2.0, upper=4.0)]))

# Uniform material reference at an already matched initial point.
c0 = panel_surface_current_factors(coupled_microstrip(**parameters)).C0
epsilon = 3.0 + 0.7 / (1 + 1j * frequencies / 1e9)
z = np.array([np.sqrt(mu_0 * epsilon_0 / e) * np.linalg.inv(c0) for e in epsilon])
a = np.array([[1.0, -1.0], [0.5, 0.5]])
targets = np.diagonal(a @ z @ a.T, axis1=1, axis2=2).real
quantities = ("differential_forward_impedance_real", "common_forward_impedance_real")
request = SampledPanelForwardPairDesignDocument(study,
    conductor=dict(kind="perfect"), frequencies=frequencies.tolist(),
    targets=dict(zip(quantities, targets.T.tolist())),
    tolerances=dict(zip(quantities, (targets * 0.005).T.tolist())),
    initial=[3.0, 3.0], max_evaluations=4)
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=4)
assert output["status"] == "complete"
assert output["result"]["evaluations"] == 4
```

## Validation and limits

Checks include independent modal roots versus the direct API, strict JSON and
copy isolation, full-grid table limits, fixed-pitch material substitution,
preflight and parent budgets, every failed refinement stage, and nine frequency
samples within a four-batch matched-point budget. Actual saved geometry replays
the qualified finite-frequency selected point and all three frozen refinements;
independent balanced 2N characteristic matrices agree within 1e-10. A saved
uniform Debye case checks the complex analytic matrix within 1e-10 and C/G
scaling within 1e-12, with zero R.

The direct API's outer-domain study remains separate; normalization does not
automatically certify outer convergence. These cases do not establish continuous
band behavior, arbitrary geometry, unique inversion, measurement accuracy or
manufacturing yield. No browser/Worker/EXE integration or new platform support
is implied by the transport-neutral saved request.
