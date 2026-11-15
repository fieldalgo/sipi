# Reuse within two-ground manufacturing studies

The scalar line-quantity, paired and finite-frequency paired study documents
reuse successful current factors and detached meshes within one synchronous
`analyze()` call. This helps material-only samples with identical geometry;
it does not reuse dielectric matrices, metal-law evaluation, line networks or
sampled outputs. Every row retains its own material input and field evaluation.

The existing sample order, correlation, preflight budget, all failed rows,
diagnostics and summaries remain unchanged. A successful reusable geometry
calculation is not another independent sample or convergence result. Statistical
yield and candidate-selection consumers retain their original trial counts and
unknown-row treatment; each underlying study has a separate scope.

The [current key and eight-entry limit](two_ground_current_reuse.md) and
[detached mesh snapshots and two-entry/64 MiB array limit](two_ground_mesh_reuse.md)
remain unchanged. Different geometry or mesh controls cause a miss. Mesh keys
include the original cross-section material metadata, even when only field
material overrides vary. No process-wide cache or cross-candidate cache is added.
Input and material admission still run for every row; failures are never stored
as reusable current or mesh results. Nested requests restore the outer scope,
and completion, errors and interrupts clear each request's temporary storage.

Verification uses four predeclared material samples (uniform Debye strength
from 0.5 to 0.9, seed 19), separately for scalar attenuation at 2 GHz, two launch
impedances at 2 GHz, and the same pair on 2/3.5/5 GHz. Complete saved receipts,
inputs, row values, current and mesh records and statistics must match execution
with reuse disabled. Shared current and mesh calls each fall from four to one
for these fixed geometries while the four material-dependent values differ.
Existing geometry studies and independent physical/reference/refinement checks
remain required. These cases do not establish arbitrary-geometry accuracy,
measured production yield, elapsed-time speedup or support on another platform.

[한국어](../../locales/ko/pages/packages/sipi/two_ground_study_reuse.md)
