# Saved lines with panel currents by default

`sipi.transmission-line/8` (`DefaultPanelTransmissionLineDocument` in
`sipi.default_line`) has the fields of [transmission-line/7](line_model.md)
plus the conductor-current method. `surface` and `surface-boundaries`
conductors default to the panel method. Normalization always writes
`current_method`, and for the panel method also `panel`, into the saved
document, so a stored line keeps its method and controls when defaults change.
Transmission-line/1 to /7 documents and their results are unchanged.

| Field | Contract |
|---|---|
| `schema`, `cross_section`, `frequency_hz`, `materials`, `conductor`, `length_m`, `reference_ohms` | as transmission-line/7 |
| `current_method` | `"panel"` or `"volume-p1"`; optional on input, always saved |
| `panel` | panel method only; optional on input, always saved: `panels_per_edge`, `ground_modes`, `interpolation_degree` (no `ground_modes` when bottom, top and sides are all open) |

When `current_method` is omitted, `surface` and `surface-boundaries`
conductors use `panel`. A `perfect` conductor has no default, so name the
method. To use the P1 volume-mesh surface currents, set
`current_method: "volume-p1"`. `panel` is then not allowed.

When `panel` is omitted, the default controls depend on the section:

| Section | Default `panel` |
|---|---|
| bottom ground, open top and sides | `panels_per_edge` 64, `ground_modes` 512, `interpolation_degree` 14 |
| two grounds, open sides | `panels_per_edge` 64, `ground_modes` 512, `interpolation_degree` 14 |
| open bottom, top and sides | `panels_per_edge` 64, `interpolation_degree` 12 |

The defaults are kept in one constant,
`sipi.default_line.DEFAULT_PANEL_CONTROLS`, and saved documents record the
values they used. They were chosen from a scan of all 72 templates with
typical inputs and the templates' default boxes. Going from 64 to 128 panels
per edge changed C0 by at most 1.5e-6 and each current Gram matrix by at most
5.2e-3 of its largest entry. The median panel time was 1.05 times the P1
default-mesh time. Trapezoidal (etched) conductors converge most slowly: their
remaining Gram error at 64 panels is estimated at about 1–2%. For a precision
run, write `panels_per_edge: 128` explicitly. It takes about twice as long and
reduces the Gram change about 2.5 times. Layered coplanar striplines between
two grounds need 37 interpolation boxes and took about 150–200 s, whatever the
panel count.

**Precision conductor loss: write `panels_per_edge` 128 to 256.** An
independent comparison on 2026-11-28 checked the panel conductor loss against
an independent finite-element solution on two sections. With the default 64
panels per edge the panel loss was higher by 0.46 % and 0.23 %. At 128 and
256 panels per edge the difference fell monotonically, and its extrapolation
to infinitely many panels was +0.008 % and +0.005 %. The default 64 is
therefore a few tenths of a percent high in loss; 128 to 256 brings it
closer to the converged value at about two (128) or more (256) times the
panel time. Saved documents keep the panel controls they were written with,
so set the value explicitly. These are observations on two sections, not an
error bound; the default controls are unchanged.

The calculation is the one a [method line](method_line.md) runs with the
same content: `method_document()` returns that
`sipi.method-transmission-line/1` document, and `equivalent_document()` the
panel, two-ground panel, open panel or transmission-line/7 document that runs.
No new numerical path is added. R, L, G, C and S are bit-identical to that
document, and the result keeps this input as `input_json`. `sipi run` and
`execute_saved` add `current_method = {method, equivalent_schema}` to the
equivalent result.

```python
from sipi.default_line import DefaultPanelTransmissionLineDocument

saved = DefaultPanelTransmissionLineDocument(geometry, [1e9, 5e9], materials={}, length=.02,
    conductor=dict(kind='surface', conductivity=58e6, ground_thickness=35e-6,
                   relative_permeability=1., roughness=dict(kind='smooth')))
saved.to_dict()['current_method']   # 'panel', with the default panel controls saved
result = saved.analyze()
```

## What is refused

A refusal never falls back to the P1 method. Each panel refusal says that
`current_method: "volume-p1"` selects P1 explicitly.

- `surface-faces` conductors (per-face metals) have no panel default and are
  refused for the panel method. Name `volume-p1` or use a face panel line
  document.
- Boundary combinations other than the three above, for example grounded
  sides.
- Normalization also refuses what the panel documents check without a field
  solve: conductor kind for the section (two grounds need `surface` or
  `surface-boundaries`), positive conductor thickness, panel controls and the
  conductor and panel-count limits.
- Other limits of the shared panel kernel are checked by `analyze()`: convex
  polygons, the width/height range of the box (one ground [0.25, 4], two
  grounds [0.25, 64], no ground [0.25, 16]), wall clearance and quadrature
  convergence.

Documents that contain a transmission line (circuits, studies, panel lines,
method lines and others) accept transmission-line/1 to /7 and refuse /8 and /9.
They are not silently computed with P1. New container versions admit /8
and /9 explicitly: [`sipi.circuit/2`](circuit_document.md#version-2-default-panel-lines)
runs a nested transmission-line/8 or /9 unchanged, bit-identical to the line alone, as do
[`sipi.network-assembly/2`](network_assembly.md#version-2-default-panel-lines),
[`sipi.network-transforms/3`](network_document.md#version-3-default-panel-lines),
[`sipi.network-band/2`](band.md#version-2-default-panel-lines) and
[`sipi.line-length-design/3`](extracted_length.md#version-3-default-panel-lines).

## Version 9: the recovered method by name

`sipi.transmission-line/9` (the same class, `schema='sipi.transmission-line/9'`)
has the fields of version 8 plus an optional `recovery`. It also admits
`current_method: "volume-p1-recovered"`, only when named. The default stays
`panel`, and panel and `volume-p1` documents run exactly as in version 8.
`recovery` (`support_fraction`, default 0.4 from
`DEFAULT_RECOVERY_CONTROLS`) is written into the saved document. It is
refused with any other method, and `panel` is refused with the recovered
method. Version 8 keeps its two values and refuses `recovery`.
`method_document()` returns a `sipi.method-transmission-line/2` document, which
runs the [recovered line](method_line.md#version-2-recovered-currents).
`perfect` and `surface-faces` conductors are refused for the recovered method.

```python
saved = DefaultPanelTransmissionLineDocument(geometry, [1e9, 5e9], materials={}, length=.02,
    conductor=conductor, current_method='volume-p1-recovered',
    schema='sipi.transmission-line/9')
saved.to_dict()['recovery']   # {'support_fraction': 0.4}
```
