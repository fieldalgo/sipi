# Saved lines with an explicit current method

`MethodTransmissionLineDocument` (`sipi.method-transmission-line/1`) wraps a
canonical [transmission-line document](line_model.md) and states which
existing calculation supplies the conductor surface currents. Its fields are
exactly `schema`, `line`, `current_method` and, for the panel method only,
`panel` with `panels_per_edge`, `ground_modes` and `interpolation_degree`.
`current_method` has no default.

| `current_method` | Section | Runs | Conductors |
|---|---|---|---|
| `volume-p1` | any the line accepts | the nested line unchanged (P1 volume-mesh surface currents) | as the line |
| `panel` | bottom ground, open top and sides | [`sipi.panel-transmission-line`](panel_line.md) /1 (nested line /1–/6) or /2 (/7) | perfect, surface, surface-boundaries |
| `panel` | two grounds, open sides | [`sipi.two-ground-panel-transmission-line/1`](two_ground_panel_line.md) | surface, surface-boundaries |

For the panel method a `surface` conductor is passed on as the same metal on
every boundary: `surface-boundaries` with that metal for each signal and the
reference (transmission-line /1 and /2 become /3; a /1 `roughness_rms` becomes
`{"kind": "hammerstad", "rms_m": ...}`). For two grounds, the bottom and top
planes and grounded traces take the reference metal and the open sides none.
`equivalent_document()` returns the document that runs.

```python
from sipi.method_line import MethodTransmissionLineDocument

line = TransmissionLineDocument(geometry, [1e9, 5e9], materials={}, length=.02,
    schema='sipi.transmission-line/2',
    conductor=dict(kind='surface', conductivity=58e6, ground_thickness=35e-6,
                   relative_permeability=1., roughness=dict(kind='smooth')))
saved = MethodTransmissionLineDocument(line, current_method='panel',
    panel=dict(panels_per_edge=64, ground_modes=512, interpolation_degree=14))
result = saved.analyze()
```

## What is checked

- Construction validates the line, the method, the exact keys and, for the
  panel method, everything the panel document checks without a field solve:
  section boundaries, positive conductor thickness, conductor kind, panel
  controls and the conductor/panel-count limits. Other conditions of the
  shared panel kernel (wall clearance, aspect ratio, convexity, quadrature
  convergence) are checked by `analyze()`.
- A refused panel calculation is never replaced by the volume method.
- R, L, G, C and S equal those of the equivalent document bit for bit; the
  result keeps this input as `input_json`. `sipi run` and `execute_saved`
  return the equivalent document's result with
  `current_method = {method, equivalent_schema}` added.

## Why choose explicitly

The P1 volume-mesh surface currents converge slowly. On two microstrips, a
grounded coplanar line and a stripline, P1 was 12–19% below the panel value
with default mesh settings while C0 agreed within 4e-4
([conductor loss](conductor.md)). The panel method is not available for every
section: with typical inputs and the templates' default boxes, 54 of 72
templates compute panel currents with the pinned shared revision (20 before
its interpolation-box and range changes, which admitted ten coupled, layered
and broadside striplines, 21 grounded coplanar and coplanar-stripline
sections nearer the walls than their extent and three layered coplanar
striplines with width/height up to 64). The 18 sections without a bottom
ground are refused. Existing transmission-line documents and their results are
unchanged.
