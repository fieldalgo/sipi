# Fixed face-metal candidates across frequency samples

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_sampled_pair_selection.md)

`TwoGroundFaceSampledForwardPairSelectionDocument` stores
`sipi.two-ground-face-sampled-forward-pair-selection/1`. Each of 1..32 fixed named
candidates supplies a complete [face-metal frequency study](two_ground_face_sampled_pair_study.md)
and a nonnegative cost in one stated unit. Frequency vectors and acceptance arrays
must match exactly. Metal faces, references, materials, panel settings and IID
sampling remain explicit. Preparation below does not solve fields.

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

from sipi.two_ground_face_sampled_pair_selection import TwoGroundFaceSampledForwardPairSelectionDocument
candidates = []
for index, (lower, upper) in enumerate(((.00043, .000435), (.000435, .00044))):
    raw = study.to_dict()
    raw['study']['sampling']['variables'] = [dict(name='width', lower=lower, upper=upper)]
    candidates.append(dict(name='fixed-'+str(index), cost=index+1., study=raw))
acceptance = dict(
    differential_forward_impedance_real=dict(minimum=[100.]*3, maximum=[103.]*3),
    common_forward_impedance_real=dict(minimum=[50.]*3, maximum=[52.]*3))
selection = TwoGroundFaceSampledForwardPairSelectionDocument(candidates,
    cost_unit='relative', acceptance=acceptance, minimum_yield=.1, confidence=.9)
assert TwoGroundFaceSampledForwardPairSelectionDocument.loads(selection.dumps()).dumps() == selection.dumps()
```

`selection.analyze(max_evaluations=8)` evaluates all eight planned rows. Every
candidate and sample-generation operation is checked before the first field solve.
Budget counts every planned row; finding an early qualified candidate does not stop
the family. Failures remain unresolved in the original denominator and later
candidates still run. Interrupts propagate without returning a partial selection.

Each row is one [joint event](two_ground_face_sampled_pair_yield.md) across both
quantities and all supplied frequencies. The original conservative exact-float
Bonferroni allocation divides the family error budget by candidate count, not
frequency or quantity count. Candidates may be dependent; rows in each candidate
must follow its stated IID uniform or normal model. Each keeps exact
Clopper–Pearson bounds covering every possible completion of unknown labels.

The cheapest qualified fixed member is selected; original order breaks ties.
A cheaper undetermined candidate remains visible and may actually be feasible.
`none-certified` requires all members to fail the probability target; unresolved
statistical decisions yield `undetermined`. A zero probability target can qualify
an all-unknown member without erasing its unknown rows or [0,1] interval. Selection
is conditional on the model and finite family, not a global or continuous optimum.

The physical test fixes the example's two width distributions before solving,
with four draws each, seed19, Debye materials, 2/3.5/5 GHz and face conductivities
58/35/21/45 MS/m in opposing orders. All frequencies must meet Zdd100–103 ohms
and Zcc50–52 ohms. Family confidence0.9 allocates candidate confidence0.95.
The requested probability0.1 illustrates the contract; it is not a production
target. Independent classification and binomial intervals determine qualification
and the cost decision. Earlier endpoint field, mesh, panel and outer checks are
separate evidence, not uncertainty estimates for every random row.

CLI, saved requests, records and projects retain all candidate inputs, attempts,
classifications, current/mesh evidence and typed failures. Any unknown row makes
execution incomplete even if selection succeeds. Restoring records does not solve
again. Checks include independent intervals, arbitrary candidate dependence,
unequal counts, ties, unknown cheaper candidates, preflight budgets, strict source
types, malformed inputs and interruption. No adaptive resampling, continuous-band
guarantee, measured production yield or platform qualification is implied.
