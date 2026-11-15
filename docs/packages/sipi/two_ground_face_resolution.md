# Finite resolution assessment with physical-face metals

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_resolution.md)

`assess_two_ground_face_line_resolution` accepts explicit
[face-metal lines](two_ground_face_panel_line.md). It assesses volume, panel and
outer-width changes separately while retaining physical-face laws. This is a
direct API; existing whole-boundary inputs and saved schemas remain unchanged.
A completed assessment may be unaccepted. Finite agreement is not an absolute
error estimate or an asymptotic convergence certificate.

The following example prepares the inputs without field work. Uncomment the
last line to execute the complete assessment:

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_resolution import ResolutionTolerance
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument
from sipi.two_ground_face_resolution import assess_two_ground_face_line_resolution
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
finer = dict(panels_per_edge=128, ground_modes=256, interpolation_degree=16)
outer = []
for width, modes in ((.016, 512), (.032, 1024)):
    raw = line.to_dict()
    raw['cross_section']['box']['width'] = width
    for key in ('edge_size', 'far_size', 'grade'):
        raw['cross_section']['mesh'][key] *= .5
    raw['panel'] = dict(finer, ground_modes=modes)
    outer.append(TwoGroundFacePanelTransmissionLineDocument.from_dict(raw))
controls = dict(refined_panel_options=finer, outer_documents=outer,
    refinement_factor=.5, max_solves=6,
    tolerances={key: ResolutionTolerance(.01, 0.) for key in
                ('R', 'L_internal', 'L_external', 'C', 'G', 'C0')})
# Run the six line evaluations explicitly when ready:
# assessment = assess_two_ground_face_line_resolution(line, **controls)
```

The full plan is admitted before fields. It evaluates base, volume-only,
panel-only and joint inputs, followed by explicit wider boxes. `max_solves`
is 5..16 and counts full line attempts, including failures; it does not count
internal linear systems. At least one outer document is required. Volume
refinement scales edge_size, far_size and grade by the stated factor below one.
All three refined panel controls are explicit, none decreases and at least one
increases. Outer inputs retain joint panel resolution, except that ground_modes
may increase to resolve the wider domain.

Outer documents strictly expand open sides without moving either physical
ground plane. They preserve traces, internal interfaces, dielectric models,
frequency and signal order, ports, length, every face metal, coating, roughness
and reference law. These finite open sides have zero normal flux, not radiation
boundary conditions. Whole-boundary inputs are not converted automatically.
There is no fallback, retry, clipping or inferred larger domain.

Select any nonempty subset of R, L_internal, L_external, C, G and C0, with explicit
`ResolutionTolerance(relative, absolute)` in SI units. Each entry at each
frequency uses absolute + relative*max(abs(a),abs(b)), with no small-entry floor.
Volume and panel each compare with base; joint compares with each single axis;
every outer result compares with joint. Unselected quantities are not assessed.
Records retain exact inputs, actual current and mesh observations, differences
and allowances. Exceptions stop later evaluations and retain completed work,
stage, failed input and available typed current/mesh causes. Interrupts propagate.

The registered scalar check uses the example's two dielectric layers at 2/5 GHz.
A second check uses two equal traces, width 0.43 mm, gap 0.28 mm, thickness
50 micrometres, height 0.975 mm in a uniform 2 mm dielectric at 2/3.5/5 GHz.
The traces have reversed face conductivity assignments; both ground metals are
58 MS/m. Both cases use degree16, 64/128 panels, 128/256 ground modes, half-size
volume settings and outer widths16/32mm with512/1024modes. All six selected
matrix quantities must pass relative0.01/absolute0 on every axis. Independent
scalar/matrix square roots check characteristic impedances; the uniform pair
also checks C/G and external-L/C0 identities. Actual observations are recorded
before assertions. Synthetic checks cover every failed stage, entrywise limits,
changed-physics refusals, completed disagreement and interrupts.

These finite cases do not establish adequacy of default modes on arbitrary
large boxes, continuous-band or measured accuracy, all manufacturing geometries,
or browser/platform acceptance. Original failed observations and thresholds
remain unchanged.

[Save a face-metal assessment and partial record](two_ground_face_resolution_document.md)

[Bounded consecutive refinement](adaptive_two_ground_face_resolution.md)
