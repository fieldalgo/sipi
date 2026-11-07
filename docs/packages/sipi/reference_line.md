# Saved lines with separate reference surfaces

[한국어](../../locales/ko/pages/packages/sipi/reference_line.md) · [Reference API](reference_surfaces.md) · [Saved signal faces](face_line.md)

`sipi.transmission-line/5` adds a strict reference-surface variant to the existing
`surface-faces` conductor. Earlier versions keep their meanings and the constructor
still defaults to version 1. Version 5 also accepts all existing perfect, common
surface, boundary-metal and face-metal forms without changing their results.

```python
from sipi import CrossSectionDocument, stripline
from sipi.line_model import TransmissionLineDocument
from sipi.execution import normalize_saved, execute_saved

def metal(sigma=58e6):
    return dict(conductivity=sigma, relative_permeability=1., roughness=dict(kind='smooth'))

cross = CrossSectionDocument(stripline(width=.5e-3, plane_spacing=1e-3,
    thickness=50e-6, eps_r=4., tan_delta=.02, box_width=4e-3),
    mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05))
conductor = dict(kind='surface-faces', ground_thickness=35e-6,
    conductors={'signal': {face: metal() for face in ('bottom', 'top', 'left', 'right')}},
    reference=dict(kind='surfaces', bottom=metal(), top=metal(35e6), sides=None, conductors={}))
line = TransmissionLineDocument(cross, [1e9, 4e9], materials={}, conductor=conductor,
    length=.03, z_ref=75., schema='sipi.transmission-line/5')
assert normalize_saved(line.dumps()) == line.dumps()
report = execute_saved(line.dumps())
assert report['status'] == 'complete'
assert report['result']['conductor_boundaries']['labels'][-2:] == ['reference:bottom', 'reference:top']
```

The `reference` object has exactly `kind='surfaces'`, `bottom`, `top`, `sides`
and `conductors`. Active planes/walls need complete existing metal records;
open boundaries need JSON `null`. `conductors` maps exactly the ground-trace
names to complete metal records, distinct from the outer signal-face mapping.
Each metal record retains `conductivity`, `relative_permeability` and an explicit
supported `roughness`. Ground traces keep one law over their whole perimeter;
both side walls share one law. All grounds remain one PEC potential, not extra ports.

This variant is accepted only for `surface-faces` in version 5. The old untagged
common-reference metal remains valid in versions 4 and 5. Unknown fields, missing
groups, metals on open boundaries, null grounded boundaries, invalid metals,
duplicate JSON keys and nonfinite numbers reject. All geometry, mapping and
local skin-depth gates run during normalization before any field solve.

Analysis reuses the same one-mesh composition: reference and signal current
partitions supply C0 to the dielectric extraction. Shared execution retains every
surface label, skin depth, roughness factor, complex surface impedance, resistance
contribution, Q and integrated current, plus unsplit conductor currents and flux
error. The existing caller frequency budget and diagnostic selection still apply.
No new field solver, current redistribution or physical accuracy is introduced.

The existing circuit source accepts this document. The once-extracted length
search also reuses it without another source kind or search schema:

```python
from sipi.length_design import LineLengthDesignDocument

source = line.to_dict()
source['length_m'] = 0.
plan = LineLengthDesignDocument(dict(kind='transmission-line', document=source),
    limits=[dict(name='insertion', input_port='near:signal', output_port='far:signal',
                 frequency_hz=[1e9, 4e9], minimum=.7, maximum=None)],
    bounds=[0., .5], tolerance=1e-5, max_evaluations=32, schema='sipi.line-length-design/2')
result = plan.solve()
assert result.feasible.passed and not result.infeasible.passed
assert result.to_dict()['source_evaluation']['field_extractions'] == 1
```

Length search keeps its sampled bracket, attempt-budget and failure rules; it
does not establish a global maximum or continuous-band guarantee. The original
field source still needs geometry-specific mesh and outer-domain convergence.

Tests compare saved RLGC/S with separate direct reference-loss and dielectric
APIs within 1e-10, older common-reference forms within 1e-12, and existing circuit
terminal voltages within 1e-10. They verify one mesh/shared C0 identity, detached
canonical replay, strict pre-mesh rejection, all retained diagnostics and one
field extraction for mixed-mode length search. Independent field/plate/convergence
evidence remains in the [reference API](reference_surfaces.md). These are engine
contracts; application pins, measured foil validation and platform acceptance remain separate.

```sh
python -m pytest -q tests/sipi/test_reference_line.py tests/sipi/test_face_line.py tests/sipi/test_line_model.py tests/sipi/test_execution.py tests/sipi/test_extracted_length_design.py
```
