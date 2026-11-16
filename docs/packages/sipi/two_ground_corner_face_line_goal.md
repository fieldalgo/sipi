# Bounded corner-current line goals

`seek_two_ground_corner_face_line_quantity` in
`sipi.two_ground_corner_face_line_goal` searches one positive geometry parameter
using an explicit `TwoGroundCornerFacePanelTransmissionLineDocument` factory.
The bounded search supports `impedance_real`, `attenuation`,
`differential_forward_impedance_real` and `common_forward_impedance_real`.
The latter two use the full forward characteristic matrix and its separate
mixed-coordinate launches; they are not independent eigenmode impedances.
Use one positive frequency, zero line length and fixed panel controls.

## Refinements and finite limits

The 5..10000 evaluation budget counts failed attempts and reserves three
refinements. The frozen selected input is evaluated with half the resolved
edge/far/grade, double the current panel count, and both changes. Ground modes,
interpolation degree, physical face laws, frequency and ordered signal names
stay fixed. Inputs that cannot be refined are refused before field work.
No factory recall, clipping, fallback or different current method is used.

Every refined value must meet the original absolute target tolerance. Each
must change by at most 0.005 relative to nominal, and the joint result must
agree with each single-axis result at that same limit. A zero comparison
allows only zero; there is no denominator floor. Finite agreement is not
an outer-domain check, an absolute error bound or proof of a unique design.
Use the [separate resolution assessment](two_ground_corner_face_resolution.md)
for explicit wider-domain comparisons.

## Records and validation

The design retains the exact selected document, attempt history, refined
inputs and actual current/mesh records. A typed goal failure retains completed
history, failed input and the original staged cause. Interrupts propagate.
The callable is not serialized; this unit adds no saved goal or study schema.

Structural checks exercise all four quantities, budget reservation, failures
at every attempt, control drift, interrupts and each independent acceptance
gate. The registered physical scalar case seeks 58 ohm at 2 GHz within 0.05 ohm
for width 0.55..0.65 mm, using 128/256 current panels, fixed 256 ground modes
and degree24. Every returned field is checked against scalar `sqrt(Z/Y)` and
`sqrt(Z*Y)` identities. These checks qualify only their stated cases and
artifacts; they do not establish measured-foil or another-platform accuracy.

[한국어](../../locales/ko/pages/packages/sipi/two_ground_corner_face_line_goal.md)

## Saved goal input

The [separate saved goal](two_ground_corner_face_line_goal_document.md) binds one source interval, target and budget to this direct adapter without serializing a callable.
