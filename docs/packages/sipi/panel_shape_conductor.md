# Integrated currents from capacitance shape derivatives

`panel_shape_current_factors` is an explicit alternative for convex, finite
conductors over a grounded bottom, with insulated side/top walls in the vacuum
electric dual. It calls the existing shared boundary solver. It does not change
the gradient, dual-cell or panel-current defaults or any saved-line schema.

Shrinking one trace by a unit inward normal displacement gives
`Q_b = -d(C/epsilon)/dh`. Moving the bottom ground outward gives its separate
matrix. The original capacitance matrix converts voltage bases to unit signal
currents; explicit grounded traces remain at zero potential. Their matrices and
the bottom-plane matrix are grouped into the reference contribution. Dielectric
material metadata does not enter this vacuum solve.

Two central-difference steps, `h` and `h/2`, are evaluated at fixed panel settings.
`h = step_fraction * shortest_trace_edge`, with default `step_fraction=1e-3`
and allowed range `1e-5`–`1e-2`. Each polygon corner moves along the intersection
of its two inward-offset edges. Every grouped and individual boundary entry,
and every entry of their sum, must agree between steps to `1e-4` relative to the
larger magnitude. There is no denominator floor for small mutual entries; two
exact zeros agree. Reciprocity, positive semidefiniteness and algebraic current
conservation are checked separately. The returned `parts` uses the smaller step.

This is a finite-difference stability check, **not a panel/domain convergence
or absolute resistance-error certificate**. Refine `panels_per_edge`, ground
Fourier resolution and the outer domain independently. Squaring a discretized
panel current and differentiating its discretized capacitance need not give the
same finite-resolution value. Preserve both observations when comparing them.
The existing shared admission limits and internal quadrature gates remain in
force; unsupported or unresolved requests raise without fallback.

There are `1 + 4 * (number_of_traces + 1)` shared solves. Controls have the same
limits as the shared solver: 1–256 panels per edge, at most 2048 total panels,
64–4096 ground modes and interpolation degree 10, 12, 14 or 16. Degree defaults
to 16 for this explicit API. More panels can make the multiple dense solves
expensive. Nothing automatically increases a requested control.

The immutable result retains `step_m`, both grouped `step_parts`, individual
`boundary_step_parts`, and all `samples`. Each sample contains an exact request,
capacitance per permittivity and solver diagnostics. `request.arguments()` makes
an independent JSON-compatible copy. `PanelShapeCurrentError` retains completed
samples, a failed field request if applicable, and both step matrices when a
step/positivity check fails. User interrupts propagate.

```python
from sipi import CrossSection, Layer, Trace
from sipi.panel_shape_conductor import panel_shape_current_factors

section = CrossSection([Layer('uniform', .01105, 4.)],
    [Trace('signal', 0., .0008, .0008, thickness=35e-6)], .02)
factors = panel_shape_current_factors(section,
    panels_per_edge=32, ground_modes=1024)
assert factors.names == ('signal',)
assert len(factors.samples) == 9
assert factors.diagnostics['step_relative_change'] <= 1e-4
assert factors.current_error <= 1e-10
```

`panel_shape_conductor_loss_by_boundary` applies the existing independent metal,
coating and roughness laws to these integrated factors. Its skin-depth and
surface-perturbation restrictions remain unchanged; it is not a volume
eddy-current solver. All reference surfaces share one material. Face-specific
metals and arbitrary local boundary impedance need a separate contract.

Validation includes rectangular single/equal/unequal/close thin pairs against
separately refined capacitance derivatives, an independent circular conductor
above a plane image solution, polygon-normal identities, scale/order/grounded
potential checks and preserved failure inputs. Finite outer boxes in the image
check require their own refinement; the smaller-box observation failed before
the larger-domain check passed. This evidence does not establish arbitrary
polygon, measured foil, native-platform or whole-product accuracy.

[한국어](../../locales/ko/pages/packages/sipi/panel_shape_conductor.md)

For versioned input and common execution, use the explicit
[saved shape-current line](shape_panel_line.md) wrapper.
