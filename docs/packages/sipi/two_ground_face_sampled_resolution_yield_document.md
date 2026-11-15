# Saved face-metal frequency-resolution acceptance

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_sampled_resolution_yield_document.md)

`TwoGroundFaceSampledResolutionYieldDocument` stores
`sipi.two-ground-face-sampled-resolution-yield/1`. Its five root keys are
`schema`, `studies`, `acceptance`, `confidence` and `minimum_yield`.
The [direct resolution assessment](two_ground_face_sampled_resolution_yield.md)
contract is unchanged: 2..8 physically identical face-metal IID studies,
distinct mesh/panel controls, one manufacturing denominator and disagreement
or failed grids retained as unresolved. Nested versions, face/ground laws,
ordered frequency arrays and sampling specifications remain explicit.

The following prepares a saved base/joint plan without calculating fields:

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

from sipi.two_ground_face_sampled_resolution_yield_document import TwoGroundFaceSampledResolutionYieldDocument
saved = TwoGroundFaceSampledResolutionYieldDocument([plans[0], plans[3]],
    acceptance=acceptance, confidence=.95, minimum_yield=.8)
assert saved.required_evaluations == 4
assert TwoGroundFaceSampledResolutionYieldDocument.loads(saved.dumps()).dumps() == saved.dumps()
```

`saved.analyze(max_evaluations=4)` executes the four planned whole-frequency rows.
All documents, IID admission, distinct controls and the total planned budget are
checked before fields. The total cannot exceed10000 rows; repeated frequency
points do not add trials. Sample generation is checked before any study starts.
Failures keep their original rows and typed causes, later planned rows still run,
and interrupts propagate. These limits do not bound internal solves, memory or
wall-clock time.

Saved requests and CLI use the same explicit evaluation, input-byte and diagnostic
limits. Unsupported diagnostics and insufficient budgets are refused before field
work. Complete statistical execution does not mean a passing probability target.
Any unknown classification makes execution incomplete; pure resolution disagreement
has no fabricated field error. Saved records/projects reopen all inputs, rows and
causes without solving again. JSON duplicate keys, nonfinite numbers, wrong source
methods and changed physical inputs are refused.

The registered physical example reuses the direct assessment's two seed19 width
samples at2/3.5/5GHz, with base and joint controls. Four extracted rows are checked
against independent matrix-square-root forward impedances, then common execution
replays the captured line results exactly. A separate evidence comparison matches
the direct assessment's original base/joint inputs, values, current and mesh data.
Source and exact installed artifacts run independently. CLI checks retain both
complete and failed-row records through project reopening.

This compares fixed evaluated models. It does not bound discretization error,
prove continuous-band acceptance, estimate measured production yield or qualify
other platforms. Numerical/outer checks and manufacturing distribution validity
remain separate requirements; the small sample example is not a production study.
