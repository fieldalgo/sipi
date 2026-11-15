# Saved two-ground paired goals on a finite frequency grid

[한국어](../../locales/ko/pages/packages/sipi/two_ground_sampled_pair_goal_document.md)

`TwoGroundSampledForwardPairDesignDocument` stores
`sipi.two-ground-sampled-forward-pair-design/1`. It connects template/material
inputs to the [direct finite-grid goal](two_ground_sampled_pair_goal.md), without
serializing a Python callable or changing existing saved schemas.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_sampled_pair_goal_document import TwoGroundSampledForwardPairDesignDocument
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
goal = TwoGroundSampledForwardPairDesignDocument(source,
    frequencies=[2e9, 3.5e9, 5e9],
    conductors=dict(positive=metal, negative=metal),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=128, ground_modes=128,
    interpolation_degree=12,
    targets=dict(differential_forward_impedance_real=[90., 90., 90.],
                 common_forward_impedance_real=[44.5, 44.5, 44.5]),
    tolerances=dict(differential_forward_impedance_real=[.1, .1, .1],
                    common_forward_impedance_real=[.1, .1, .1]),
    initial=[.00038, .00028], max_evaluations=64)
text = goal.dumps()
assert normalize_saved(text) == text
```

The example prepares and validates input without fields. `goal.solve()` or
`execute_saved(text, max_evaluations=64)` performs the search. Lengths are metres,
frequencies Hz and targets/tolerances ohms. Each named quantity requires one
positive finite entry per frequency, including interior frequencies. The source
study anchors the first frequency. Its study/3 or /4 corner sampler must contain
exactly two positive bounded variables. Material-leaf bindings and fixed geometry
constraints retain their existing meaning; whole-surface metal laws stay fixed.

Normalization validates nominal, initial/midpoint and four bound corners across
the complete grid, together with the three future volume/panel/joint refinements.
It does not solve fields or certify all interior points. Unknown, duplicate,
missing, nonfinite and malformed fields are rejected. The saved attempt budget
is 4..10000; a smaller caller budget, an insufficient input-byte limit or an
unsupported diagnostic request is rejected before search fields.

The direct API preserves full complex forward-launch targets, uncached-attempt
accounting, three reserved frozen refinements and the original absolute and
relative 0.005 criteria. There is no per-frequency resampling, automatic retry,
clipping or continuous-band guarantee. Failed execution retains the frequency
vector, completed history, attempt count, failed input, stage and typed current
or dielectric cause details. Interrupts propagate. A failed goal has a null result
and its evidence in the error; the existing version-1 record contract applies.
Saved requests, records and projects reopen without running another solve.

The registered physical transport check freezes the initial width/gap selected
by the separately recorded 33-attempt direct study: .00043331845625629 m and
.00028959075290925696 m. With the original 2/3.5/5 GHz, 90/44.5 ohm targets and
0.1 ohm tolerances, the saved and independently constructed direct factories each
use four attempts. Their complete results are compared exactly. This checks
transport of one selected case, not a new optimization or independent physical
accuracy reference. The direct study's original matrix, refinement and finite
outer checks remain separate evidence. No reference arrays or tolerances are
changed to match the selected geometry.

Source and installed-artifact validation do not establish browser, macOS, Windows
or public deployment acceptance. The explicitly pinned shared numerical
capability is required; there is no fallback to another field method.

[Identical current factors are reused within a request](two_ground_current_reuse.md); line attempts and numerical criteria remain unchanged.

Identical successful meshes are reused only inside one paired request; see [mesh reuse](two_ground_mesh_reuse.md) for snapshot isolation and resource bounds.
