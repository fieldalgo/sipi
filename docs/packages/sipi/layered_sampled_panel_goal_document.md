# Saved coated goals at fixed frequency samples

Explicit `sipi.sampled-panel-forward-pair-design/2` inputs preserve a fixed
line/7 metal law and panel-line/2 current method over a finite frequency grid.
Use `schema='sipi.sampled-panel-forward-pair-design/2'` in the constructor.
The default remains version 1 and keeps its original line/6 metal contract.
No conversion to a coated FEM goal occurs.

The nine keys remain `schema`, `study`, `conductor`, `panel`, `frequency_hz`,
`targets_ohm`, `tolerances_ohm`, `initial` and `max_evaluations`. Both target
maps require `differential_forward_impedance_real` and
`common_forward_impedance_real`, each with one positive finite value per
frequency. They are the real diagonal entries of the full complex mixed
characteristic matrix, not imaginary-part or uncoupled-mode targets.

```python
import numpy as np
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_goal_document import SampledPanelForwardPairDesignDocument
from sipi.execution import execute_saved, normalize_saved

study = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3,
         substrate_height=.5e-3, eps_r=4., tan_delta=.02,
         left_thickness=35e-6, right_thickness=50e-6,
         box_width=.024, air_height=.010),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='corners', variables=[
        dict(name='left_width', lower=.4e-3, upper=.9e-3),
        dict(name='gap', lower=.2e-3, upper=.6e-3)]))

def metal():
    return dict(kind='layered', conductivity=58e6, relative_permeability=1., coatings=[
        dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
        dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])

dd = 'differential_forward_impedance_real'
cc = 'common_forward_impedance_real'
request = SampledPanelForwardPairDesignDocument(study,
    conductor=dict(kind='surface-boundaries',
        conductors={'positive':metal(), 'negative':metal()}, reference=metal(),
        ground_thickness=35e-6),
    frequencies=[1e9,2e9,4e9], targets={dd:[110.]*3, cc:[40.]*3},
    tolerances={dd:[.25]*3, cc:[.125]*3},
    initial=[.0006050501120606677,.0004089487094424394], max_evaluations=4,
    schema='sipi.sampled-panel-forward-pair-design/2')
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=4)
assert output['status'] == 'complete' and output['error'] is None
result = output['result']
assert result['evaluations'] == 4
assert np.all(abs(np.asarray(result['residuals_ohm'])) <= result['tolerances_ohm'])
```

This example starts at the qualified candidate and performs nominal,
volume-only, panel-only and joint checks. Use `initial=[.7e-3,.35e-3]` and
`max_evaluations=64` for the actual search documented in the
[direct contract](layered_sampled_panel_goal.md). Set the common execution
budget to at least the saved budget. One attempt is a whole frequency batch,
including an unsuccessful attempt; it is not a bound on internal field solves
or elapsed time. Three refinement attempts remain reserved.

Parsing is field-free. It checks the 2–64 increasing positive frequencies,
the first-frequency study anchor, strict keys and finite numbers, nominal
and initial/midpoint inputs, all four parameter corners and each future
refinement. The full grid must be within each material's admitted band and
the coating/core/skin-depth limits. This finite preflight does not establish
validity everywhere inside the parameter box or between frequencies.

Fixed pitch, material leaf variables and variable order keep their original
study meanings. Coatings are fixed metadata; they are not newly sampled or
optimized variables. Common execution refuses insufficient budgets and
diagnostic overrides before solving. A failed batch retains its stage,
all frequencies, attempted input, completed history and original cause.

Validation checks strict version separation, full-grid admission, every
refinement failure, fixed pitch/material leaves, actual coated batches and
exact direct/common replay. Prior version 1 canonical inputs and one actual
saved execution are compared unchanged. Separate transfer-matrix references
check the coatings, full characteristic matrix and nonzero-length network.
Finite-domain and small-mutual-entry limits remain those of the direct API;
this saved contract adds no continuous-band or measured-accuracy guarantee.

[Single-frequency saved goal](layered_panel_goal_document.md) ·
[한국어](../../locales/ko/pages/packages/sipi/layered_sampled_panel_goal_document.md)
