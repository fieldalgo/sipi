# Explicit shape-current goals across a finite frequency grid

[한국어](../../locales/ko/pages/packages/sipi/shape_sampled_panel_pair_goal.md) ·
[Single-frequency shape goals](shape_panel_pair_goal.md) · [Original grid search](sampled_panel_pair_goal.md)

`seek_shape_sampled_panel_forward_pair_impedances` seeks the real differential
and common forward impedances at every supplied frequency. These are separate
power-dual launches derived from the full complex characteristic matrix, not
modal magnitudes or terminated input impedances. The factory must explicitly
return `ShapePanelTransmissionLineDocument`; existing goals retain their method.

Two positive bounded parameters and 2..64 strictly increasing positive frequencies
are required. Targets and absolute tolerances are positive real (N,2) matrices in
ohms, ordered differential/common; scalar broadcasting is rejected. The ordered
signals, frequency vector, zero length, panel controls and shape step must remain
fixed throughout search. Bulk/fixed-coated metals keep their own admission rules.
A finite-grid problem can be overdetermined or have no acceptable solution.

An integer budget of 4..10000 counts uncached whole-line attempts, including failed
attempts and optimizer probes. Three attempts are reserved for the frozen selected
input: volume-only, panel-only and joint refinements. Future refinements are admitted
before search fields. Every selected/refined frequency must satisfy the original
absolute tolerances. Refined values must change by at most 0.5% from nominal;
joint refinement must also meet 0.5% against both separate refinements. An initial
match still needs all four actual batches. No failed candidate is returned as a
qualified design.

This example prepares a search without running it. Its targets come from a saved
finite-domain calculation at width .55 mm/gap .35 mm, **not an independent field
reference or measurement**. The initial parameters are different. Dimensions are
metres and the frequency vector is in hertz.

```python
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.dielectric import DebyeDielectric
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.shape_sampled_panel_pair_goal import seek_shape_sampled_panel_forward_pair_impedances

frequencies = [1e9, 2e9, 4e9]
def line(width, gap):
    section = asymmetric_coupled_microstrip(
        left_width=width, right_width=.5e-3, gap=gap,
        substrate_height=.2e-3, eps_r=1., tan_delta=0.,
        left_thickness=35e-6, right_thickness=50e-6,
        box_width=8e-3, air_height=3.75e-3)
    metal = dict(conductivity=58e6, relative_permeability=1., roughness={'kind':'smooth'})
    conductor = dict(kind='surface-boundaries',
        conductors={'positive':metal, 'negative':metal}, reference=metal,
        ground_thickness=35e-6)
    material = DebyeDielectric(3., (.7,), (1e9,))
    source = TransmissionLineDocument(
        CrossSectionDocument(section, mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1)),
        frequencies, materials={'substrate':material, 'air':material},
        conductor=conductor, length=0., schema='sipi.transmission-line/6')
    return ShapePanelTransmissionLineDocument(PanelTransmissionLineDocument(source,
        panels_per_edge=16, ground_modes=512, interpolation_degree=16))

options = dict(factory=line, bounds=[[.4e-3,.7e-3],[.2e-3,.5e-3]],
    frequencies=frequencies,
    targets=[[68.8828994054204,21.90566648151497],
             [71.10351393482341,22.613365409231967],
             [72.29432825718574,22.993194259891602]],
    tolerances=[[.05,.025]]*3, initial=[.48e-3,.28e-3], max_evaluations=64)
assert line(.55e-3,.35e-3).to_dict()['line']['line']['frequency_hz'] == frequencies
# goal = seek_shape_sampled_panel_forward_pair_impedances(**options)
```

`ShapeSampledPanelForwardPairDesign` retains the chosen line, three refined lines,
parameters, frequency grid, targets/tolerances and complete history. `to_dict()`
adds the full current records for selected/refined results; history retains original
input and impedances. Fresh document accessors preserve the explicit method. The
report is not a saved request/factory schema.

`SampledPanelForwardPairGoalError` retains completed history, frequency vector,
failed attempt count, stage, parameters/input and original cause chain. A
`ShapePanelLineError` cause exposes its detailed partial current record. Interrupts
propagate. No fallback method is silently substituted.

Validation includes independent modal grids and unit scaling, full-grid target
and identity failures, reserved budgets, original consumers, and actual bulk/coated
searches from nonmatching starts. Selected and separately refined fields are checked
against independent uniform Debye, metal-transfer and four-port identities. The
finite-domain targets exercise inverse-search self-consistency; they do not supply
independent absolute accuracy evidence. Existing small-domain outer rejections
remain unchanged. No global optimum, uniqueness, continuous-band compliance,
outer-domain sufficiency or absolute accuracy is certified.

[Saved requests and execution receipts](shape_sampled_panel_pair_goal_document.md).
