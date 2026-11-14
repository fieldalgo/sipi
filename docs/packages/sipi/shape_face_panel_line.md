# Saved face-metal shape-current lines

`ShapeFacePanelTransmissionLineDocument` uses explicit schema
`sipi.shape-face-panel-transmission-line/1` for the
[straight-face loss API](shape_face_conductor.md), a saved dielectric mesh,
and a uniform-line network. It retains the exact eleven root keys:
`schema`, `cross_section`, `frequency_hz`, `materials`, `conductors`,
`reference`, `ground_thickness_m`, `length_m`, `reference_ohms`, `panel`,
`step_fraction`. Existing schemas and default methods are unchanged.

Each signal's `conductors` entry has exactly `bottom`, `top`, `left`, `right`.
Each law uses the existing transmission-line/7 bulk/explicit roughness or
outside-in layered-metal grammar. `reference` must have `kind: surfaces`,
a bottom law, null top/sides, and exact grounded names. A grounded name takes
one whole-perimeter law or `kind: faces` plus the four face laws. The direct
API's 1..4 finite rectangular/tapered traces, bottom ground/open top/sides,
individual skin/core gates and bounded shape controls remain in force.

Construction and strict normalization check materials and all finite offsets
without solving fields. Duplicate, missing, extra and nonfinite JSON inputs
are rejected. Accessors return detached records. An explicit frequency budget
is checked before execution; it counts frequency samples and does not replace
the face extractor's bounded shared-solve count or control its solve time.

Analysis uses the same PEC face energy/C0/external L as the direct API and
one saved dielectric mesh for C/G on the same signal basis. R is the sum of
surface-resistance weights and L includes internal metal inductance. The
network uses saved length and real positive reference impedance. Matching
basis and C0 does not certify arbitrary geometry or outer-domain accuracy.

This example saves and normalizes without fields; uncomment the last call
to run it. All lengths are metres and frequencies hertz.

```python
from sipi import CrossSection, Layer, Trace, CrossSectionDocument
from sipi import ShapeFacePanelTransmissionLineDocument
from sipi.execution import normalize_saved

section = CrossSection([Layer('uniform', .01105, 4.)], [
    Trace('a', -.0005, .0003, .001, 50e-6, top_width=.00022),
    Trace('guard', 0., .0002, .001, 50e-6, ground=True, top_width=.00012),
    Trace('b', .0005, .0004, .001, 60e-6, top_width=.00055),
], .02)
metal = {'conductivity': 58e6, 'relative_permeability': 1.,
         'roughness': {'kind': 'smooth'}}
faces = {name: metal for name in ('bottom', 'top', 'left', 'right')}
reference = {'kind': 'surfaces', 'bottom': metal, 'top': None, 'sides': None,
             'conductors': {'guard': {'kind': 'faces', **faces}}}
document = ShapeFacePanelTransmissionLineDocument(
    CrossSectionDocument(section, mesh={'edge_size': 10e-6, 'far_size': .0005, 'grade': .1}),
    [1e9, 4e9], materials={}, conductors={'a': faces, 'b': faces}, reference=reference,
    ground_thickness=35e-6, length=.02, panels_per_edge=32, ground_modes=4096)
saved = document.dumps()
assert saved == normalize_saved(saved)
assert ShapeFacePanelTransmissionLineDocument.loads(saved).dumps() == saved
# result = document.analyze()  # Starts fields; result retains R/L/G/C and S.
```

Common execution reports R/L/G/C, network, requested diagnostics and explicit
`conductor_boundaries`: labels, skin depth, roughness, complex Zs, each
resistance contribution and its assigned energy matrix. `current_solver`
has kind `grounded-rectangle-face-capacitance-shape`, raw trace order and
signal/ground flags, ordered face energies, both steps, all face requests and
samples, and the complete original `whole_current` record. Raw face order
is geometry order, while conductor weighting uses signal faces, plane, then
ground groups. Both orders and their labels are retained. Signed face flux
is not inferred; the grouped conservation record remains in `whole_current`.

`ShapeFacePanelLineError` preserves stage, original cause, canonical input,
complete currents when available, and partial current evidence. Whole-current
failure retains its original partial requests; face-current failure also
retains the completed original whole extraction. Later mesh/dielectric/network
failures retain all face records. Interrupts propagate. `execute_saved`
returns `status: failed` with no completed result for these failures;
request receipts and explicit execution-record/2 preserve partial evidence
without rerunning fields. Execution-record/1 keeps its existing rules.

Validation distinguishes actual saved/direct field equality, uniform-medium
identities, independent planar-metal/four-port equations, panel and dielectric
mesh checks, partial failures, and old canonical records. A finite outer
observation is retained as unqualified unless its independent convergence
contract passes. Local coating and roughness limitations remain; no absolute
small-mutual accuracy, browser/EXE or new platform qualification is inferred.
This unit does not add automatic outer refinement or face-metal optimization.
