# Coated pair goals at fixed frequency samples

`seek_sampled_panel_forward_pair_impedances` can use an explicit panel-line/2
factory with line/7 coated metals. One width and gap must satisfy both real
forward impedance targets at every supplied frequency. These are Re(Zdd) and
Re(Zcc) from the full complex characteristic matrix, for zero common current
and zero differential current respectively; imaginary parts are not targets.
Each metal's
ordered coatings and bulk properties stay fixed throughout the search.

The example starts at a qualified candidate and still runs all four independent
resolution checks. To search from a point outside the target tolerances, use
`initial=[.7e-3,.35e-3]` and `max_evaluations=64`. One budget attempt evaluates
the entire stated frequency vector; it does not bound internal field solves,
memory or elapsed time. Inputs use SI units and absolute ohm tolerances.

```python
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.sampled_panel_pair_goal import seek_sampled_panel_forward_pair_impedances
import numpy as np

MESH = dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075)


def material():
    return dict(kind='layered', conductivity=58e6, relative_permeability=1., coatings=[
        dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
        dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])


def factory(width, gap, *, box=.024, air=.010):
    section = asymmetric_coupled_microstrip(left_width=width, right_width=.5e-3,
        gap=gap, substrate_height=.5e-3, eps_r=4., tan_delta=.02,
        left_thickness=35e-6, right_thickness=50e-6, box_width=box, air_height=air)
    line = TransmissionLineDocument(CrossSectionDocument(section, mesh=MESH), [1e9,2e9,4e9],
        materials={}, length=0., conductor=dict(kind='surface-boundaries',
            conductors={t.name:material() for t in section.traces}, reference=material(),
            ground_thickness=35e-6), schema='sipi.transmission-line/7')
    return PanelTransmissionLineDocument(line, schema='sipi.panel-transmission-line/2')


goal = seek_sampled_panel_forward_pair_impedances(factory,
    [[.4e-3, .9e-3], [.2e-3, .6e-3]], [1e9,2e9,4e9],
    [[110.,40.]]*3, tolerances=[[.25,.125]]*3,
    initial=[.0006050501120606677, .0004089487094424394], max_evaluations=4)
assert len(goal.history) == 4
assert np.all(abs(np.asarray(goal.residuals)) <= goal.tolerances)
```

This contract accepts 2–64 increasing positive frequency samples. The example
imposes 110/40 ohms with .25/.125 ohm tolerances at 1, 2 and 4 GHz simultaneously.
The initial mismatching geometry gives approximately 103.52/39.10 ohms at 1 GHz;
the selected width/gap are approximately .605050/.408949 mm. The test requires
an actual bounded search and retains every attempted input and completed result.
A stationary point must satisfy every target; optimizer success alone is insufficient.

Nominal, volume-only, panel-only and joint refinements must each satisfy every
frequency target. Independent relative changes must also meet the original
0.5% gates, including joint versus both individual refinements. Coating depth,
remaining core and panel geometry admission still apply to each batch before
fields. Failures retain their exact stage, frequency vector and attempted input.

A separate regression freezes the selected geometry at joint resolution and
uses box width/air height 24/10, 36/15 and 48/20 mm, with 512, 768 and 1024
ground modes. Each frequency must meet both finite-domain differential
change gates (each <= 1e-4 of the first value), while the second common-mode
change must be smaller than the first. The API does not run these outer checks
automatically. A passing finite sequence is not an infinite-domain error bound.

Independent planar transfer matrices check the coatings; full 4-by-4 transfer
matrices check the characteristic matrix and 20 mm line scattering matrix.
Reciprocity and passivity are checked at that nonzero length. These comparisons
reuse extracted RLGC and do not independently establish geometry or measured
accuracy. Small mutual resistance entries keep their separate accuracy limits.

The output describes only the supplied frequencies and a bounded local search.
It does not certify unsampled frequencies, continuous-band feasibility, a global
optimum or production yield. The original single-frequency API and saved
contracts retain their meanings.

[Saved version 2 requests](layered_sampled_panel_goal_document.md) preserve the
coated factory inputs and whole-frequency-batch budget through common execution.

[Single-frequency coated goal](layered_panel_goal.md) ·
[Finite-frequency contract](sampled_panel_pair_goal.md) ·
[한국어](../../locales/ko/pages/packages/sipi/layered_sampled_panel_goal.md)
