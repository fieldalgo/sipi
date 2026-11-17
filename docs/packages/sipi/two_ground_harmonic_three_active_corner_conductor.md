# Three-active harmonic corner currents and surface loss

The explicit `sipi.two_ground_harmonic_three_active_corner_conductor` module
connects the bounded shared three-active field to existing physical surface
metal laws. It admits exactly three finite rectangular or tapered `Trace`
conductors between two grounded planes, open sides, and no grounded finite
trace. Existing one/two-conductor and other current methods are unchanged.

The four callables are `two_ground_harmonic_three_active_corner_current_factors`,
`two_ground_harmonic_three_active_corner_face_current_factors`,
`two_ground_harmonic_three_active_corner_conductor_loss`, and
`two_ground_harmonic_three_active_corner_conductor_loss_by_face`.
They retain the existing result contracts: physical vacuum C0 in F/m, current
Gram in 1/m, R in ohm/m, and internal inductance in H/m. Every signal retains
bottom/top/left/right faces; the two plane contributions remain distinct.
The field already uses the three independent active-current bases, so its
matrices are copied without a spurious identity solve or guard reduction.

Controls are explicit: 32 subdivisions per edge, 256 fine ground modes and
interpolation degree24 by default. Even subdivisions start at10; the512
physical-panel cap limits three four-sided Traces to48 subdivisions. The
32-to48 comparison therefore refines the current density without raising
that cap. Each panel has two static spatial modes. Even ground modes64..4096
remain available. Panel, volume-dielectric and finite outer comparisons have
separate meanings; this adapter does not choose them automatically.

Whole-metal and face-metal inputs use existing `SurfaceMetal`, layered metal,
`TraceFaceMetals` and `ReferenceSurfaceMetals` contracts. Material/skin-depth,
remaining-core, coating and roughness admission precede fields. The current
extraction is the homogeneous magnetic exterior; dielectric metadata does not
enter its vacuum C0/current factors. Surface impedance changes reweight each
physical face independently. This is surface perturbation, not finite-metal
diffusion, general microscopic roughness or measured foil fitting.

A distinct private request-cache namespace allows exact current reuse inside
an existing synchronous scope. Geometry, labels, controls and solver identity
must agree. Failed fields are never cached; all admission still runs. Nothing
is reused across scopes. Reusing currents never skips face-metal evaluation.

Validation uses three unequal tapered traces and independent smooth-surface
impedance at1/3/10GHz, positive power, a reciprocal/passive six-port network,
face-specific perturbations, immutable physical conversion, current conservation
and32/48 refinement without denominator floors. Independent shared field
references and numerical/outer gates remain separate evidence. The exact
pinned shared wheel must provide the explicit capability; no fallback occurs.

This callable layer does not add a saved line/study/goal schema, UI workflow,
fixed-ground trace support, absolute accuracy, measurement or another-platform
qualification. Three-signal target design requires its own quantity contract.

[Linear one/two-active currents](two_ground_linear_corner_conductor.md) ·
[한국어](../../locales/ko/pages/packages/sipi/two_ground_harmonic_three_active_corner_conductor.md)

The separate [saved three-active face line](two_ground_harmonic_three_active_corner_face_panel_line.md) connects matched dielectric fields and a six-port network with retained execution evidence.
