# Bounded refinement of two-ground face-metal lines

[한국어](../../locales/ko/pages/packages/sipi/adaptive_two_ground_face_resolution.md)

`refine_two_ground_face_line_resolution` extends the explicit
[finite resolution comparison](two_ground_face_resolution.md) to two through
four predeclared refinement levels. It preserves the same physical ground planes,
face-metal laws, dielectric models, port ordering and original current gates.
It does not select a new default solver or infer unspecified future panel settings.

The example constructs a plan without field calculations:

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_resolution import ResolutionTolerance
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
section = CrossSection([
    Layer('lower', .001, 3., tan_delta=.002),
    Layer('upper', .001, 5., tan_delta=.004)],
    [Trace('signal', 0., .0007, .0006, .00005)], .008, top='ground')
line = TwoGroundFacePanelTransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05)),
    [2e9, 5e9], materials={}, conductors=dict(signal=dict(zip(('bottom','top','left','right'),
        [dict(metal,conductivity=s) for s in (58e6,35e6,21e6,45e6)]))),
    reference=dict(kind='surfaces', bottom=metal, top=dict(metal, conductivity=21e6),
                   sides=None, conductors={}),
    ground_thickness=35e-6, length=.02, panels_per_edge=64, ground_modes=128,
    interpolation_degree=16)
from sipi.adaptive_two_ground_face_resolution import (
    TwoGroundFaceResolutionRefinement, refine_two_ground_face_line_resolution)
steps = []
mesh = line.to_dict()['cross_section']['mesh']
for level in (1, 2):
    for key in ('edge_size', 'far_size', 'grade'):
        mesh[key] *= .75
    panel = dict(panels_per_edge=64*2**level, ground_modes=128*2**level,
                 interpolation_degree=16)
    outer = []
    for width, modes in ((.016, 256*2**level), (.032, 512*2**level)):
        raw = line.to_dict()
        raw['cross_section']['box']['width'] = width
        raw['cross_section']['mesh'] = dict(mesh)
        raw['panel'] = dict(panel, ground_modes=modes)
        outer.append(TwoGroundFacePanelTransmissionLineDocument.from_dict(raw))
    steps.append(TwoGroundFaceResolutionRefinement(panel, outer))
controls = dict(refinements=steps, refinement_factor=.75, max_solves=9,
    tolerances={key: ResolutionTolerance(.01, 0.) for key in
                ('R', 'L_internal', 'L_external', 'C', 'G', 'C0')})
assert len(steps) == 2
# Run the bounded plan explicitly when ready:
# assessment = refine_two_ground_face_line_resolution(line, **controls)
```

Each level compares volume/base, panel/base, joint/volume and joint/panel for every
selected entry and frequency. Two consecutive levels must pass before any outer
check is run. A failed level resets that count. The previous joint calculation is
reused as the next base. The example performs nine complete line batches and ten
comparisons when accepted. Outer domains keep the same ordered sizes across levels;
only ground modes may increase relative to that level's joint panel controls.

All planned levels and outer inputs are admitted before fields. Mesh controls
must use the exact sequential refinement values; multiplying once by a power can
round differently and is not the same strict input. The example therefore updates
its mesh dictionary at each level. Physical dimensions, materials and tolerance
values are never repaired. `max_solves` is8..32 whole-line attempts, not a bound
on internal solves, memory or time. Three next-level batches and every outer check
must fit the remaining budget before the level starts.

The result distinguishes `accepted`, `resolution-unaccepted`, `outer-unaccepted`,
`budget-exhausted` and `field-failed`. Level/outer disagreement is a completed but
unaccepted plan. Budget exhaustion and field failure are incomplete. A selected
joint evaluation exists only after two consecutive passes and all outer checks.
Outer disagreement stops without trying extra levels. Typed failures retain the
exact attempted input, prior results and current/dielectric-mesh observations;
interrupts propagate. `to_dict()` includes all comparisons and original observations.

Registered layered scalar and uniform Debye paired examples use64→128→256 panels,
128→256→512 ground modes, degree16 and sequential mesh factor0.75. The selected
level's16/32mm outer boxes use1024/2048 modes. Six matrix quantities use1% relative
and zero absolute entrywise comparisons without a small-entry floor. Independent
matrix-square-root forward impedances use1e-10; the paired case additionally checks
uniform Debye C/G and vacuum LC invariants. Synthetic cases exercise every stage,
last-frequency mutual entries, count resets, later-plan rejection, budget reserves,
outer stops, immutable plan snapshots and typed failures.

These are finite agreement checks on the stated cases, not a discretization-error
bound, asymptotic convergence proof, measured accuracy certificate, continuous-band
guarantee or platform qualification. A shared systematic error can remain despite
agreement. Original numerical tolerances and existing methods are unchanged.

[Saved bounded plans and partial evidence](adaptive_two_ground_face_resolution_document.md)
