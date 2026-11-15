# Saved two-ground face-metal paired goal

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_pair_goal_document.md)

`TwoGroundFaceForwardPairDesignDocument` in `sipi.two_ground_face_pair_goal_document`
stores `sipi.two-ground-face-forward-pair-design/1`. It connects the
[explicit face-metal goal](two_ground_face_pair_goal.md) to shared saved execution,
immutable requests, result records, projects and the CLI. The whole-boundary
schema and all existing documents are unchanged. This is an input contract,
not a new physical approximation or a browser qualification.

The ten root keys are schema, study, conductors, reference, ground_thickness_m,
panel, targets_ohm, tolerances_ohm, initial and max_evaluations. Unknown/missing
keys, duplicate JSON keys and nonfinite numbers are rejected. Each ordered
signal uses bottom/top/left/right metal laws; reference foils and fixed ground
conductors retain the [face-line contract](two_ground_face_panel_line.md).
The new constructor defaults to degree 16; existing document defaults are unchanged.

A study/3 or /4 source supplies exactly two ordered positive bounded variables
with corners sampling, a paired template and one positive frequency. Existing
fixed-pitch and dielectric material-leaf bindings are reused. Nominal, initial
(or midpoint), and all four bound corners must admit the line and all three
future refinements without field calculations. This does not prove validity
throughout the interior. Frozen refinements preserve the named face assignments.

The original direct-goal criteria apply: 4..10000 attempts including failures,
three reserved refinements, both original absolute target tolerances and 0.005
relative comparisons. The host rejects a caller budget below the saved budget
before solving. Top-level line diagnostics are not accepted for a goal.
Failures retain the stage, attempted input, history and original typed face-line
cause. Interrupts propagate. Restoring a saved record/project performs no solve.

This example prepares and round-trips the input without a field solve:

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_face_pair_goal_document import TwoGroundFaceForwardPairDesignDocument

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness=dict(kind="smooth"))

names = ("bottom", "top", "left", "right")
positive = dict(zip(names, [metal(s) for s in (58e6, 35e6, 21e6, 45e6)]))
negative = dict(zip(names, [metal(s) for s in (45e6, 21e6, 35e6, 58e6)]))
study = ImpedanceStudyDocument("coupled_stripline", dict(
    width=.00038, gap=.00028, plane_spacing=.002, eps_r=4.,
    thickness=.00005, tan_delta=.003, box_width=.008, trace_height=.000975),
    sampling=dict(kind="corners", variables=[
        dict(name="width", lower=.00035, upper=.0005),
        dict(name="gap", lower=.0002, upper=.0004)]),
    quantity="z_diff_forward", frequency=2e9, materials={},
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
quantities = ("differential_forward_impedance_real", "common_forward_impedance_real")
document = TwoGroundFaceForwardPairDesignDocument(study,
    conductors=dict(positive=positive, negative=negative),
    reference=dict(kind="surfaces", bottom=metal(58e6), top=metal(58e6),
                   sides=None, conductors={}), ground_thickness=35e-6,
    targets=dict(zip(quantities, [90., 44.5])),
    tolerances=dict(zip(quantities, [.1, .1])), initial=[.00038, .00028],
    panels_per_edge=128, interpolation_degree=16, max_evaluations=64)
text = document.dumps()
assert TwoGroundFaceForwardPairDesignDocument.loads(text).dumps() == text
# Field calculations are explicit: result = document.solve()
```

[Manufacturing samples with fixed face laws](two_ground_face_pair_study.md)
