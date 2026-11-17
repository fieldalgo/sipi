# Three-active harmonic-current finite resolution

Use `assess_two_ground_harmonic_three_active_corner_face_line_resolution` from
`sipi.two_ground_harmonic_three_active_corner_face_resolution` with a saved
[three-active line](two_ground_harmonic_three_active_corner_face_panel_line.md).
It compares current-density and dielectric-mesh refinements separately for
exactly three finite rectangular or tapered Trace conductors between two
physical grounded planes. This is a direct Python operation; it does not add
a saved assessment schema or select a different method for existing inputs.

Supply all three `refined_panel_options` and explicit `outer_documents`.
The registered check uses 32 to 48 subdivisions and 256 to 512 ground modes,
with dielectric edge size, far size and grade multiplied by 0.5. Outer inputs
use widths 16 and 32 mm and 1024 and 2048 ground modes respectively. They
retain the joint volume and current resolution. The conductor geometry,
physical plane positions, materials, frequencies, length and ports cannot
change. All input and solve-budget checks precede any field solve. The
shared limits remain 512 physical panels and 1024 density unknowns.

With two outer documents the six evaluations are base, volume-only,
current-only, joint, and the two explicit outer inputs. The two single-axis
results are compared with base; joint is compared with each single-axis
result; each outer result is compared with joint. Each selected entry of R,
internal L, external L, C, G and vacuum C0 uses the supplied absolute allowance
plus the relative allowance times the larger magnitude. No denominator floor
hides small mutual entries. Finite agreement is not absolute accuracy or
proof of asymptotic convergence.

Exact input JSON, actual dielectric-mesh and current-method records, and
completed comparisons are retained. Typed current, mesh, dielectric or network
exceptions stop later work and preserve previous results. Completed disagreement
remains unaccepted. Keyboard interrupts propagate.

Current and mesh reuse is scoped to this operation. Six budgeted line
evaluations use four distinct current fields when base/volume and panel/joint
share their exact geometry and controls. Physical and material admission still
runs for every evaluation; reuse does not approximate geometry or persist
across requests.

Validation covers one registered heterogeneous three-tapered-trace geometry
at 1, 3 and 10 GHz with 1% relative and zero absolute allowance for all six
quantities, independently reconstructed entrywise differences, failure
retention and admission before fields. It does not qualify fixed guards,
other geometries, measured accuracy, browser execution or another platform.

[한국어](../../locales/ko/pages/packages/sipi/two_ground_harmonic_three_active_corner_face_resolution.md)
