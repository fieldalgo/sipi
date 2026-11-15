# Saved two-ground face-resolved lines

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_panel_line.md)

`TwoGroundFacePanelTransmissionLineDocument` saves the direct
[face-resolved conductor model](two_ground_face_conductor.md) together with
same-geometry dielectric extraction and the existing RLGC network. Its explicit
schema is `sipi.two-ground-face-panel-transmission-line/1`. Existing
[whole-surface documents](two_ground_panel_line.md) retain their original schema
and meaning.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument

metal = {"conductivity": 58e6, "relative_permeability": 1.0,
         "roughness": {"kind": "smooth"}}
section = CrossSection(
    [Layer("substrate", 0.002, 4.0, tan_delta=0.003)],
    [Trace("signal", x=0.0, width=0.0006, y=0.0007, thickness=0.00005)],
    width=0.008, top="ground",
)
doc = TwoGroundFacePanelTransmissionLineDocument(
    CrossSectionDocument(section, mesh={"edge_size": 5e-6,
                         "far_size": 0.0001, "grade": 0.05}),
    [1e9, 3e9, 10e9], materials={},
    conductors={"signal": {face: metal for face in ("bottom", "top", "left", "right")}},
    reference={"kind": "surfaces", "bottom": metal, "top": metal,
               "sides": None, "conductors": {}},
    ground_thickness=35e-6, length=0.02,
    panels_per_edge=64, interpolation_degree=16,
)
text = doc.dumps()
restored = TwoGroundFacePanelTransmissionLineDocument.loads(text)
result = restored.analyze()
```

The strict top-level fields are `schema`, `cross_section`, `frequency_hz`,
`materials`, `conductors`, `reference`, `ground_thickness_m`, `length_m`,
`reference_ohms` and `panel`. Panel controls are the explicit
`panels_per_edge`, `ground_modes` and `interpolation_degree` values. SI units,
the existing mesh resource limits and all direct face-model admission rules
apply. Signal records contain exactly four named face-metal records. Ground
trace records select either a whole surface law or `kind: "faces"` with four
laws. Existing bulk, rough and planar-coating records are reused.

Normalization performs no field solve and does not require the optional shared
edge capability to be installed. Duplicate keys, unknown/missing nested keys,
nonfinite JSON, unsupported trace shapes, incorrect signal/reference maps,
invalid materials and skin/core violations are refused. Accessors and saved
inputs are detached snapshots. The shared capability and numerical convergence
are checked when analysis actually runs.

Analysis obtains face currents and their original whole-boundary evidence from
one shared current solve. It builds the saved dielectric mesh for the same
section, checks signal ordering, and combines the resulting C/G with the current
model's vacuum C0, external inductance and face-weighted conductor loss. It then
forms the existing transmission-line network. All controls and actual mesh
identity are retained. No current calculation silently switches to a different
field method.

`result.current_record()` uses `kind: "two-ground-rectangle-face-panels"` and
retains face labels, signed currents, current Grams and an embedded
`whole_current` record. `result.mesh_record()` returns the actual dielectric
mesh observation. Both return detached SI dictionaries.

The common saved execution, request, record, project and CLI paths accept this
schema. Frequency-count budgets are checked before fields. Completed receipts
retain the exact input, RLGC, network, optional characteristic/mode diagnostics,
face surface laws and current/mesh records. A staged
`TwoGroundFacePanelLineError` retains the original input, cause and any completed
current or mesh work for failures in material admission, conductor admission,
current calculation, meshing, dielectric extraction or network construction.
Reopening a record or project does not recompute the fields.

The direct model's skin-depth, local planar-coating and finite-outer limitations
remain. A successful saved execution is not a convergence or accuracy
certificate, an eye-diagram calculation, or a new browser form. Independently
validate the geometry, face quantities, dielectric mesh and frequency range
before using a result for engineering decisions. Native/Worker parity and
packaged-platform qualification are separate checks.

[Paired forward-impedance goal with face laws](two_ground_face_pair_goal.md)
