# Saved lines with signal-face surface loss

[한국어](../../locales/ko/pages/packages/sipi/face_line.md)

[Version 5](reference_line.md) also saves separate reference planes, walls and ground traces.

`sipi.transmission-line/4` adds an explicit `surface-faces` conductor record to
the [shared-mesh line document](line_model.md). It reuses the validated
[signal-face surface model](face_conductor.md) and the existing dielectric,
network and circuit APIs. It does not introduce a different field approximation.

```python
import json
from sipi import microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.execution import normalize_saved, execute_saved

cross = CrossSectionDocument(microstrip(width=.5e-3, substrate_height=.5e-3,
    thickness=35e-6, eps_r=4., air_height=1e-3, box_width=4e-3),
    mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05))
def metal(rms=0.):
    return dict(conductivity=58e6, relative_permeability=1.,
        roughness=dict(kind="hammerstad", rms_m=rms))
conductor = dict(kind="surface-faces", ground_thickness=35e-6,
    conductors={"signal": dict(bottom=metal(.5e-6), top=metal(),
                               left=metal(), right=metal())}, reference=metal())
document = TransmissionLineDocument(cross, [1e9, 4e9], materials={},
    conductor=conductor, length=.03, schema="sipi.transmission-line/4")
text = normalize_saved(document.dumps())
report = execute_saved(text, diagnostics=["characteristic"])
assert report["status"] == "complete"
faces = report["result"]["conductor_boundaries"]
assert len(faces["labels"]) == 5
assert faces["current_flux_error"] <= .05
json.dumps(report, allow_nan=False)
```

## Strict inputs and preserved older versions

The top-level fields are the existing `schema`, `cross_section`, `frequency_hz`,
`materials`, `conductor`, `length_m`, `reference_ohms`. `conductor` has exactly
`kind`, `conductors`, `reference`, `ground_thickness`. Its kind is `surface-faces`;
`conductors` maps **every signal name** to an object with exactly `bottom`, `top`,
`left`, `right`. Every face and the one common `reference` are existing metal
records with exactly `conductivity` (S/m), `relative_permeability`, `roughness`.
Roughness explicitly selects smooth, Hammerstad, Groiss, causal Huray or
Cannonball Huray with that model's existing fields and validity rules.

Parsing validates mappings, geometry and every metal/skin-depth condition
before field work. Unknown/missing/duplicate keys, nonfinite numbers, invalid
metals, unsupported polygon/zero-thickness signal faces and inadequate skin
depth reject. No implicit face defaults or guessed roughness conversion occurs.
Input/output dictionaries are detached snapshots. Loading and normalization do
not mesh or solve a field.

The constructor still defaults to version 1. Version 1 keeps `roughness_rms` for
its common surface record; versions 2–4 use the explicit `roughness` object.
Version 3 remains the original per-signal/common-reference metal contract.
Version 4 also accepts the previous `perfect`, `surface` and `surface-boundaries`
records. Versions 1–3 reject `surface-faces`; old readers must not silently read
the new version as a whole-boundary model. Record the exact engine artifact with
saved inputs during unreleased development.

## One mesh, shared C0 and output

`analyze()` creates one cross-section mesh. The face loss model performs one
vacuum current extraction; the dielectric sweep reuses its C0, so the external
inductance and surface currents use the same geometry/basis. The result combines
face R/internal L with dielectric C/G and external L into the existing RLGC
network. It retains the canonical input and direct `FaceConductorLoss` object.
Original depth, good-conductor, current-flux and roughness limits are unchanged.

Common execution retains R/L/G/C, S, names/frequency and optional characteristic
or mode diagnostics. `conductor_boundaries` keeps ordered labels, skin depth,
roughness factor, complex surface impedance and per-face/reference resistance.
Face records additionally retain `surface_current_factors_per_m` (Q),
`current_integrals`, `whole_boundary_current_integrals` and `current_flux_error`.
Q has shape (4N+1,N,N); face and whole-boundary integrated currents have shapes
(4N+1,N) and (N+1,N). Reference is always the final entry. These diagnostics
make partition conservation inspectable; they do not certify resistance accuracy.
Existing whole-boundary output is preserved without these extra face fields.

Existing circuit/assembly/transform sources accept the versioned line through
`{"kind":"transmission-line", "document": ...}`. No new transport or circuit
schema is needed. A saved line's successful execution is separate from physical
validity, convergence, application UI support and platform acceptance.

Tests compare saved RLGC/S to direct face and frequency-dependent dielectric
APIs at `1e-10`, old conductor forms across versions 3/4 at `1e-12`, exact
one-mesh/shared-C0 composition, snapshot/replay and parsing without field work.
They retain face diagnostics, replay a terminated circuit at `1e-10` and exercise
existing line/boundary/execution regressions. Physical field/face/mesh acceptance
remains that of the linked model. Reference-face separation, empirical foil
calibration and full application/platform parity remain separate work.
