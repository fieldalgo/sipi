# Saved three-active finite-resolution assessments

`TwoGroundHarmonicThreeActiveCornerFaceResolutionDocument` from
`sipi.two_ground_harmonic_three_active_corner_face_resolution_document` stores
an explicit [finite-resolution assessment](two_ground_harmonic_three_active_corner_face_resolution.md).
Its schema is `sipi.two-ground-harmonic-three-active-corner-face-resolution/1`.
It reuses the same six-stage operation; a JSON round trip does not choose a
different solver or reinterpret an existing saved line.

The input contains the base line, all three refined panel controls, explicit
outer line documents, volume refinement factor, full-line solve budget and
selected SI quantity allowances. Every allowance declares both `relative`
and `absolute`. No denominator floor or inferred default accuracy is added.
All nested inputs and budgets are checked before fields. The three active
traces, physical planes, materials, frequencies, ports and length must match
the direct assessment contract.

Use `SavedExecutionRequest` or `sipi run INPUT --output RECEIPT --max-evaluations 6`.
A completed calculation with disagreements has `completed=true` and
`accepted=false`; completion does not mean finite agreement. A typed field
failure retains the exact failed input and completed current/mesh history,
stops subsequent work, and produces a failed execution receipt. Keyboard
interrupts propagate. The result can be stored in a `SavedExecutionRecord`
and attached to a project without rerunning fields during restoration.
Partial failed results require execution-record schema version 2 and are
bound to the exact planned stage and completed prefix.

Tests cover strict fields and SI names, budgets before fields, all six failed
stages, changed partial-record rejection, project restoration, CLI transport,
and an actual saved six-stage receipt matching the complete direct assessment
exactly. The physical example retains the registered 1% relative and zero
absolute criteria; they are finite agreement criteria, not measurement or
universal accuracy certification. This schema does not imply a scalar or
paired target for three signals, fixed-guard support, UI parity or another
platform.

[한국어](../../locales/ko/pages/packages/sipi/two_ground_harmonic_three_active_corner_face_resolution_document.md)
