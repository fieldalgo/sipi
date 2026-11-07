# Saved lines with separate ground faces

[한국어](../../locales/ko/pages/packages/sipi/ground_face_line.md) · [Ground-face API](ground_faces.md) · [Reference groups](reference_line.md)

`sipi.transmission-line/6` saves four surface laws on each finite rectangular or
tapered ground trace. It extends the existing `surface-faces` conductor and
`reference.kind='surfaces'`. All older conductor forms remain available. The
constructor still defaults to version 1; loading never promotes an old schema.

```python
from sipi import CrossSectionDocument, coplanar_stripline
from sipi.line_model import TransmissionLineDocument
from sipi.execution import normalize_saved, execute_saved, saved_schemas

def metal(sigma=58e6):
    return dict(conductivity=sigma, relative_permeability=1., roughness=dict(kind='smooth'))

faces = ('bottom', 'top', 'left', 'right')
section = coplanar_stripline(width=.5e-3, gap=.2e-3, ground_width=.5e-3,
    plane_spacing=1e-3, trace_height=.4e-3, thickness=50e-6, eps_r=4., tan_delta=.02, box_width=4e-3)
cross = CrossSectionDocument(section, mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05))
left = dict(kind='faces', **{face: metal() for face in faces})
left['top'] = metal(58e6/4)
reference = dict(kind='surfaces', bottom=metal(), top=metal(), sides=None,
    conductors={'ground_left': left, 'ground_right': metal()})
line = TransmissionLineDocument(cross, [1e9, 4e9], materials={}, length=.03, z_ref=75.,
    conductor=dict(kind='surface-faces', ground_thickness=35e-6,
        conductors={'signal': {face: metal() for face in faces}}, reference=reference),
    schema='sipi.transmission-line/6')
assert normalize_saved(line.dumps()) == line.dumps()
assert line.to_dict()['schema'] in saved_schemas()
report = execute_saved(line.dumps())
assert report['status'] == 'complete'
labels = report['result']['conductor_boundaries']['labels']
assert 'reference:ground:ground_left:top' in labels
assert labels[-1] == 'reference:ground:ground_right'
```

Each named ground value is either the existing complete metal record, covering
its whole perimeter, or exactly `{kind: "faces", bottom, top, left, right}`.
Each face requires `conductivity`, `relative_permeability` and explicit
`roughness` with its existing model contract. Signal faces retain their untagged
four-field record. Planes and walls retain one metal each; open boundaries are
null. All grounded traces must be named, including those using a whole metal.

Version 5 still rejects four-face ground records. Unknown or missing fields,
duplicate JSON keys, nonfinite values, thin/polygon face assignments, expanded
label collisions and each face's skin-depth violation reject before meshing.
Normalization returns a detached canonical snapshot without solving fields.
The [API's geometry, skin-depth and current-conservation limits](ground_faces.md)
apply unchanged. All reference conductors share one PEC potential.

Analysis makes one geometry mesh and one shared vacuum current extraction,
passing the same C0 to dielectric extraction. Execution retains expanded labels,
skin depth, roughness factor, surface impedance, resistance contributions, Q,
face currents and unsplit currents. A single extraction means one unit-voltage
field per signal, not one scalar solve for every possible cross section.

Existing circuit sources accept this version. A length search freezes its RLGC
once and then reuses the existing sampled bracket and evaluation budget:

```python
from sipi.length_design import LineLengthDesignDocument

source = line.to_dict()
source['length_m'] = 0.
plan = LineLengthDesignDocument(dict(kind='transmission-line', document=source),
    bounds=[0., .5], tolerance=1e-5, max_evaluations=32,
    limits=[dict(name='insertion', input_port='near:signal', output_port='far:signal',
                 frequency_hz=[1e9, 4e9], minimum=.7, maximum=None)],
    schema='sipi.line-length-design/2')
result = plan.solve()
assert result.feasible.passed and not result.infeasible.passed
assert result.to_dict()['source_evaluation']['field_extractions'] == 1
```

Tests compare separate Python API RLGC/S and circuit replay within 1e-10,
uniform ground faces against the old whole-perimeter model within 1e-12, and
frozen-RLGC length histories exactly. An independent scikit-rf DistributedCircuit
comparison requires absolute S error below 1e-10 using the same extracted RLGC;
it validates network propagation, not the field extraction. Prior independent
finite-element, wide-foil and mesh/box evidence remains in the ground-face API.
Saved transport introduces no new physical accuracy claim, continuous-band
guarantee, app integration or Windows acceptance.

```sh
python -m pytest -q tests/sipi/test_ground_face_line.py tests/sipi/test_reference_line.py tests/sipi/test_face_line.py tests/sipi/test_execution.py tests/sipi/test_extracted_length_design.py
```
