# Saved panel lines without a ground plane

[한국어](../../locales/ko/pages/packages/sipi/open_panel_line.md)

`OpenPanelTransmissionLineDocument` (`sipi.open-panel-transmission-line/1`)
is the [panel line](panel_line.md) for sections whose bottom, top and sides
are all open, such as the unbacked coplanar templates. There is no ground
plane: the grounded traces are the reference and carry the whole return
current. Its fields are exactly `schema`, `line` and `panel`. `panel` holds
`panels_per_edge` (1–256) and `interpolation_degree` (10, 12, 14 or 16); there
are no ground modes. The nested line is transmission-line /1 through /7 with a
`perfect` or `surface-boundaries` conductor and positive conductor thickness.

```python
from sipi import CrossSectionDocument
from sipi.templates import unbacked_coplanar
from sipi.line_model import TransmissionLineDocument
from sipi.open_panel_line import OpenPanelTransmissionLineDocument

metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
line = TransmissionLineDocument(CrossSectionDocument(unbacked_coplanar(width=.3e-3, gap=.2e-3,
    ground_width=1e-3, substrate_height=.2e-3, eps_r=4, thickness=35e-6)), [1e9, 5e9],
    materials={}, length=.02, schema='sipi.transmission-line/3',
    conductor=dict(kind='surface-boundaries', ground_thickness=35e-6,
                   conductors={'signal': metal}, reference=metal))
saved = OpenPanelTransmissionLineDocument(line, panels_per_edge=64, interpolation_degree=12)
result = saved.analyze()
```

The vacuum currents come from the shared open-box panel solver
(`galerkin.laplace_open_box`). It uses zero normal flux on all four box
walls, the same open boundaries as the volume mesh, and holds every grounded
trace at zero voltage. They supply the vacuum capacitance and external L. The
existing dielectric solver supplies C and G on the saved volume mesh, and the
existing per-boundary surface laws give R and internal L, with one reference
metal shared by all grounded traces. `ground_thickness` enters the same
reference skin-depth check as the volume route. Construction and normalization
solve no field. The shared kernel's admission (convex polygons, width/height in
[0.25, 16], wall-scaled interpolation boxes) and its 1e-10 refinement checks
run in `analyze()`. A refusal is never replaced by the volume method.

`execute_saved` and `sipi run` return the line result. They add
`current_solver.kind = "open-rectangle-panels"`, the settings, the grounded
trace names, vacuum capacitance, surface-current factors and solver
diagnostics. The diagnostics include `smooth_interpolation_boxes` and
`charge_sum_error`.

On the three unbacked coplanar templates (single, coupled, asymmetric) the
panel vacuum capacitance agrees with an independent scikit-fem P2 solution on
the default mesh within 5e-4 (1.1e-4 measured,
`tests/sipi/test_open_panel_line.py`). The P1 volume surface currents of the
same section are lower than the panel currents, as for the grounded panel
route. The shared solver's analytic and series references are listed on its
own page. These are finite comparisons, not general accuracy qualifications.
[Explicit current method](method_line.md) selects this document for open
sections.
