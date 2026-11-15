# Saved two-ground panel line

[한국어](../../locales/ko/pages/packages/sipi/two_ground_panel_line.md)

The saved line API provides `TwoGroundPanelTransmissionLineDocument` in
`sipi.two_ground_panel_line`, with strict schema
`sipi.two-ground-panel-transmission-line/1`. It composes the
[two-ground surface currents](two_ground_conductor.md) with existing
same-geometry dielectric extraction and RLGC networks. It requires the explicit
shared capability from the revision in `dependencies.json`. Saved execution is
registered separately; browser qualification is not implied.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument

metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness={"kind": "smooth"})
section = CrossSection([Layer("uniform", .002, 4., tan_delta=.003)],
    [Trace("signal", 0., .0007, .0006, .00005)], .008, top="ground")
saved = TwoGroundPanelTransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05)),
    [2e9, 5e9], materials={}, conductors={"signal": metal},
    reference=dict(kind="surfaces", bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, length=.02, panels_per_edge=64)
assert saved.loads(saved.dumps()).to_dict() == saved.to_dict()
result = saved.analyze()
assert result.current_record()["boundary_labels"] == [
    "signal:signal", "reference:bottom", "reference:top"]
```

The top-level keys are schema, cross_section, frequency_hz, materials, conductors,
reference, ground_thickness_m, length_m, reference_ohms and panel. Panel keys are
panels_per_edge, ground_modes and interpolation_degree. Coordinates and thickness
are metres, frequency Hz, length metres and reference impedance ohms. Existing
CrossSectionDocument geometry/mesh and dielectric model schemas are reused.
Signal/reference whole-surface metal JSON uses the existing explicit bulk,
roughness and layered-coating contracts. Missing, extra, duplicate or nonfinite
values are rejected; normalization returns detached canonical input and never
solves a field or requires the optional shared capability.

Construction checks material samples, geometry/resource controls, local
skin-depth and remaining-core limits. Analyze requests currents first, then
meshes the exact saved section for dielectric C/G, checks signal order and builds
the existing network. The current solver supplies vacuum C0 and external L.
The existing dielectric implementation scales C0 for exactly homogeneous scalar
coefficients, while heterogeneous or tensor coefficients use the saved volume
mesh. Input geometry and every numerical setting remain in the result. Actual
mesh node, element and boundary-set hashes are exposed by `mesh_record()`.

`TwoGroundPanelLineError` retains stage, cause type, canonical input, any completed
current result, and any completed dielectric mesh identity. Stages are material
admission, conductor admission, current, mesh, dielectric and network. A missing
shared capability is an explicit current-stage failure; no result or convergence
is invented. Records returned by accessors are detached from the object.

Validation includes six actual uniform lines: scalar, symmetric pair and
asymmetric pair, each with common or different top/bottom foil laws at 2 and
5GHz. C=epsilon_r*C0, G=omega*tan_delta*C, L_external*C0=mu0*epsilon0*I and
independently assembled matrix-exponential port-wave conversion are checked.
The original direct-current material observations and all 128 related checks
remain required. A separate registered nonuniform scalar study uses two 1mm
layers (epsilon_r3/tan_delta.002 and epsilon_r5/tan_delta.004), three volume mesh
settings and a finest-mesh complex P2 scikit-fem reference. Its original 1%
adjacent C/G and independent C/G criteria are retained; the accompanying record
states whether they passed. This study is not layered outer-domain convergence.

Current-panel convergence and dielectric-volume convergence are different tests.
These limited checks do not establish general accuracy, spatially magnetic
exteriors, volume conductor diffusion, measured agreement or new platform
support. No existing input schema, threshold, fixture, failed result, default
solver, public deployment or Windows executable is changed.

The separate [saved execution](two_ground_execution.md) adds host/request/record/CLI transport.

[Line-quantity sampling](two_ground_line_study.md) connects scalar impedance,
attenuation or a selected paired launch to ordered geometry/material draws.

[Finite resolution assessment](two_ground_resolution.md) separates volume, panel,
joint and explicit outer-width observations with selected SI allowances.
