# Saved finite corner-line comparisons

`TwoGroundCornerFaceResolutionDocument` in
`sipi.two_ground_corner_face_resolution_document` stores
`sipi.two-ground-corner-face-resolution/1`. It wraps the explicit
[finite corner comparison](two_ground_corner_face_resolution.md); previous
line, resolution and execution-record formats keep their meaning.

Construct it with a corner-face line and explicit `refined_panel_options`,
`outer_documents`, `tolerances`, `refinement_factor` and `max_solves` controls.
The defaults for the last two are 0.5 and 6; numerical allowances have no
default. JSON contains `schema`, `line`, `refined_panel`, `outer_lines`,
`refinement_factor`, `max_solves`, `tolerances`. Tolerances use SI quantity
names and explicit `relative`/`absolute` values. Each nested line retains its
separate current and dielectric-mesh controls. Missing/extra keys, duplicate
JSON keys, nonfinite values and altered physical outer-domain plans are refused.

Normalization, request preparation, project reopening and result-record loading
perform no field solve. `analyze(max_evaluations=...)` and saved execution
check the full-line evaluation budget before solving. The document preserves
the selected finite comparison axes and every actual input; it does not
silently increase a budget or change an allowance.

`normalize_saved`, `execute_saved`, `SavedExecutionRequest`, the CLI and
`SavedProject` share the same contract. A completed comparison can have
`accepted=False`; this is a numerical disagreement, not a missing result.
A failed comparison retains completed evaluations, current/mesh records and
the failed planned input. `SavedExecutionRecord(...,
schema='sipi.execution-record/2')` can retain this partial-result failure;
version 1 still refuses a non-null failed result. Typed cause details, planned
count, exact input prefix and failure stage are checked when restoring it.
The envelope is structural, not a signature or proof that declared artifacts
were executed or numerical results are physically accurate.

Tests cover strict field-free admission, budget refusal, actual saved
execution, completed disagreement, every staged failure, interrupts,
record/project reopening and tampered partial evidence. Finite entrywise
agreement is not an absolute error bound, general convergence proof, physical
calibration or new platform qualification. Old schemas never select this
current method implicitly.
