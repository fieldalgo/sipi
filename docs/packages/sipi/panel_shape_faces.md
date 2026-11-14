# Straight-face shape-current energies

`panel_shape_face_current_factors` explicitly computes the integral of Ki*Kj
on each straight conductor face. It supports one to four finite rectangular
or tapered `Trace` objects, including grounded traces, over a grounded bottom
with open top/sides. Arbitrary `PolygonTrace` objects are not admitted by this
API. It reuses the [whole-boundary shape-current method](panel_shape_conductor.md)
and does not change existing defaults, saved schemas or material models.

A continuous vertex displacement has unit inward normal velocity on one
selected face and zero normal velocity on adjacent faces. The capacitance
shape derivative is transformed from unit potential to the same unit-signal-
current basis as the original whole extraction; grounded traces remain at
zero potential. This gives energy matrices, not signed face current integrals.
No face flux is inferred from energy, and no finite-conductivity interior or
coating corner is solved.

All geometry and both offset levels are preflighted before the first solve.
Existing shared panel/domain admission remains active during extraction.
With n total traces, the method retains the original 4*n+5 whole-boundary
samples and performs 16*n face solves, totaling 20*n+5 (at most 85).
`panels_per_edge`, `ground_modes`, `interpolation_degree` and `step_fraction`
retain the original limits. No hidden subdivision, fallback or automatic
method change occurs. This count does not bound each solve's memory/time.

`PanelShapeFaceCurrentFactors` has immutable `step_parts`, `samples`,
`diagnostics`, `trace_names` and `trace_ground`. `parts` selects the smaller
step. The order is each trace in geometry order, its bottom/top/left/right
faces, then the bottom plane. Sloping faces retain left/right names.
`labels` distinguishes `signal:<name>:<face>`,
`reference:ground:<name>:<face>` and `reference:bottom`. This geometry order
can interleave signal and grounded traces. Use labels when assigning material
weights. `total` sums all faces; `whole_boundary_step_parts` regroups each trace.
`names`, `C0` and `L_external` retain the original signal basis. `base` retains
all original whole-current evidence; its grouped `current_integrals` and
conservation diagnostic remain separate from the energy matrices.

Every entry of the two face steps, their total, and face-to-whole sums must
agree to 1e-4 relative with no denominator floor. Reciprocity and PSD use
1e-10; total energy must be positive definite. Nonfinite results are rejected.
There is no PSD projection or current-conservation rescaling. Original
whole-current failures retain their exception/evidence. A subsequent
`PanelShapeFaceCurrentError` retains `base`, all completed face `samples`,
the failed `request`, and complete `step_parts` when available. Interrupts
propagate.

The following prepares a tapered guarded geometry; the commented call runs
fields. Dimensions are metres and current-energy factors are inverse metres.

```python
from sipi import CrossSection, Layer, Trace, panel_shape_face_current_factors

section = CrossSection([Layer('uniform', .01105, 4.)], [
    Trace('a', -.0005, .0003, .001, 50e-6, top_width=.00022),
    Trace('guard', 0., .0002, .001, 50e-6, ground=True, top_width=.00012),
    Trace('b', .0005, .0004, .001, 60e-6, top_width=.00055),
], .02)
options = dict(panels_per_edge=32, ground_modes=4096,
               interpolation_degree=16, step_fraction=.001)
# factors = panel_shape_face_current_factors(section, **options)
# print(factors.labels, factors.parts)  # Starts actual field solves.
```

Checks cover exact normal-motion/sum identities, independent P2 volume-energy
integration on preserved rectangular-line potentials, and explicit rectangular
and tapered face observations. A separate image-solution study checks circular
quarter integrals and separates polygon, panel and finite outer refinement;
that study does not add circular-conductor support to this API. The rectangular
P2 normal-gradient integral itself was insufficiently resolved and is not used
as the accepted reference. Its original failures remain preserved.

Step agreement, selected finite outer changes and whole-boundary agreement are
not absolute or small mutual-entry error bounds. Refine panels and the outer
box independently for the intended geometry; unresolved inputs can fail.
There is no material-loss weighting, new saved input, browser integration or
cross-platform qualification in this energy-only API unit.
