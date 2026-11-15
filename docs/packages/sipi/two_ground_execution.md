# Two-ground saved execution

[한국어](../../locales/ko/pages/packages/sipi/two_ground_execution.md)

The shared execution registry includes
`sipi.two-ground-panel-transmission-line/1` with the existing normalization,
execution request, result record, project and CLI APIs. The
[saved line contract](two_ground_panel_line.md) and
[surface-current limits](two_ground_conductor.md) are unchanged. The validated
shared capability is supplied by the exact revision in `dependencies.json`.
Existing extraction defaults are unchanged; unavailable capability is an explicit
failure. Installed artifact checks identify the implementation actually used.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument
from sipi.execution_request import SavedExecutionRequest

metal = dict(conductivity=58e6, relative_permeability=1., roughness={"kind":"smooth"})
section = CrossSection([Layer("uniform", .002, 4.)],
    [Trace("signal", 0., .0007, .0006, .00005)], .008, top="ground")
doc = TwoGroundPanelTransmissionLineDocument(CrossSectionDocument(section),
    [2e9, 5e9], materials={}, conductors={"signal": metal},
    reference=dict(kind="surfaces", bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, length=.02, panels_per_edge=64)
request = SavedExecutionRequest(doc.dumps(), max_evaluations=2,
                                diagnostics=["characteristic"])
assert request.input_json == doc.dumps()
# request.run() calculates using the explicitly installed shared capability.
```

Preparation and normalization remain field-free. Frequency count must not exceed
max_evaluations before any current or volume solve; the budget counts complete
frequency evaluations, not internal matrix operations. The existing generic
minimum/maximum budget and input byte limits remain in force. Optional
characteristic/mode diagnostics use the existing contract and preserve the
completed base result if a diagnostic rejects its input.

Complete results retain SI R/L/G/C, network and diagnostics, individual
conductor-boundary labels, surface impedances, skin depths, roughness factors,
resistance contributions, boundary current Gram matrices and signed currents.
`current_solver` retains the exact panel settings, vacuum C0, grouped and separate
current observations and numerical diagnostics. `dielectric_mesh` identifies the
actual volume mesh. Neither identifier nor a small residual proves convergence.

A typed line failure produces status failed, a null result and the unchanged
stage/cause/input/current/mesh record. Missing shared capability is a current
stage RuntimeError, never a successful result or an automatic alternative.
SavedExecutionRecord binds the receipt and original text to the request digest;
SavedProject preserves and selects it through the existing API. Artifact entries
remain host-declared, not verified merely because they appear in a saved record.
The separate installed-wheel audit supplies actual artifact identity evidence.

Use the existing `python -m sipi validate input.json` or
`python -m sipi run input.json --output result.json`. Existing CLI statuses are
unchanged: input/preparation errors return2; calculation failures, including a
model budget rejected at execution before fields, return1. Output refusal/error
returns3. A failed calculation receipt is preserved when one exists. Output paths
are never silently overwritten. No browser Worker/UI, target solver, tolerance
study, public deployment or Windows executable support is added by this unit.
