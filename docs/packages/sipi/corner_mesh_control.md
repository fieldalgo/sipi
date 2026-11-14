# Explicit corner mesh targets

`CrossSection.mesh`, `mesh_settings` and `analyze` accept an optional
`corner_size` in metres. It must be a finite real value with
`0 < corner_size <= edge_size`, using the resolved `edge_size` when that
option is omitted. Booleans are rejected.

```python
from sipi import stripline

section = stripline(width=.0006, plane_spacing=.002, eps_r=4.,
                    thickness=.0004, box_width=.008)
settings = section.mesh_settings(edge_size=1e-5, far_size=.0002,
                                 grade=.15, corner_size=2.5e-6)
assert settings['corner_size'] == 2.5e-6
# field = section.mesh(**settings)
# parameters = field.line_parameters()
```

The size target is the minimum of `corner_size + grade * corner_distance`,
`3 * edge_size + grade * trace_distance` and `far_size`. Corners include
the existing trace and local dielectric-region vertices. This keeps the
face target separate from the corner target. With zero grade, the corner
target applies throughout the domain. These are mesher targets, not a
guarantee of exact element lengths or monotonically increasing node counts.

Omitting `corner_size`, or passing `None`, preserves the original resolved
four-key settings and mesh. Explicit `corner_size=edge_size` requests the
same target function. Geometry, materials, mesher ordering and boundary
labels are unchanged. To refine all length scales, halve `corner_size`
together with `edge_size`, `far_size` and `grade`; retain `min_angle`.

This option is currently a direct Python mesh control. Existing saved
cross-section versions 1–3 reject it, as do their saved study and goal paths.
Do not insert the key into an old document or discard it when recording an
experiment. Store the explicit Python settings separately until a versioned
saved contract supports this control.

Validation covers rectangular, tapered, polygonal and local-region sections:
default mesh identity, geometry area and material labels, homogeneous
capacitance scaling, separate finite mesh/outer comparisons and an independent
quadratic finite-element capacitance calculation. Those finite observations
do not certify absolute accuracy, surface-loss convergence, or all geometries.
Small mutual loss terms require their own entrywise convergence checks.

[한국어](../../locales/ko/pages/packages/sipi/corner_mesh_control.md)
