# Broadside pair with an interface inside the gap

`split_gap_broadside_stripline` describes two trapezoidal conductors with four
planar dielectric layers. All lengths are metres. `gap` is the vertical
metal-to-metal clearance. `gap_lower_height` locates the interface above the
lower copper's top face and must satisfy `0 < gap_lower_height < gap`. The
remaining upper gap is `gap - gap_lower_height`. Moving the interface does
not move the copper or outer ground planes.

The bottom-to-top materials are `lower`, `gap_lower`, `gap_upper`, `upper`,
with independent relative permittivities and loss tangents. Outer clearances
exclude copper; outer layer thicknesses include it. Equal adjacent materials
retain separate layer identities. All four widths and both copper thicknesses
are positive. Bottom/top widths refer to geometric -y/+y faces for both traces.
The lower `positive` and upper `negative` centres are `-offset/2` and `+offset/2`.
Planes are grounded, side walls have zero normal flux and require a separate
outer-width check. No exchange symmetry or independent even/odd modes is assumed.

```python
from sipi import split_gap_broadside_stripline, CrossSectionDocument

section = split_gap_broadside_stripline(
    lower_width=.4e-3, lower_top_width=.32e-3,
    upper_width=.7e-3, upper_top_width=.55e-3,
    lower_thickness=25e-6, upper_thickness=45e-6,
    lower_height=.35e-3, upper_height=.55e-3,
    gap=.25e-3, gap_lower_height=.1e-3,
    lower_eps_r=3., gap_lower_eps_r=3.2,
    gap_upper_eps_r=4.6, upper_eps_r=5.,
    lower_tan_delta=.01, gap_lower_tan_delta=.015,
    gap_upper_tan_delta=.025, upper_tan_delta=.03,
    offset=.15e-3, box_width=.012,
)
document = CrossSectionDocument(
    section, mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2),
)
assert CrossSectionDocument.loads(document.dumps()).dumps() == document.dumps()
assert section.layers[1].thickness == .1e-3
```

The specified case is checked against independently prescribed four-region
material masks and scikit-fem complex/vacuum assembly (normalized difference
at most `1e-10`), half-mesh changes of at most 1%, and doubled-box changes of
at most 0.5%. Homogeneous/vacuum invariants, positive reciprocal matrices and
horizontal/vertical reflections are checked separately. Vertical reflection
swaps gap materials and replaces the interface distance by `gap - gap_lower_height`.
The equal-gap-material limit matches the three-layer factory within 0.5% on
separately generated fine meshes. These criteria do not establish absolute
physical error, manufacturing calibration or arbitrary thin-layer accuracy.

[한국어](../../locales/ko/pages/packages/sipi/split_gap_broadside.md)

## Saved interface studies and width goals

The template is registered for editable JSON, tolerance studies and design
goals with `z_diff_forward`. Symmetry-based objectives, horizontal fixed
pitch and a two-layer height-sum constraint are inapplicable. Sampling
`gap_lower_height` moves only the material interface; the upper gap thickness
is derived for every sample. Out-of-gap normal samples remain failed rows.
Gap material sweeps and correlated bottom/top width studies use the ordinary
saved execution path. A width goal retains the interface and both gap materials.

```python
from sipi import ImpedanceDesignDocument
from sipi.study import ImpedanceStudyDocument
from sipi.template_document import TemplateSectionDocument

parameters = dict(
    lower_width=.4e-3, lower_top_width=.32e-3,
    upper_width=.7e-3, upper_top_width=.55e-3,
    lower_thickness=25e-6, upper_thickness=45e-6,
    lower_height=.35e-3, upper_height=.55e-3,
    gap=.25e-3, gap_lower_height=.1e-3,
    lower_eps_r=3., gap_lower_eps_r=3.2,
    gap_upper_eps_r=4.6, upper_eps_r=5.,
    lower_tan_delta=.01, gap_lower_tan_delta=.015,
    gap_upper_tan_delta=.025, upper_tan_delta=.03,
    offset=.15e-3, box_width=.012,
)
name = 'split_gap_broadside_stripline'
mesh = dict(edge_size=5e-6, far_size=.25e-3, grade=.2)
editable = TemplateSectionDocument(name, parameters, mesh=mesh)
study = ImpedanceStudyDocument(
    name, parameters, quantity='z_diff_forward', mesh=mesh,
    sampling=dict(kind='sweep', count=2, variables=[
        dict(name='gap_lower_height', lower=.08e-3, upper=.12e-3)]),
)
goal = ImpedanceDesignDocument(
    name, parameters, quantity='z_diff_forward', mesh=mesh,
    variable='lower_top_width', bounds=[.3e-3, .65e-3], target=50.,
    tolerance=.5, search_tolerance=.05,
)
assert ImpedanceDesignDocument.loads(goal.dumps()).dumps() == goal.dumps()
assert len(study.sample_parameters()) == 2
```
