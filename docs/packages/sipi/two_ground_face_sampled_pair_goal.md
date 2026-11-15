# Face-metal two-ground goals on a finite frequency grid

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_sampled_pair_goal.md)

`seek_two_ground_face_sampled_forward_pair_impedances` in
`sipi.two_ground_face_sampled_pair_goal` connects the existing bounded finite-grid
search to the explicit [face-metal two-ground line](two_ground_face_panel_line.md). This is a
direct Python API; it does not serialize a callable. The existing
[single-frequency goal](two_ground_face_pair_goal.md) and saved inputs are unchanged.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument
from sipi.two_ground_face_sampled_pair_goal import seek_two_ground_face_sampled_forward_pair_impedances

frequencies = [2e9, 3.5e9, 5e9]
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))

faces = dict(zip(('bottom','top','left','right'),
    [dict(metal,conductivity=sigma) for sigma in (58e6,35e6,21e6,45e6)]))

def make_line(width, gap):
    section = CrossSection([Layer('dielectric', .002, 4., tan_delta=.003)],
        [Trace('positive', x=-(width+gap)/2, width=width, y=.000975, thickness=.00005),
         Trace('negative', x=(width+gap)/2, width=width, y=.000975, thickness=.00005)],
        .008, top='ground')
    return TwoGroundFacePanelTransmissionLineDocument(
        CrossSectionDocument(section, mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05)),
        frequencies, materials={}, conductors=dict(positive=faces,
            negative=dict(zip(faces,reversed(list(faces.values()))))),
        reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
        ground_thickness=35e-6, length=0., panels_per_edge=128, ground_modes=128,
        interpolation_degree=16)

def solve():
    return seek_two_ground_face_sampled_forward_pair_impedances(
        make_line, [[.00035, .0005], [.0002, .0004]], frequencies,
        [[90., 44.5]]*3, tolerances=[[.1, .1]]*3,
        initial=[.00038, .00028], max_evaluations=64)

assert make_line(.00038, .00028).to_dict()['frequency_hz'] == frequencies
```

The example prepares inputs without fields; call `solve()` to run the search.
Lengths are metres, frequencies Hz and impedances ohms. The factory receives
two positive bounded parameters and must return two ordered signals, zero
length and the exact supplied grid of 2..64 increasing positive frequencies.
Signal order and current controls must stay fixed. Every frequency requires two
positive targets and absolute tolerances: Re(Zdd) and Re(Zcc) under separate
Ic=0 and Id=0 launches of the full complex characteristic matrix. These are not
independent propagation-mode impedances. An asymmetric matrix is not replaced
by a symmetric approximation.

`max_evaluations` is an integer from 4 to 10000. It counts uncached whole-grid
attempts, including failed attempts and optimizer probes; it does not count
each frequency as a new manufactured geometry. Three attempts are reserved for
the frozen selected input, without calling the factory again. Volume refinement
halves resolved edge size, far size and grade; panel refinement doubles the
panel count; joint refinement does both. All other physical and current controls
stay fixed. The three inputs must pass resource admission before search fields.

Every refined value must meet its own absolute target tolerance. The original
relative 0.005 limit applies against nominal and from joint to both single-axis
refinements, at every frequency and for both launches. A missed frequency cannot
be hidden by averaging. There is no automatic retry or relaxed acceptance.
These finite comparisons do not guarantee outer-domain adequacy, a continuous
frequency band, uniqueness, a global optimum or measured accuracy.

The returned design preserves parameters, the full grid, targets, tolerances,
history, exact selected/refined inputs, actual current records and dielectric
mesh identities. `SampledPanelForwardPairGoalError` preserves the attempt count,
completed history, failed stage/input and the original typed two-ground cause
chain. Interrupts propagate. The attempt bound is not a memory or time bound.

The physical registration uses the existing uniform epsilon_r=4, tan_delta=.003,
8 mm by 2 mm box with vertically centered 50 um conductors. The first signal
uses bottom/top/left/right conductivities 58/35/21/45 MS/m; the second reverses
those assignments. Both ground foils use 58 MS/m. Nominal panels are 128 and
interpolation degree is 16. At 2, 3.5 and 5 GHz it
requests 90/44.5 ohm with 0.1 ohm tolerances, the bounds/start above and 64 attempts.
Selected and three refined results are checked against an independent complex
matrix square root and uniform-material invariants. Separate 16/32 mm boxes keep
the selected joint geometry/mesh controls and use 512/1024 ground modes; all R,
internal/external L, C, G and C0 entries require relative 0.01 with absolute zero.
Uniform-material C0 scaling makes volume-only equality an analytic property;
it is not evidence of heterogeneous dielectric mesh convergence. Retained test
records state the outcome of these unchanged criteria. No new fixture is fitted
to the optimizer result.

The pinned shared development capability is required, without a fallback solver.
Exact source and installed artifacts, browser Worker and macOS/Windows validation
remain separate acceptance evidence.

Face laws and coatings remain attached to their named physical boundaries
through every frozen refinement. Only the dielectric mesh context is reused;
no whole-boundary current cache substitutes for face-current evaluation. The
prior whole-boundary API and its numerical criteria remain unchanged.

[Save a face-metal finite-frequency goal](two_ground_face_sampled_pair_goal_document.md)
