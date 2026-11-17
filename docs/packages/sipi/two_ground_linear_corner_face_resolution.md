# Explicit linear corner-current finite resolution

`assess_two_ground_linear_corner_face_line_resolution` from
`sipi.two_ground_linear_corner_face_resolution` compares a saved
`TwoGroundLinearCornerFacePanelTransmissionLineDocument` along separate
current-density and dielectric-mesh axes. Existing saved schemas keep their
own methods; this function does not select or replace an existing engine.

Provide all three `refined_panel_options` explicitly and one or more
`outer_documents` with the same physical conductors, grounds, materials,
frequencies, length and ports. Only side width can expand. Outer inputs must
retain the jointly refined mesh and density controls; ground modes may
increase. All inputs and the full-line solve budget are checked before any
field solve. The shared limit remains512 physical panels and1024 density
unknowns.32 to64 subdivisions fits one and two finite Trace conductors.

The six stages with two outer documents are base, volume-only, current-only,
joint, outer0 and outer1. Compare each single axis with base, joint with each
single axis, and each explicit outer input with joint. Each selected entry of
R, internal L, external L, C, G and vacuum C0 uses the supplied absolute plus
relative times the larger magnitude allowance. There is no denominator floor.
Finite agreement does not establish asymptotic convergence or absolute accuracy.

The result retains exact input JSON, actual dielectric meshes, current solver
records and all completed comparisons. A typed current, mesh, dielectric or
network failure preserves previous work and stops later solves. Completed
but disagreeing values remain unaccepted; interrupts propagate.

Checks use real layered one/two-signal lines with unchanged1% relative and
zero absolute criteria, independent entrywise comparison, field-free invalid
input refusal, typed failure retention and interruption propagation. This
route does not qualify fixed guards, arbitrary conductor count, physical
measurements, browser execution or another platform.

The operation uses request-local exact current reuse (at most eight entries) and bounded mesh snapshots. Six line evaluations remain six budgeted evaluations; identical vacuum geometry/control fields are computed four times with two outer domains. Every call still validates physical/material admission. No cache survives the operation, and no approximate geometry key is used. See the [saved input](two_ground_linear_corner_face_resolution_document.md).
