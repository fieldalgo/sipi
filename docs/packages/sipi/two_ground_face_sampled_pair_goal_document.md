# Saved face-metal paired goals at finite frequencies

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_sampled_pair_goal_document.md)

`TwoGroundFaceSampledForwardPairDesignDocument` stores
`sipi.two-ground-face-sampled-forward-pair-design/1`. It connects template/material
inputs and physical-face metal laws to the [direct finite-grid goal](two_ground_face_sampled_pair_goal.md).
It does not serialize a callable or change existing schemas and numerical gates.

This example prepares and normalizes input without field work:

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_face_sampled_pair_goal_document import TwoGroundFaceSampledForwardPairDesignDocument
from sipi.execution import normalize_saved

source = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00038, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, tan_delta=.003, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9, materials={},
    sampling=dict(kind='corners', variables=[
        dict(name='width', lower=.00035, upper=.0005),
        dict(name='gap', lower=.0002, upper=.0004)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
goal = TwoGroundFaceSampledForwardPairDesignDocument(source,
    frequencies=[2e9, 3.5e9, 5e9],
    conductors=dict(
        positive=dict(zip(('bottom','top','left','right'),
            [dict(metal,conductivity=s) for s in (58e6,35e6,21e6,45e6)])),
        negative=dict(zip(('bottom','top','left','right'),
            [dict(metal,conductivity=s) for s in (45e6,21e6,35e6,58e6)]))),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=128, ground_modes=128,
    interpolation_degree=16,
    targets=dict(differential_forward_impedance_real=[90., 90., 90.],
                 common_forward_impedance_real=[44.5, 44.5, 44.5]),
    tolerances=dict(differential_forward_impedance_real=[.1, .1, .1],
                    common_forward_impedance_real=[.1, .1, .1]),
    initial=[.00038, .00028], max_evaluations=64)
text = goal.dumps()
assert normalize_saved(text) == text
```

`goal.solve()` or `execute_saved(text, max_evaluations=64)` runs the search.
Lengths are metres, frequencies Hz and targets/tolerances ohms. Require 2..64
strictly increasing positive frequencies and one positive finite target and
absolute tolerance per named quantity per frequency. Study/3 or /4 anchors the
first frequency, with exactly two positive bounded corner variables. Existing
material-leaf and fixed-pitch bindings apply. Signal faces, coatings, roughness
and reference metals remain fixed during the search.

Normalization admits nominal, initial/midpoint and four corner inputs across
the complete grid, including all three future volume/panel/joint refinements.
It performs no field solve and does not prove every interior point is feasible.
Missing, unknown, duplicate, nonfinite and malformed fields are refused. The
saved 4..10000 whole-grid attempt budget must fit the caller limit. Input-byte
limits and unsupported diagnostics are checked before search fields.

The direct algorithm preserves full complex forward-launch targets and three
reserved frozen refinement attempts. Every frequency must satisfy its absolute
target and the original 0.005 relative refinement gates. Failed uncached attempts
count toward the budget. Failed execution retains the frequency vector, stage,
input, history and typed current or dielectric cause details; interrupts propagate.
Requests, records and projects reopen without another solve. CLI input files
remain unchanged while output receipts are written. Only successful dielectric
meshes are reused inside the request; whole-boundary current reuse is not selected.

The physical transport check repeats a complete saved search at 2/3.5/5 GHz,
90/44.5 ohms with 0.1 ohm tolerances, initial width/gap 0.38/0.28 mm, and
64 attempts. An independent geometry factory repeats the full direct search;
the complete results must be exactly equal. Template inputs use a `dielectric`
layer name and explicit minimum angle, so the earlier direct fixture's `uniform`
label and omitted default are recorded separately rather than represented as
identical input bytes. The previous direct study's independent matrices,
refinements and finite outer-domain checks remain separate numerical evidence.

A separate CLI case starts at the previously selected width/gap
0.0004327005475196886/0.0002901571356784889 m and uses four attempts, including
three refinements. Synthetic checks cover strict fields, 64 frequencies, later
material refusal, corner/initial factories, material and fixed-pitch bindings,
failed attempts, budgets and record restoration. No continuous-band accuracy,
measured equivalence, arbitrary outer-domain adequacy or platform/browser release
acceptance follows. The exact pinned shared capability remains required.
