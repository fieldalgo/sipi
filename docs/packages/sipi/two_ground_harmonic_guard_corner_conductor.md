# Two active traces with a fixed-potential finite guard

The explicit `sipi.two_ground_harmonic_guard_corner_conductor` module provides:

- `two_ground_harmonic_guard_corner_current_factors(section, ...)` for whole boundaries;
- `two_ground_harmonic_guard_corner_face_current_factors(section, ...)` for individual faces;
- `two_ground_harmonic_guard_corner_conductor_loss(section, frequency, ...)` for whole-surface metals;
- `two_ground_harmonic_guard_corner_conductor_loss_by_face(section, frequency, ...)` for face metals.

Supply exactly three finite rectangular or tapered `Trace` objects, exactly one
with `ground=True`. Bottom and top planes are grounded and side boundaries are
open. The two active current coordinates follow the non-grounded traces in
section order. The guard is held at zero voltage and can carry nonzero induced
current. This is a fixed-potential model, not a floating conductor or a finite
termination circuit.

The pinned shared API selects those two active indices directly. The consumer
retains its current basis without a second capacitance reduction. Whole boundary
order is two signals, bottom plane, top plane and guard. Four physical faces per
signal precede both planes and four guard faces in the face result. Each trace
uses bottom/top/left/right in global coordinates, including tapered faces.
Signed current integrals retain conservation; guard losses and off-diagonal
coupling terms are not discarded. C0 and inverse-C0 external inductance retain
the existing vacuum magnetic-exterior contract. Dielectric metadata does not
alter this extraction; nonuniform electric fields are a separate calculation.

All four functions use explicit `panels_per_edge=32`, `ground_modes=256` and
`interpolation_degree=24`. The compact two-mode method permits even subdivisions
10..512 and even modes64..4096, with at most512 physical panels and1024 density
modes. Three quadrilaterals use312 physical panels at32 subdivisions and504 at48.
A control within the integer range can still exceed the total budget or fail
quadrature admission. Refusal has no automatic retry or alternative solver.
Refine panels and finite outer boundaries separately for the required quantities.

Both loss functions require explicit positive frequencies in hertz, `conductors`,
`reference` and `ground_thickness` in metres. `conductors` maps exactly the two
active names to `SurfaceMetal` for whole loss or `TraceFaceMetals` for face loss.
`ReferenceSurfaceMetals` supplies bottom/top laws, `sides=None`, and exactly the
guard name in its `conductors` mapping. Whole loss requires a whole guard law;
face loss accepts either one law expanded uniformly or four distinct guard
laws. Existing skin-depth, remaining-core, coating and roughness restrictions
run before fields. A local planar coating or roughness law does not resolve
coating corners, finite-metal diffusion or measured foil morphology.

R and internal L use the existing signed complex surface impedances times
physical current Grams. All material contributions, including guard faces and
both foils, remain separate in results. Network construction adds external L
and internal L once, retaining the two-current basis and four ports. It does
not add a saved transmission-line schema or target search by itself.

Validation includes direct shared-result identity, face endpoint ownership,
nonzero guard currents, current conservation, immutability, geometry/active
order permutations, whole/uniform-face equivalence, independent smooth-metal
formulas and positive power, passive reciprocal networks, selected guard-face
roughness/coating changes, and no-floor32/48 panel comparison. Invalid section,
material and control admission precedes fields. Request-scoped reuse includes
physical geometry, ground flags, controls and solver identity; failed solves
are not cached. Existing methods and defaults remain unchanged.

The shared field also has independent tapered finite-element and Fourier-circle
reference evidence. These registered geometries and numerical gates do not
certify arbitrary geometry, measurements or an untested operating system.

[Three-active adapter](two_ground_harmonic_three_active_corner_conductor.md) ·
[한국어](../../locales/ko/pages/packages/sipi/two_ground_harmonic_guard_corner_conductor.md)

The separate [saved fixed-guard face line](two_ground_harmonic_guard_corner_face_panel_line.md) connects matched dielectric fields and a four-port network with retained execution evidence.
