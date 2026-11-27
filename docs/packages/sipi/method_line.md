# Saved lines with an explicit current method

`MethodTransmissionLineDocument` (`sipi.method-transmission-line/1`) wraps a
canonical [transmission-line document](line_model.md) and states which
existing calculation supplies the conductor surface currents. Its fields are
exactly `schema`, `line`, `current_method` and, for the panel method only,
`panel` with `panels_per_edge`, `ground_modes` and `interpolation_degree`
(without `ground_modes` when bottom, top and sides are all open).
`current_method` has no default. [Transmission-line/8](default_line.md) saves
the same choice in the line itself, defaults to `panel` for `surface` and
`surface-boundaries` conductors and runs through this document.

| `current_method` | Section | Runs | Conductors |
|---|---|---|---|
| `volume-p1` | any the line accepts | the nested line unchanged (P1 volume-mesh surface currents) | as the line |
| `panel` | bottom ground, open top and sides | [`sipi.panel-transmission-line`](panel_line.md) /1 (nested line /1–/6) or /2 (/7) | perfect, surface, surface-boundaries |
| `panel` | two grounds, open sides | [`sipi.two-ground-panel-transmission-line/1`](two_ground_panel_line.md) | surface, surface-boundaries |
| `panel` | open bottom, top and sides (grounded traces only) | [`sipi.open-panel-transmission-line/1`](open_panel_line.md) | perfect, surface, surface-boundaries |

For the panel method a `surface` conductor is passed on as the same metal on
every boundary: `surface-boundaries` with that metal for each signal and the
reference (transmission-line /1 and /2 become /3; a /1 `roughness_rms` becomes
`{"kind": "hammerstad", "rms_m": ...}`). For two grounds, the bottom and top
planes and grounded traces take the reference metal and the open sides none;
with no ground plane the grounded traces share the reference metal.
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
section, but with typical inputs and the templates' default boxes all 72
templates compute panel currents with the pinned shared revision. Before its
interpolation-box and range changes, 20 did. Those changes admitted ten
coupled, layered and broadside striplines, 21 grounded coplanar and
coplanar-stripline sections nearer the walls than their extent, and three
layered coplanar striplines with width/height up to 64. The 18 sections with
no ground plane use the [open-box panel line](open_panel_line.md). Other
boundary combinations (for example grounded sides) are refused. Existing
transmission-line documents and their results are unchanged.

## Version 2: recovered currents

`sipi.method-transmission-line/2` admits the same `panel` and `volume-p1`
values with the same meaning and the same equivalent documents, plus
`volume-p1-recovered`. Version 1 keeps exactly its two values and refuses the
third with a pointer to version 2. A published schema names the values it
accepts: a version-1 document with a new value would be refused by released
readers, and a reader could not tell from the schema which calculation a
value means, so the value set is extended by a new version instead of
widening `CURRENT_METHODS`, which stays `('panel', 'volume-p1')`.
`METHODS_BY_SCHEMA` lists the values of each version.

`volume-p1-recovered` requires `recovery` with `support_fraction` in
(0, 0.5) and runs `sipi.recovered-transmission-line/1` (`RecoveredTransmissionLineDocument`
in `sipi.recovered_line`). That document keeps the nested transmission-line/1
to /7 and its saved mesh. It replaces only the surface-current factors with
[`recovered_surface_current_factors`](conductor.md) on that mesh, with the
same P1 basis and C0. C, G and external L are therefore bit-identical to
`volume-p1`, and R and internal L use the same surface-impedance laws with the
recovered factors.

| Conductor | `volume-p1-recovered` |
|---|---|
| `surface` | one factor matrix for every surface, as `volume-p1` |
| `surface-boundaries` | per-boundary factors with each signal's and the reference metal |
| `perfect` | refused: no surface current loss; use `volume-p1` |
| `surface-faces` | refused: the recovery has no per-face factors |

Corners other than convex right angles (trapezoid, acute, re-entrant),
supports reaching another conductor or meeting an open wall with a normal
component, and a boundary-gradient flux error above 5% are refused by
`analyze()` with the reason. A refusal is never replaced by another method.
`sipi run` and `execute_saved` add `current_method` and `current_solver`
(`kind`, `settings`, `diagnostics` with `support_width`, `clearance`,
`support_triangles`, `corners` and `gradient_current_error`, the factors and
current integrals).

```python
saved = MethodTransmissionLineDocument(line, current_method='volume-p1-recovered',
    recovery=dict(support_fraction=0.4), schema='sipi.method-transmission-line/2')
result = saved.analyze()
```
