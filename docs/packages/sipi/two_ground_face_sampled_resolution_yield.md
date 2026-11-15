# Joint face-metal acceptance across explicit resolutions

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_sampled_resolution_yield.md)

`assess_two_ground_face_sampled_pair_resolution_yield` compares 2..8 completed
[face-metal frequency studies](two_ground_face_sampled_pair_study.md) without
solving fields. All inputs, ordered frequencies, face/ground metal laws, material
models and sample specifications must match. Only the explicit volume mesh and
panel controls may differ, and duplicate control sets are refused. Changing the
box or a ground plane is a physical input change and is refused here; assess
[finite outer agreement](two_ground_face_resolution.md) separately.

This example prepares four explicit plans without running them:

```python
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import DebyeDielectric
from sipi.two_ground_face_sampled_pair_study import TwoGroundFaceSampledForwardPairStudyDocument

source = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00043, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9,
    materials={'dielectric': DebyeDielectric(3., (.7,), (1e9,))},
    sampling=dict(kind='uniform', count=4, seed=19, variables=[
        dict(name='width', lower=.00043, upper=.00044)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
study = TwoGroundFaceSampledForwardPairStudyDocument(source,
    frequencies=[2e9, 3.5e9, 5e9],
    conductors=dict(
        positive=dict(zip(('bottom','top','left','right'),
            [dict(metal,conductivity=s) for s in (58e6,35e6,21e6,45e6)])),
        negative=dict(zip(('bottom','top','left','right'),
            [dict(metal,conductivity=s) for s in (45e6,21e6,35e6,58e6)]))),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=64, ground_modes=128,
    interpolation_degree=16)
assert TwoGroundFaceSampledForwardPairStudyDocument.loads(study.dumps()).dumps() == study.dumps()
assert len(study.samples()) == 4

from sipi.two_ground_face_sampled_resolution_yield import assess_two_ground_face_sampled_pair_resolution_yield
plans = []
for phase in ('base', 'volume', 'panel', 'joint'):
    raw = study.to_dict()
    raw['study']['sampling']['count'] = 2
    if phase in ('volume', 'joint'):
        for key in ('edge_size', 'far_size', 'grade'):
            raw['study']['mesh'][key] *= .5
    if phase in ('panel', 'joint'):
        raw['panel'].update(panels_per_edge=128, ground_modes=256)
    plans.append(TwoGroundFaceSampledForwardPairStudyDocument.from_dict(raw))
acceptance = dict(
    differential_forward_impedance_real=dict(minimum=[100.]*3, maximum=[103.]*3),
    common_forward_impedance_real=dict(minimum=[50.]*3, maximum=[52.]*3))
assert len(plans) == 4 and all(len(p.samples()) == 2 for p in plans)
```

After explicitly running each plan with `p.analyze(max_evaluations=2)`, pass the
four study results to `assess_two_ground_face_sampled_pair_resolution_yield`,
with `acceptance=acceptance`, `confidence=.95` and `minimum_yield=.8`.
The direct assessor itself performs no field solve and does not choose a mesh.

A row's event is the intersection of both impedance limits at every supplied
frequency. One manufactured sample passes if every resolution passes, fails if
every resolution fails, and is otherwise unresolved, including an original field
failure. The denominator remains two in this example, not eight evaluations or
24 frequency points. The original exact binomial envelope includes every possible
completion of unresolved labels. All original rows, values, failures, current
observations and meshes remain under their resolution's input. Input and row
validation is structural, not authentication of manually assembled field data.

The registered Debye example uses uniform widths0.43–0.44mm, gap0.28mm, seed19,
two samples and 2/3.5/5GHz. Base controls are64 panels/128 ground modes/degree16;
volume refinement halves edge/far/grade, panel refinement uses128/256/16, and
joint applies both. All six R/internal-L/external-L/C/G/C0 matrix quantities use
1% relative, zero absolute entrywise finite comparisons without a floor between
base and each refined case, and between joint and each separate axis. Independent
matrix square roots check forward impedances at1e-10; uniform Debye C/G and
vacuum LC invariants remain separate checks. Limits Zdd100–103/Zcc50–52 ohms
specify the joint event, not a field-accuracy tolerance. Independent per-entry
classification and binomial bounds check the combined decision.

Two samples only illustrate transport. Agreement cannot detect shared systematic
error, bound discretization error, certify asymptotic convergence, acceptance
between frequency points or measured production yield. There is no automatic
refinement, outer-box variation, adaptive sampling or platform qualification.
Synthetic tests exhaust two/three-resolution truth tables and unknown completions,
retain one denominator up to eight resolutions, reject changed physics and other
current methods, preserve original failures, and check immutable results.
