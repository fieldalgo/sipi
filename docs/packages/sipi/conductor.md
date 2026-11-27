# High-frequency conductor surface loss

**English** | [한국어](https://github.com/fieldalgo/sipi/blob/main/docs/locales/ko/pages/packages/sipi/conductor.md)

[Cross-sections](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/overview.md) · [Uniform-line networks](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/network.md)

`sipi.conductor.surface_conductor_loss` extracts conductor R and high-frequency
internal L from the signal **and reference** surfaces of a finite-thickness
cross-section. This is a leading-order surface-impedance perturbation of the
perfect-conductor field. It does not solve current diffusion inside the metal.
Existing `CrossSection.analyze()` continues to return external L and dielectric
C/G; it does not silently add conductor loss.

```python
import numpy as np
from sipi import coupled_microstrip
from sipi.conductor import surface_conductor_loss

section = coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=1e-3,
                            thickness=50e-6, eps_r=4)
mesh = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)
f = np.array([1e9, 4e9, 10e9])
loss = surface_conductor_loss(section, f, conductivity=58e6,
                             ground_thickness=35e-6, **mesh)
dielectric = section.analyze(**mesh)
network = loss.network(C=dielectric.C, G=np.zeros((2, 2)), length=.03)
loss.R, loss.L_internal, loss.skin_depth, loss.factors.current_error
```

The example uses a smooth metal and lossless, frequency-independent dielectrics.
All values are SI. A runnable example is
[`conductor_loss.py`](https://github.com/fieldalgo/sipi/blob/main/examples/sipi/conductor_loss.py).

## Contract and validity

- Frequency is a nonempty, strictly increasing one-dimensional Hz array with
  **f > 0**. Conductivity (S/m), relative permeability and reference-plane
  `ground_thickness` (m) must be positive finite real numbers, not booleans.
  There is no implicit copper choice or reference-plane thickness.
- All signal and reference conductors share the specified metal. The exterior
  is nonmagnetic. `relative_permeability` applies to the metal surface model.
- Every trace must have positive thickness. The largest skin depth must be at
  most one fifth of **each** trace thickness, bottom/top face width, reference
  thickness and box width. Also require `sigma/(omega*eps0) >= 1000`.
  These necessary conditions do not bound corner curvature, proximity,
  perturbation, truncation or discretization errors. Sharp corners still need
  refinement, even when the thickness/skin-depth check passes.
- `roughness_rms` defaults to zero. When positive, Hammerstad's empirical
  factor `1 + (2/pi)*atan(1.4*(Rq/delta)**2)` multiplies **R only**. Smooth-metal
  reactance is retained. This is not a causal broadband roughness model, a
  measured surface fit, or a correction to the geometry. Alternatively,
  [causal Huray roughness](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/roughness.md) changes both R and internal L using
  explicit sphere radii/area ratios; choose `roughness=CausalHuray(...)`.
  [Groiss RMS](groiss.md) instead multiplies the full impedance by a real,
  noncausal frequency-domain factor. [Cannonball Huray](cannonball.md) maps
  explicit ten-point Rz to the causal sphere law. Gradient roughness is not
  supported by this surface adapter.
  A separate [Gaussian conductivity-profile kernel](conductivity_profile.md)
  returns a 1D exterior-port impedance with an explicit reference plane;
  it is not a multiplier or a line-inductance correction for this adapter.
- Invalid material/skin inputs are rejected before meshing. A discrepancy of
  more than 0.05 in the integrated unit-current matrix raises `ValueError`
  requesting refinement. This flux check is **not a 5% resistance guarantee**.
  Check R itself under refinement and separately enlarge the outer box.

`ConductorLoss` contains copied, read-only frequency, `skin_depth` (m),
`roughness_factor` (real resistance ratio), `R` (ohm/m) and `L_internal` (H/m). R and L are `(F,N,N)`;
off-diagonal terms are retained. `.factors` exposes C0, the `(N+1,N,N)`
surface integrals and `(N+1,N)` integrated currents: one surface group per
signal in `.names` order, followed by **all reference conductors together**.
User-created result objects validate shape and finiteness; they are not proof
that a solve was performed or that the physical model applies.

`.network(C=..., G=..., length=..., z_ref=50)` uses this R and
`L_external + L_internal` with the existing RLGC network solver. The caller
must supply C/G for the **same geometry, conductor order and frequencies**.
Shapes alone cannot establish that match. This API does not import measurements,
alter geometry JSON, add a browser screen or package an executable.

## Method

The smooth half-space impedance, with exp(+j omega t), is

```text
delta = 1 / sqrt(pi f mu sigma)
Zs = (1+j) sqrt(pi f mu / sigma)
```

Solve a vacuum electrostatic potential basis V and its energy capacitance C0.
For the unit longitudinal signal-current vector i, magnetic/electric duality
gives the surface current `K = eps0 d_n(V) inv(C0) i`, where n points out of
the dielectric into the metal. Tangential magnetic field follows the same
vacuum geometry, not a dielectric-weighted field. Integrate **every** signal
and return boundary:

```text
A_ij = integral K_i K_j ds
R(f) = Re(Zs(f)) A
L_internal(f) = Im(Zs(f)) A / (2 pi f)
L_external = mu0 eps0 inv(C0)
```

The Gram form preserves reciprocal positive-semidefinite loss, and includes
the leading-order perfect-conductor return/proximity distribution. It does
not resolve the redistribution caused by finite conductivity. P1 element
gradients are evaluated on dielectric boundary edges; internal zero-thickness
strips are rejected. The lower-level `surface_current_factors(mesh, signals,
ground)` allows custom dielectric-only meshes such as an annulus. It reports
the flux discrepancy without enforcing the cross-section adapter's 5% gate.
An open electric boundary is insulated in this dual problem, not infinity.

## Validation and limits

`tests/sipi/test_conductor.py`, Linux, Python 3.12.14, NumPy 2.5.4,
SciPy 1.18.1, 2026-10-30. Criteria were set before the tests.

| Check | Criterion | Result |
|---|---|---|
| Parallel plate, width 2 mm, height 1 mm | Each surface factor 1/width and integrated currents ±1, 1e-10 | Passed; total factor 1000 /m |
| Coax a=.5 mm, b=2 mm; radial cells 64/128/256, angular 256 | Total factor approaches `(1/a+1/b)/(2pi)`, finest error <1% | 3.3833%, 1.7224%, 0.8681% |
| Coupled microstrip above, all three mesh settings halved | R matrix max change / max fine R <6% (5% until 2026-11-26); flux <5% | 4.08% (macOS 5.01%); fine flux 2.22% |
| Coarser coupled mesh 10 µm/.4 mm/.2 | Reject flux >5% | 5.83%, rejected |
| Smooth Rs and skin depth vs scikit-rf 2.2.0 | Relative difference <1e-12 | 2.00e-15 and 2.22e-15 |
| R/L reciprocity, PSD and resulting S reciprocity/passivity | 1e-10 | Passed |

The scikit-rf check is an independent **half-space law** comparison, not a
whole-PCB field-solver or roughness comparison. It runs only in tests using
the already inventoried BSD-3-Clause dependency; no runtime dependency or
third-party binary is added. The plate/coax references independently check the
geometry integrals. The finite-thickness PCB check records the mesh change
for that case, not measured loss accuracy or a universal error bound.

The focused installed-wheel run at `8694e70` (2026-11-13) retained the original
5% resistance-change gate. Linux and Windows passed all seven conductor/reference
cases; macOS ARM64 passed four and failed the three related PCB refinement
checks. The common smooth-metal geometry gave a 4.07962% change on Linux/Windows
and 5.01444% on macOS. Their respective coarse/fine meshes had 19610/75158 and
19582/75157 nodes. Replaying the actual macOS meshes on Linux reproduced every
recorded P1 array within 7.47e-13 maximum-entry-normalized difference and reproduced the
failed resistance change. This isolates this failure to different generated
meshes, rather than different solutions on the same mesh; it does not identify
which meshing operation first diverged. On 2026-11-26 the three tests' mesh-change
bound became 6% (approved): with P1's observed order of about 0.12 the change is
not an accuracy measure, and a valid alternative triangulation moves it by about
one percentage point. The flux bound stays 5%.

Further Linux observations on the same geometry illustrate why a small mesh
change is not an absolute loss-error estimate. A third P1 mesh (1.25 µm edge,
50 µm far size, grade .025; 296525 nodes) changed the total current factor by
3.95719% from the previous fine mesh. Its first diagonal was 1519.646 /m.
The separate panel path at 64/128/256 panels per edge gave 1747.183, 1745.546
and 1744.857 /m with degree 14 and 512 ground modes. Degree 16 at the last two
resolutions retained those values to the displayed precision. These are
discretization observations, not a measured reference, a certified error bound,
or replacement acceptance criteria. In particular, the P1/panel difference
remains much larger than the successive P1 mesh change.

A four-level study on 2026-11-22 (each of edge, far and grade halved; Linux,
the same geometry) measured how slowly this P1 factor converges. The first
diagonal was 1404.945, 1464.699, 1519.646 and 1570.054 /m with 19610,
75158, 296525 and 1182640 nodes (the last run outside the 300000-point
product mesher limit). Successive differences 59.75, 54.95 and 50.41 /m give
an observed order of about 0.12. The panel path gave 1744.857 /m, and the
vacuum C0 of the two paths agreed to 5.6e-5. On the same meshes, an
independent scikit-fem P2 reference gave 1546.896, 1559.606 and
1597.804 /m. The P1 factor was therefore 19.5% and 16.1% below the panel
value on the two meshes of the refinement test and still 10.0% below it at
1.18 million nodes, while the test's mesh change was about 4%.

For this rectangular section, the 6% (formerly 5%) mesh-change check therefore does not
bound the loss error, and the P1 resistance may be 10 to 20% low on
ordinary meshes. Prefer the [boundary-panel path](panel_conductor.md) where
its geometry applies, and treat P1 results with this limitation.
[Transmission-line/8](default_line.md) uses panel currents by default for
`surface` and `surface-boundaries` conductors. These are
observations for one geometry, not a general error bound or a measured
reference; other sections are being compared separately. The original
tests, meshes and limits are unchanged.

This common-metal adapter does not model DC/low-frequency transition or
interior skin/proximity diffusion. Those belong to the separate
[finite-metal diffusion model](conductor_diffusion.md). Distinct metals and
roughness use the separate [signal-boundary](boundary_conductor.md),
[signal-face](face_conductor.md), [reference-surface](reference_surfaces.md)
and [ground-face](ground_faces.md) assignments; they retain the surface
perturbation assumptions. Finite-conductivity reference-current redistribution,
measured-coupon calibration and full-wave radiation remain outside this model.
Do not extrapolate this model to DC or substitute it for an AC PDN solver.

References: E. Hammerstad and Ø. Jensen, “Accurate models for microstrip
computer-aided design,” IEEE MTT-S Digest, 1980 (empirical roughness factor);
standard good-conductor surface impedance and quasi-TEM electric/magnetic
duality, checked here by the stated plate and coax limits.

Run the related validation with the test extra installed:

```sh
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q tests/sipi/test_conductor.py
```

[Shared-mesh frequency-line input](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/line_model.md) combines this extraction with
the other material/conductor components and saves the complete input as JSON.

[Explicit boundary-panel currents and per-boundary loss](panel_conductor.md) provide an optional shared-kernel path with fixed grounded traces and separate panel/domain convergence checks.

## Independent quadratic field comparison

`test_crosscheck_conductor_p2.py` solves the same vacuum geometry and conductor
potentials with scikit-fem 12.0.2 quadratic triangles. It computes its own energy
capacitance matrix and integrates boundary-normal derivatives with fourth-order
facet quadrature. Plane and circular-coax analytical limits check the reference
calculation. PCB comparisons retain each boundary matrix, mutual entry and
current integral for both coarse and fine meshes. They are report-only: a small
change between two quadratic meshes is not an accuracy certificate, and does
not replace the existing P1 flux, resistance or exterior-boundary checks. The
quadratic tool is a test dependency, not a selectable production solver.

[Fixed-radius surface-model fitting](roughness_fit.md) accepts explicit complex surface-impedance samples and retains incompatible data.

[Planar layered-metal impedance](layered_metal.md) resolves explicit thin metal coatings on a bulk half-space, independently of the finite-geometry surface adapter.

[Explicit dual-cell currents](dual_cell_conductor.md) use weak P1 boundary reactions with independent field comparisons. Algebraic conservation is separate from resistance accuracy; saved-line defaults remain unchanged.

[Explicit capacitance-shape currents](panel_shape_conductor.md) provide a
separate integrated-current estimate with retained finite-difference samples.
Step agreement is distinct from panel and outer-domain convergence.

## Auxiliary recovered currents (volume shape derivative)

`sipi.recovered_conductor.recovered_surface_current_factors(mesh, signals,
ground, *, support_fraction=0.4)` is an **auxiliary** current method. It takes
the same dielectric-only P1 mesh and conductor node sets as
`surface_current_factors`, solves the same vacuum basis and returns the same
C0; only the surface integrals differ. `surface_current_factors`, the
`volume-p1` method, the panel default and every saved document and result are
unchanged. Saved lines select it by name as `current_method:
"volume-p1-recovered"` in `sipi.method-transmission-line/2` or
`sipi.transmission-line/9` ([method lines](method_line.md#version-2-recovered-currents));
the default stays panel.

The boundary integral of a product of normal derivatives is replaced by its
domain (Hadamard) form, which is Wheeler's incremental-inductance rule: each
conductor wall moves by a unit normal displacement theta. With n pointing into
the dielectric and theta.n = 1 on the group's edges,

```text
integral_Gamma dn(Va) dn(Vb) ds = integral grad(Va) . ((div theta) I - D theta - D theta^T) grad(Vb) dx
```

for harmonic Va, Vb that are constant on Gamma, with theta zero on every other
conductor and tangent to insulated walls. P1 element gradients are constant,
so the volume integral is exact per element. For each surface group (each
signal, then all references together):

1. Each boundary vertex gets a miter m with m.n1 = m.n2 = 1 for its two edge
   normals (m = n1 when they are parallel within 1e-9, and m = n at an end on
   an insulated wall). Normals turning by more than 20 degrees make a corner.
2. Near each corner c, with radius `rc = min(w, half the shorter adjacent
   side)`, non-corner vertices blend towards the corner miter:
   `m_v + psi(|v-c|/rc) (m_c - m_v)` summed over the side's two end corners.
   This keeps theta.n = 1 exactly on every edge.
3. Each mesh node takes the boundary value at its nearest edge point, linearly
   interpolated, times `psi(d/w)`, where `psi(s) = (1-s)^2 (1+2s)` for
   0 <= s <= 1 and 0 beyond, and `w = support_fraction` times the minimum node
   distance between separate connected conductor boundaries.

The nearest edge is searched among the 12 nearest edge midpoints; when those
cannot prove it, every edge close enough to be nearer is checked. Integrated
currents weight the consistent P1 flux by the same cutoff; this equals the
unit-current target to rounding, so `current_error` is **not** an
under-resolution signal here. `diagnostics['gradient_current_error']` reports
the boundary-gradient flux discrepancy of the same basis, the quantity the 5%
gate of the existing adapter checks. Other diagnostics are `support_fraction`,
`support_width` and `clearance` (m), and `support_triangles` and `corners` per
surface group.

Refused with `ValueError` instead of returning a result: `support_fraction`
outside (0, 0.5); corners other than convex right angles (trapezoid, acute and
re-entrant corners have not been characterised); a support that reaches
another conductor; and a support that meets an insulated (open) wall with a
normal displacement component. Very narrow spacings, macOS and Windows have
not been characterised.

### Validation

Linux x86_64, Python 3.13.18, NumPy 2.5.5, SciPy 1.18.1, galerkin and meshine
at the pinned development commit, `OPENBLAS_NUM_THREADS=1`, 2026-11-26.
Criteria were fixed before the runs. The panel values are the recorded panel
path at 256 panels per edge (128 for the grounded coplanar section). Levels
L0, L1 and L2 use edge 5 µm, far .2 mm and grade .1, each times 2^-L.

| Section | Default mesh | vs panel | L0 | L1 | Extra cost / P1 solve |
|---|---|---|---|---|---|
| Coupled microstrip 0.5/0.3/1 mm, 50 µm | 1740.372 /m | -0.257% | -0.257% | -0.119% | 0.37 |
| Microstrip 0.3/0.2 mm, 35 µm | 2954.613 /m | -0.235% | -0.391% | -0.148% | 0.59 |
| Microstrip 1/0.5 mm, 17.5 µm | 1176.333 /m | -0.300% | -0.476% | -0.240% | 0.56 |
| Grounded coplanar 0.3/0.2/1 mm, 35 µm | 3091.705 /m | -0.293% | -0.441% | -0.206% | 0.85 |
| Stripline 0.2/0.5 mm, 17.5 µm | 4106.478 /m | -0.340% | -0.710% | -0.296% | 0.68 |

The existing boundary-gradient P1 factor on the same default meshes was 12% to
20% below the panel value (for example 1400.776 /m for the coupled section).
Coupled L2 gave 1743.728 /m (-0.065%), an observed order of 1.34. The coupled
off-diagonal 10.802 /m differs from the panel 10.415 /m by 0.022% of the
diagonal. Every total is symmetric positive definite. These default-mesh
totals and C0 reproduce an internal study bit for bit in this environment.
The test compares them to a relative 1e-12 on the recorded mesh. When the
mesher produces a different triangulation it compares the diagonal totals to
a relative 2e-3, below the recorded panel differences, and records which
comparison ran. Cost ratios are medians of five runs and vary with the
machine. The test records the ratio and fails only above 4, a regression
bound for shared runners; the at-most-1 criterion is the measurement above.

| Check | Criterion | Result |
|---|---|---|
| Parallel plate, width 2 mm, height 1 mm | Each surface factor 1/width and currents ±1, 1e-10; C0 identical to `surface_current_factors` | Passed |
| Coax a=.5 mm, b=2 mm, cells 16x64, 32x128, 64x256 | Observed order >= 1.8 on each surface; finest relative error < 1e-3 | Order 2.0; total -0.345%, -0.087%, -0.022% |
| Five sections vs panel [0,0] | Default and L0 within 2%; L1 within 1% | Above table |
| Coupled refinement | Order >= 0.8, or L1-L2 within 0.5% | 1.34 |
| Coupled off-diagonal | Within 1% of the largest diagonal | 0.022% |
| Totals | Symmetric positive semidefinite | Passed |
| Cost | Recovery beyond the P1 solve at most the solve time (measured; test bound 4) | 0.37 to 0.85 |
| Refusals | Fractions 0, .5, negative, boolean, NaN, string; 22.5 degree polygon; trapezoid trace; support meeting an open wall | Refused |

These are observations for these sections and meshes, not a general error
bound or a measured reference. Run
`python -m pytest -q tests/sipi/test_recovered_conductor.py tests/sipi/test_recovered_conductor_sections.py`.
