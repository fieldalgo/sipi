# Two-ground paired impedance goal

[한국어](../../locales/ko/pages/packages/sipi/two_ground_pair_goal.md)

`seek_two_ground_forward_pair_impedances` in `sipi.two_ground_pair_goal` uses the
existing bounded two-parameter forward-impedance search with an explicit
[two-ground saved line](two_ground_panel_line.md). It requires the explicit shared
capability from `dependencies.json`; existing extraction defaults are unchanged.
This callable API does not serialize a factory. A separate
[saved goal document](two_ground_pair_goal_document.md) stores template inputs.

The factory receives two positive parameters inside finite increasing bounds
and returns a TwoGroundPanelTransmissionLineDocument. The line must have exactly
two ordered signals, one positive frequency and zero length. Frequency, signal
names and panel settings stay fixed throughout the search. Full complex
conductor-coordinate characteristic matrices are transformed to the power-dual
mixed basis; the targets are Re(Zdd) and Re(Zcc) for separate Ic=0 and Id=0
launches. This retains asymmetric coupling rather than assuming modal symmetry.

All uncached factory, field and diagnostic attempts count, including failed
attempts and optimizer probes. max_evaluations remains in [4,10000]. Three
attempts are reserved for checking the frozen selected input; the factory is
not called again for refinement. Before any search field solve, all three
refined inputs must pass input validation and resource admission:

- Volume refinement halves resolved edge_size, far_size and grade.
- Panel refinement doubles panels_per_edge.
- Joint refinement performs both changes.

Ground modes, interpolation degree, material parameters, boundary conditions and
all other settings remain unchanged. A panel count above128 cannot be doubled
within the existing maximum256; total-panel admission also remains mandatory.
Each refined result must satisfy both original absolute target tolerances.
The original relative limit0.005 applies to each refined value against nominal,
and to joint versus each single-axis refinement. No averaging or fallback
replaces a failed refinement. These checks do not establish finite outer-domain
adequacy, uniqueness, continuity, a global optimum or measured accuracy.

The returned TwoGroundForwardPairDesign retains selected parameters, targets,
values, full search history, selected input and three actual refinement results.
Its serialized observation includes the complete current records and dielectric
mesh identities for selected and refined lines. ForwardPairGoalError retains
attempt counts, completed history, failed input, stage and original typed
TwoGroundPanelLineError cause. Interrupts propagate rather than becoming failed
goals. The attempt budget does not bound internal solves, time or memory.

Tests retain independent synthetic modal roots and parameter scaling, exact
frozen refinement inputs, admission before fields, reserved budgets, identity
drift rejection, failures at all four final stages and interruption propagation.
The registered physical study uses the original 8mm by2mm box, symmetric
50um-thick conductors centered vertically, existing local coated positive and
35MS/m negative metals, common58MS/m foils, epsilon_r4/tan_delta.003 at2GHz.
Width and gap bounds are .35–.5mm and .2–.4mm, initial .38/.28mm, targets90/44.5ohm
with .1ohm tolerances,128→256 panels and a64-attempt limit. The accompanying
record states whether this unchanged study passed. Independent matrix-square-root
forward impedances check the selected and refined extracted RLGC. A bounded
numerical pass is not general geometry or platform qualification.
