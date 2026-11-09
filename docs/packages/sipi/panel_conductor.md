# Explicit boundary-panel conductor loss

This explicit path uses the shared `galerkin.laplace_boundary` kernel for
vacuum perfect-conductor currents. It does not change the existing finite-element
surface-current APIs or select a new method in saved line documents.

Use wheels built from the exact commit in `dependencies.json`. Development
wheels may share a version while exposing different APIs. Loading SIPI remains
possible without this capability; calling the panel API requires a shared wheel
with explicit `interpolation_degree` support and otherwise raises an error.
There is no automatic fallback to another solver.

## Geometry and current contract

`panel_surface_current_factors(section, panels_per_edge=32, ground_modes=512,
interpolation_degree=10)` takes a `CrossSection` in metres. It requires bottom
ground, open top and sides, and positive-thickness, strictly convex conductor
polygons. The shared finite rectangular Green function applies zero electric
potential at the bottom and zero normal derivative on the other outer walls.
"Open" here therefore still needs an outer-domain convergence study.

Each explicit ground trace stays at zero potential. It is not floating. Its
surface-current energy is combined with the bottom into one reference part.
For the full conductor capacitance matrix A and signal indices S, let
B = A[S,S] and T = A[:,S] inverse(B). The current factors are Tᵀ Q_b T,
with ground pieces summed after this transformation. C0 = epsilon_0 B.
Signal boundary integrals are the identity and the combined reference integrates
to minus one for every signal basis. Ground voltage and current residuals must
be at most 1e-10.

The result extends `SurfaceCurrentFactors`, retaining `C0`, `parts`,
`current_integrals`, `L_external`, and `current_error`. It also records explicit
ground-trace names and the shared solve diagnostics. Arrays and diagnostics are
read-only. Layer permittivity and dielectric regions do not enter this vacuum
current calculation. They still matter for a separate, matching-geometry C/G
calculation.

The shared kernel limits conductor count to 16 and total panel count to 2048,
requires width/height in [0.25, 4], and requires side/top clearance from the
conductor cluster of at least its largest extent. Polygons cannot touch, overlap,
nest or touch a wall. `panels_per_edge` is an integer in [1, 256];
`interpolation_degree` is 10, 12, 14 or 16. An insufficient quadrature/interpolation
or ground-series refinement is an error, not an automatic change in parameters.
Increasing an explicit interpolation degree does not replace panel or domain
convergence. Cubic endpoint grading at 1 and 2 panels is uniform; those first
coarse differences alone do not establish asymptotic convergence.

## Metal loss and networks

`panel_conductor_loss_by_boundary` accepts one `SurfaceMetal` for every signal
and one common reference metal, with explicit `ground_thickness`. It checks the
existing positive-frequency, good-conductor and skin-depth requirements before
the field solve. Each skin depth must be at most its conductor's minimum
dimension divided by five. The reference uses the ground thickness and every
explicit ground trace. The existing polygon minimum dimension includes its
shortest edge: a finely faceted polygon can therefore be rejected even when its
overall diameter is large. No restriction is weakened for this path.

R = sum_b Re(Zs_b) Q_b and internal L = sum_b Im(Zs_b) Q_b / omega.
Existing smooth, Hammerstad, Groiss, causal Huray and cannonball Huray laws retain
their original validity limits; this path adds no material or roughness model.
All reference surfaces must share a metal. Different ground-trace metals and
independent foil-face assignment are unsupported.

The returned `BoundaryConductorLoss.network(C=..., G=..., length=...)` combines
these losses with external L = mu_0 epsilon_0 inverse(C0) from the same panel
current solve. Supply C and G from the same geometry, conductor ordering and
outer boundary conditions. Do not substitute an unrelated finite-element L.
This is a first-order surface-impedance perturbation, not an interior conductor
diffusion, DC, radiation or via model.

## Validation scope

The candidate checks fixed grounded-trace voltages, conserved currents, positive
energy, scaling and conductor permutation; it compares a qualified 2/4/8 panel
sequence with a separate direct-voltage collocation solution. A separate
scikit-fem P2 comparison is reported as a difference between discretizations;
its current-energy differences were not monotonic and are not an accuracy claim.
The original coarse 1/2/4 sequence failed monotonicity and remains a failed study.

Metal assembly checks use the independent smooth half-space law, frequency
scaling and passive reciprocal networks. A fixed two-line geometry is replayed
at three panel resolutions and three outer domains with original dielectric
matrices, target and convergence gates. Passing these fixtures does not certify
arbitrary layouts, material data or a complete inverse-design search.

## Minimal example

```python
from sipi import CrossSection, Layer, Trace
from sipi.boundary_conductor import SurfaceMetal
from sipi.panel_conductor import panel_conductor_loss_by_boundary

section = CrossSection(
    [Layer("uniform", .002, 4.2)],
    [Trace("left", -.0003, .0005, .0002, thickness=35e-6),
     Trace("right", .0003, .0005, .0002, thickness=35e-6)],
    .004,
)
copper = SurfaceMetal(58e6)
loss = panel_conductor_loss_by_boundary(
    section, [1e9, 2e9], conductors={"left": copper, "right": copper},
    reference=copper, ground_thickness=35e-6, panels_per_edge=16,
)
assert loss.R.shape == (2, 2, 2)
assert loss.factors.current_error <= 1e-10
```

[Saved panel lines](panel_line.md) retain explicit current controls and combine them with matching dielectric extraction.
