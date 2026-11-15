# Two-ground line-quantity manufacturing studies

[한국어](../../locales/ko/pages/packages/sipi/two_ground_line_study.md)

`TwoGroundLineQuantityStudyDocument` stores
`sipi.two-ground-line-quantity-study/1`. One scalar `z0` source can select
`impedance_real` (Re(Zc), ohms) or `attenuation` (Re(gamma), Np/m).
A `z_diff_forward` source selects `differential_forward_impedance_real` or
`common_forward_impedance_real`, the Re(Zdd)/Re(Zcc) full characteristic
matrix diagonals under separate Ic=0/Id=0 launches. They are not independent
modes, finite terminal impedance or insertion loss. For both paired values
in one result, use the [paired study](two_ground_pair_study.md).

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_line_study import TwoGroundLineQuantityStudyDocument
source = ImpedanceStudyDocument('offset_stripline',
    dict(width=.0006, plane_spacing=.002, trace_height=.0007, eps_r=4.,
         thickness=.00005, tan_delta=.003, box_width=.008),
    quantity='z0', frequency=2e9, materials={},
    sampling=dict(kind='sweep', count=3, variables=[
        dict(name='width', lower=.00055, upper=.00065)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
study = TwoGroundLineQuantityStudyDocument(source, quantity='attenuation',
    conductors=dict(signal=metal),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=64, ground_modes=128, interpolation_degree=12)
assert TwoGroundLineQuantityStudyDocument.loads(study.dumps()).dumps() == study.dumps()
assert len(study.samples()) == 3
```

The example prepares input without fields. Call `study.analyze(max_evaluations=3)`
or the common saved execution API to calculate. Lengths are metres, frequency
Hz; a line is created at zero length with a 50-ohm network reference. Neither
selected characteristic impedance nor attenuation depends on that reference.
Study/3 or /4 supplies ordered geometry/material samples and constraints.
Separate whole-surface metal laws and panel controls remain fixed. Normal
sampling explicitly stores its correlation matrix, including [[1.]] for one
variable. Missing, extra, duplicate and nonfinite fields are refused.

Source cardinality, metal laws and skin/core restrictions are checked before
fields; nominal preflight does not prove every sample valid. Generate and budget
all samples before any solve. Attempt duplicates and later rows after failures;
never clip, resample or discard a failed row. Each row retains original values,
resolved geometry/materials, exact line input, the selected quantity or failure
phase, typed line cause, and completed current/mesh evidence. Summaries require
all rows to succeed. They are descriptive, not yield or confidence bounds.
Partial saved execution is `incomplete`; requests, records and projects preserve
it without recomputation when reopened. Interrupts propagate.

The quantity diagnostic and ordered loop are shared with the existing FEM
study, with explicit line/error/row/result adapters. This does not substitute a
FEM current method: [two-ground panels](two_ground_panel_line.md) remain explicit
and require the pinned shared capability. Existing methods and schemas retain
their calculations and refusal rules.

The registered finite-domain check varies offset-stripline width .55/.60/.65mm
at 2GHz, using 64/128/256 panels per edge. Both adjacent R/L/C0 changes must meet
relative0.01 and absolute0. Complex sqrt(Z/Y) and sqrt(ZY) independently check
scalar impedance and propagation at every level. These checks do not establish
outer convergence, empirical loss accuracy, every template/frequency or another
platform. Volume/dielectric refinement remains a separate line-extraction gate.

A [one-variable goal](two_ground_line_goal.md) uses the same line quantities
and requires separate volume, panel and joint refinements.
