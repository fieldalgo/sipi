# Coated manufactured samples over fixed frequencies

Explicit `sipi.sampled-panel-forward-pair-study/2` preserves fixed line/7
coatings and panel-line/2 currents. Each manufactured geometry/material sample
is evaluated at the whole stated frequency vector. Version 1 remains the
default with its existing metal contract. Study version 2 has the same five
keys: `schema`, `study`, `conductor`, `panel` and `frequency_hz`.

Explicit `sipi.sampled-panel-forward-pair-yield/2` requires a version 2 study.
Its five keys remain `schema`, `study`, `acceptance`, `confidence` and
`minimum_yield`. Both real forward impedances must satisfy their inclusive
limits at every supplied frequency for that manufactured row to pass. The
trial count is the number of iid rows, not rows times frequencies or quantities.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.sampled_panel_pair_yield import SampledPanelForwardPairYieldDocument
from sipi.execution import execute_saved, normalize_saved

width, gap = .0006050501120606677, .0004089487094424394
source = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=width, right_width=.5e-3, gap=gap, substrate_height=.5e-3,
         eps_r=4., tan_delta=.02, left_thickness=35e-6, right_thickness=50e-6,
         box_width=.024, air_height=.010),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='normal', count=2, seed=3, correlation=[[1.,.5],[.5,1.]], variables=[
        dict(name='left_width', mean=width, std=10e-6),
        dict(name='gap', mean=gap, std=5e-6)]))

def metal():
    return dict(kind='layered', conductivity=58e6, relative_permeability=1., coatings=[
        dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
        dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])

study = SampledPanelForwardPairStudyDocument(source, frequencies=[1e9,2e9,4e9],
    conductor=dict(kind='surface-boundaries',
        conductors={'positive':metal(), 'negative':metal()}, reference=metal(),
        ground_thickness=35e-6), schema='sipi.sampled-panel-forward-pair-study/2')
request = SampledPanelForwardPairYieldDocument(study, acceptance={
    'differential_forward_impedance_real': dict(minimum=[109.]*3, maximum=[111.]*3),
    'common_forward_impedance_real': dict(minimum=[39.75]*3, maximum=[40.25]*3)},
    confidence=.95, minimum_yield=.9, schema='sipi.sampled-panel-forward-pair-yield/2')
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=2)
assert output['status'] == 'complete' and output['error'] is None
result = output['result']
assert result['count'] == 2 and result['frequencies_hz'] == [1e9,2e9,4e9]
assert all(len(row['values_ohm']) == 3 for row in result['rows'])
assert result['goal_status'] == 'undetermined'
```

The example uses two rows for execution, not a claim of 90% production yield.
A calculation can complete while the statistical target remains undetermined.
The exact-binomial interval envelopes original unresolved rows in their
original denominator. It is conditional on this distribution and numerical
model, not a bound for geometry extraction, discretization or measurements.
A row that passes at 1 GHz may fail the joint event at 4 GHz.

The study accepts the original sweep/corners/uniform/correlated-normal plans;
iid yield accepts only uniform/normal. The first frequency must match the study
anchor and the full 2–64 point positive increasing grid must pass nominal
material-band, coating/core, skin-depth and panel admission. All sample
vectors are generated before fields, with no frequency-dependent resampling.
Each row retains its resolved parameters, material evaluation, exact input
and whole frequency-by-two result. A failed batch has no partial accepted
values; later rows are still attempted. No clipping or rejected-row removal
changes the distribution. Descriptive per-frequency summaries exist only
when every row completes.

`max_evaluations` counts manufactured whole-frequency batches. An insufficient
budget is refused before fields, and failed rows retain their planned positions.
The limit does not bound internal field solves, time or memory. Coating stacks
are fixed metadata; these schemas add no random coating-thickness variables.
Fixed pitch and dielectric material leaves retain their existing source rules.

Existing fixed-candidate selection can retain explicit version 2 study children.
Its family budget and simultaneous interval allocation still count candidates
and manufactured rows, with no extra frequency multiplier. Versioned children
remain in every input snapshot; no default current method changes.

The numerical qualification observes eight fixed correlated rows at 1, 2 and
4 GHz with separate nominal, volume-only, panel-only and joint resolutions.
The two sampled width extremes receive separate joint-resolution finite outer
checks. All original forward-diagonal refinement and finite-domain gates remain;
small mutual matrix entries are retained separately. Independent coating
transfer, full characteristic and 20 mm network references check every batch.
The regression regenerates the first two rows and both outer endpoints, and
checks statistics, atomic failures, exact common replay and installed inputs.
These finite observations do not certify every tail of an unbounded normal
population or include numerical error in a nominal yield interval.

[Coated fixed-frequency sampling](layered_panel_study.md) ·
[Coated frequency-grid goals](layered_sampled_panel_goal_document.md) ·
[한국어](../../locales/ko/pages/packages/sipi/layered_sampled_panel_study.md)

[Compare fixed numerical resolutions](sampled_panel_resolution_yield.md).
