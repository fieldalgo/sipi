# Face-metal manufacturing samples across finite frequencies

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_sampled_pair_study.md)

`TwoGroundFaceSampledForwardPairStudyDocument` stores
`sipi.two-ground-face-sampled-forward-pair-study/1`. It connects ordered geometry
and dielectric samples to [face-metal lines](two_ground_face_panel_line.md) at
2..64 explicitly increasing positive frequencies. Each manufactured row keeps
one geometry/material sample across the grid, with fixed physical-face metal,
coating, roughness and reference laws. Re(Zdd) and Re(Zcc) describe separate
Ic=0 and Id=0 forward launches, not independent propagation modes.

The following example prepares input without solving:

```python
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import DebyeDielectric
from sipi.two_ground_face_sampled_pair_study import TwoGroundFaceSampledForwardPairStudyDocument

source = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00043, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9,
    materials={'dielectric': DebyeDielectric(3., (.7,), (1e9,))},
    sampling=dict(kind='corners', variables=[
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
assert len(study.samples()) == 2
```

`study.analyze(max_evaluations=2)` or shared `execute_saved` performs the
calculation. Lengths are metres, frequencies Hz and results ohms. The source
study anchors the first frequency. Original study/3 and /4 geometry/material
bindings, fixed pitch, seed, corner/sweep/IID and correlation semantics remain.
Sampled dielectric models keep their frequency dependence. There is no separate
resampling at each frequency and no automatic refinement or failed-row retry.

The budget counts full manufactured rows, including failures, rather than
individual frequencies. It accepts 2..10000; an insufficient limit is refused
before fields. Nominal full-grid normalization is field-free but does not prove
all sampled inputs feasible. Unknown, missing, duplicate, malformed and nonfinite
fields are rejected. A failed frequency makes its entire row unknown. Invalid,
duplicate and correlated rows retain their original order and sample values.

Each row retains the resolved material, exact line input, failure phase, typed
cause and available current/mesh evidence. Later rows still execute; interrupts
propagate. Summaries exist only when every row succeeds, and describe the
stated sample set. They do not establish production yield, confidence bounds
or continuous-band performance. Successful dielectric meshes may be reused
within this request; the whole-boundary current cache is not selected.
Existing single-frequency methods and saved schemas remain unchanged.

Shared requests, result records, projects and CLI files preserve complete or
incomplete execution. Restoring the result does not calculate. Caller budgets,
input-byte limits and unsupported diagnostics retain pre-field admission.

The physical check uses two width endpoints 0.43/0.44 mm with gap0.28mm,
2mm plane spacing, 50micrometre thickness and height0.975mm in an8mm box.
At2/3.5/5GHz, the uniform dielectric has eps_inf3, strength0.7 and pole1GHz.
The two signals have reversed face conductivity assignments and both grounds
use58MS/m. Every grid is compared with separate single-frequency RLGC at1e-12
and exact current/mesh identity; independent complex-matrix forward values
use1e-10. Original Debye C/G-to-C0 and external-L identities remain required.

Both endpoints also receive a separate [finite resolution assessment](two_ground_face_resolution.md):
64/128panels,128/256modes,degree16, volume settings halved independently,
joint refinement and16/32mm boxes with512/1024modes. All entries of R,
internal/external L,C,G,C0 use relative0.01/absolute0. Observations precede
assertions. Synthetic checks cover independent modal/statistical references,
64frequencies, correlations, failed phases, preserved face/coating laws,
material bindings, budgets and CLI restoration. This does not qualify arbitrary
boxes, all materials, continuous bands, measured accuracy or other platforms.

[Joint IID acceptance across the grid](two_ground_face_sampled_pair_yield.md)
