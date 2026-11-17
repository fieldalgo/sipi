# Linear corner-density currents

[한국어](../../locales/ko/pages/packages/sipi/two_ground_linear_corner_conductor.md)

`two_ground_linear_corner_conductor` explicitly selects the two-mode corner
field in the exact development `galerkin` dependency. It supports one or two
finite rectangular or tapered `Trace` signals between two grounded planes,
with open sides. It refuses grounded traces and other polygon types. This is
homogeneous vacuum current extraction: dielectric metadata does not change
these magnetic-exterior factors. Dielectric-interface corner fields and
finite-metal diffusion are not solved here.

```python
from sipi.two_ground_linear_corner_conductor import (
    two_ground_linear_corner_face_current_factors,
)

factors = two_ground_linear_corner_face_current_factors(
    section, panels_per_edge=32, ground_modes=256, interpolation_degree=24,
)
```

The section uses metre dimensions. Each Trace retains bottom, top, left and
right faces, followed by bottom and top reference foils. Current integrals
are signed and dimensionless for unit signal currents; squared-current
factors have units `1/m`. `C0` is vacuum capacitance in `F/m`. Results retain
immutable arrays and the explicit method diagnostic
`two-ground-linear-corner-power-all-active`. The adapter preserves shared
active-current factors directly and performs no basis congruence transform.

Each edge has `panels_per_edge - 6` physical panels, each with a constant-mass
and a zero-mass linear corner-density mode. Even subdivisions start at 16;
the 512 physical panel limit admits at most 134 subdivisions for one Trace
and 70 for two. The default is 32, and explicit refinement to 64 fits both.
The adapter checks the budget before shared solver lookup. Ground modes are
even 64–4096 and interpolation degree is fixed at 24. No fallback changes
these inputs. Numerical residual, current conservation and physical
face-partition checks retain their original limits.

Use `two_ground_linear_corner_current_factors` for whole boundaries.
`two_ground_linear_corner_conductor_loss` and
`two_ground_linear_corner_conductor_loss_by_face` reuse the existing whole
and face surface-metal laws. Material, frequency, remaining-core and foil
thickness admission precede the field solve. Resistance is in `ohm/m` and
internal inductance in `H/m`; these are surface perturbation estimates.
Existing coating/roughness applicability restrictions remain in force.
A face law does not resolve microscopic roughness or coating corners.

This direct API does not change existing solver defaults, saved JSON
schemas, resolution/goal/study documents or browser execution. Existing
[corner currents](two_ground_corner_conductor.md) remain available. Use
[the exact artifact setup](../../development.md) rather than relying on a
package version string to identify the required unreleased shared API.

Validation covers physical face mapping, shared-to-product current identity,
actual single/pair panel refinement, independent surface-impedance frequency
laws, dissipated power, reciprocal passive networks, immutable outputs and
admission ordering. The shared engine separately checks analytical moments,
circular limiting geometry, registered P3 comparisons and finite outer
changes. A passing finite refinement comparison is not absolute accuracy,
physical measurement validation, other-platform support or complete 2D
coverage. Refine both panel resolution and the finite outer domain for each
quantity used in a design.

The separate [saved face line](two_ground_linear_corner_face_panel_line.md) connects this explicit current method to matched dielectric fields and execution replay.

The separate [three-active harmonic current adapter](two_ground_harmonic_three_active_corner_conductor.md) keeps its own admission, physical panel budget and method identity.
