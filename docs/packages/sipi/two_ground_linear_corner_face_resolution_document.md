# Saved linear corner-current finite comparisons

`TwoGroundLinearCornerFaceResolutionDocument` from
`sipi.two_ground_linear_corner_face_resolution_document` uses schema
`sipi.two-ground-linear-corner-face-resolution/1`. It saves an explicit linear
corner face line, all refined panel controls, outer line documents, refinement
factor, full-line solve budget and selected SI relative/absolute allowances.
See [finite resolution](two_ground_linear_corner_face_resolution.md).

Normalization validates every planned stage before fields and preserves
existing schema bytes. JSON is strict: unknown/duplicate keys, nonfinite values,
wrong line types, missing absolute tolerances and unsupported units are refused.
The saved request/CLI/project paths use the same six-stage calculation.

Completed disagreement is a completed but unaccepted result. A typed failure
retains the original failed input, current/mesh evidence and completed prefix;
execution-record/2 validates that prefix against the saved plan on restoration,
without solving again. Execution-record/1 cannot carry this partial variant.
Interrupts propagate. Imported artifact declarations are not installed-file proof.

Current and mesh reuse is local to this operation, exact and bounded. It does
not reduce the recorded number of line evaluations or bypass geometry, material,
skin-depth, capability and resource admission. This method provides finite
agreement, not an absolute error bound or physical measurement qualification.

[한국어](../../locales/ko/pages/packages/sipi/two_ground_linear_corner_face_resolution_document.md)
