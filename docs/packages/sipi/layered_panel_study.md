# Coated panel paired tolerances and joint acceptance

[Resolution comparison](panel_resolution_yield.md) retains conflicting sample labels as unresolved.

Explicit `sipi.panel-forward-pair-study/2` connects the existing paired sampling
contract to line/7 and panel-line/2. The root keys remain `schema`, `study`,
`conductor` and `panel`. Each signal and reference boundary keeps its fixed
bulk metal and ordered planar coating stack. Geometry and supported dielectric
material variables retain their existing source-study meaning. Coating thickness
is fixed, not a newly introduced random variable.

Every requested sample is attempted in order. One extraction supplies both
Re(Zdd) and Re(Zcc); neither quantity is treated as an independent propagation
mode. Duplicates remain separate rows, failures retain their phase/input and
later rows still run. A failed pair has no partial quantity, and a descriptive
summary exists only when all rows complete. No sample is clipped or resampled.

Explicit `sipi.panel-forward-pair-yield/2` requires a nested version 2 panel
study. Version 1 retains its version 1 source. Joint acceptance is the AND of
the two inclusive limits for each manufactured sample, not the product of two
marginal fractions. Uniform or normal iid samples are required; within-row
variable correlation is allowed. Failed pairs remain unresolved in the original
denominator. The existing Clopper–Pearson interval envelopes all possible
unresolved labels. It does not include field, material or distribution error.

This small example uses two samples to demonstrate saved execution. It cannot
establish a high production yield. Lengths are metres, standard deviations are
in the variables' units, conductivity is S/m and impedance limits are ohms.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.panel_pair_yield import PanelForwardPairYieldDocument
from sipi.execution import execute_saved

width, gap = .0006073049209836395, .0004082505417130786
source = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=width, right_width=.5e-3, gap=gap,
         substrate_height=.5e-3, eps_r=4., tan_delta=.02,
         left_thickness=35e-6, right_thickness=50e-6,
         box_width=.024, air_height=.010),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='normal', count=2, seed=3,
        correlation=[[1., .5], [.5, 1.]], variables=[
            dict(name='left_width', mean=width, std=10e-6),
            dict(name='gap', mean=gap, std=5e-6)]))
metal = dict(kind='layered', conductivity=58e6, relative_permeability=1.,
    coatings=[dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
              dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])
study = PanelForwardPairStudyDocument(source,
    conductor=dict(kind='surface-boundaries', conductors=dict(positive=metal, negative=metal),
                   reference=metal, ground_thickness=35e-6),
    schema='sipi.panel-forward-pair-study/2')
request = PanelForwardPairYieldDocument(study, acceptance={
    'differential_forward_impedance_real': dict(minimum=109., maximum=111.),
    'common_forward_impedance_real': dict(minimum=39.75, maximum=40.25)},
    confidence=.95, minimum_yield=.9, schema='sipi.panel-forward-pair-yield/2')
output = execute_saved(request.dumps(), max_evaluations=2)
assert output['status'] == 'complete' and output['result']['count'] == 2
assert output['result']['event'] == 'both-paired-forward-impedance-limits'
```

Normalization performs no field solve and checks nominal metal/panel admission.
All samples and their total budget are determined before field work. Each
sample must separately satisfy the coating core/skin-depth and panel geometry
restrictions; nominal validity does not make every random draw valid. Existing
version 1 canonical inputs and numerical behavior remain unchanged.

The numerical regression uses eight normal samples, seed 3, width/gap standard
deviations 10/5 micrometres and correlation .5 around the stated mean. Each row
is independently checked by planar coating transfer, full characteristic and
20 mm scattering references. Separate volume-only, panel-only and joint
refinements require each forward diagonal to change by at most 0.5%, including
joint versus single-axis comparisons. These numerical tests are distinct from
manufacturing acceptance; a correctly computed sample can violate a target.
Full field inputs, matrices, current integrals and ordered rows are retained.

In this fixed eight-row case, the nominal and panel-only resolutions accept
six rows; volume and joint refinement accept seven. One differential value
moves across the 109-ohm lower limit, from 108.9822 to 109.0205 ohms. Thus
passing the 0.5% numerical change gate does not establish a stable acceptance
label near a specification boundary. The nominal 95% interval, approximately
[.3491, .9681], does not include this discretization uncertainty.

The study API does not automatically refine each row or certify outer-domain
accuracy. The mean geometry has the separate finite-domain observations in
[coated pair goals](layered_panel_goal.md); those observations do not establish
outer convergence for every sample. Small mutual resistance and measured-accuracy
limitations remain. Statistical bounds describe only the stated sampling model,
not measured production yield.

[Paired sampling](panel_pair_study.md) · [Joint acceptance](panel_pair_yield.md) ·
[한국어](../../locales/ko/pages/packages/sipi/layered_panel_study.md)
