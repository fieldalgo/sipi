# Two-ground face-metal paired impedance goal

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_pair_goal.md)

`seek_two_ground_face_forward_pair_impedances` in `sipi.two_ground_face_pair_goal`
connects a [face-metal saved line](two_ground_face_panel_line.md) to the existing
bounded two-parameter forward-impedance search. Import it explicitly; the
[whole-boundary goal](two_ground_pair_goal.md), its JSON and extraction defaults
are unchanged. This callable API does not save a factory or add a saved goal
schema. Saved manufacturing studies are a separate integration.

The factory takes two positive parameters inside finite increasing bounds and
returns `TwoGroundFacePanelTransmissionLineDocument`. It must supply two ordered
signals, one positive frequency and zero length. Frequency, ordered signal names
and panel controls stay fixed across search inputs. Each metal remains attached
to its named physical face, including coatings and local roughness. Existing
skin-depth, remaining-core, geometry and resource admission still apply.

The two targets are Re(Zdd) and Re(Zcc) for separate Ic=0 and Id=0 launches, using
the power-dual mixed basis of the full complex forward characteristic matrix.
Asymmetric coupling is retained. Search history records every uncached attempt,
including failed factory/field/diagnostic evaluations and optimizer probes.

`max_evaluations` is 4..10000. Three attempts are reserved for the frozen selected
input, without calling the factory again. Before the first field calculation,
each proposed search input must admit all three future refinements:

- Volume only: halve resolved edge size, far size and grading.
- Panels only: double panels per edge.
- Joint: apply both changes.

Ground modes, interpolation degree, physical boundary conditions, face laws and
other parameters are fixed during refinement. The maximum remains 256 panels
per edge, so nominal counts above 128 cannot be refined. Every refined value
must satisfy both original absolute target tolerances. The original 0.005
relative limit applies against nominal, and between joint and each single-axis
result. Failed checks are retained; no averaging, retry or method substitution
is used. The attempt budget does not bound time, internal solves or memory.

`TwoGroundFaceForwardPairDesign` exposes the selected parameters, input, full
history, target residuals and three `TwoGroundFacePairRefinement` results. Each
document accessor restores the face schema. Observations include face-current
records, their whole-current partition and actual dielectric-mesh identities.
`ForwardPairGoalError` preserves the failed input/stage, completed history and
original typed `TwoGroundFacePanelLineError` cause. Interrupts propagate.

Independent synthetic modal roots exercise parameter scaling, frozen face laws,
all reserved attempts and original target/convergence refusal. The registered
physical example uses an 8 by 2 mm uniform box, epsilon_r 4, tan_delta 0.003,
50 micrometre conductors at mid-height and 2 GHz. First-signal bottom/top/left/right
conductivities are 58/35/21/45 MS/m, reversed on the second signal; both reference
foils use 58 MS/m. Width/gap bounds are 0.35..0.5 / 0.2..0.4 mm, initial values
0.38/0.28 mm and targets 90/44.5 ohm with 0.1 ohm tolerances. Panels are 128→256,
degree 16 and the attempt limit is 64. An independent matrix square root of ZY
checks the selected and refined forward matrices. The associated validation
record identifies the actual result and the separately tested finite-domain
and frequency sensitivity. It does not certify arbitrary geometry, infinite
outer-domain convergence, uniqueness, global optimality, measured accuracy or
new platform support. The underlying [face-current references](two_ground_face_conductor.md)
retain their own narrower geometry and material scope.

[Saved paired-goal document](two_ground_face_pair_goal_document.md)

[One-parameter face-metal goals](two_ground_face_line_goal.md)

[Face-metal goals at multiple frequencies](two_ground_face_sampled_pair_goal.md)
