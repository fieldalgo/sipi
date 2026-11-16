# Finite corner-current line resolution

`assess_two_ground_corner_face_line_resolution` in
`sipi.two_ground_corner_face_resolution` compares explicit
[corner-power face line](two_ground_corner_face_panel_line.md) calculations.
It does not change existing line or resolution methods or saved schemas.

Supply a line, all three `refined_panel_options`, one or more explicit
`outer_documents`, and a nonempty `tolerances` mapping. Supported quantities
are `R`, `L_internal`, `L_external`, `C`, `G`, `C0`; each value must be a
`ResolutionTolerance(relative, absolute)` with the absolute term in SI.
There is no default numerical acceptance tolerance. `refinement_factor`
defaults to 0.5 and `max_solves` to 6 (allowed 5–16).

The assessment evaluates base, volume-only, panel-only, joint and each outer
line. Volume refinement multiplies the explicitly supplied mesh edge size,
far size and grade by the factor. Panel controls cannot decrease and at least
one must increase. Interpolation stays at the supported degree 24. Each outer
line keeps joint mesh and subdivisions; only ground modes may increase.
Width must expand while the physical ground planes, conductors, dielectric
interfaces, metal laws, frequencies, length and ports remain unchanged.
All planned inputs and the full-line budget are admitted before fields.

Comparisons are volume/base, panel/base, joint/volume, joint/panel and each
outer/joint. Every selected matrix entry at every frequency must satisfy
`abs(new-old) <= absolute + relative*max(abs(new), abs(old))`. There is no
relative denominator floor; zero allowances require exact agreement.
Small mutual entries remain part of the test. Unselected quantities are not
assessed. The budget counts full-line evaluations, not internal linear solves.

The immutable result retains inputs, separate numerical axes, current settings,
actual meshes, differences and allowances. A completed disagreement is
`completed=True, accepted=False`. A failed line retains all previously
completed evaluations and its typed current/mesh error; later solves stop.
A comparison failure retains the just-completed line. Interrupts propagate.
The record scope is `two-ground-corner-face-finite-resolution-not-absolute-accuracy`.
This function does not add a saved resolution schema, automatic refinement,
optimization or manufacturing-study acceptance.

Finite agreement is a necessary observation, not an absolute error estimate,
asymptotic convergence proof or measured-foil qualification. Default line
controls alone do not establish agreement. Independent current and network
references remain required alongside these comparisons; a failed observation
must not be replaced by a passing geometry or relaxed allowance.
