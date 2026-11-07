# Buried coplanar lines at a dielectric interface

[한국어](../../locales/ko/pages/packages/sipi/layered_coplanar_stripline.md)

`layered_coplanar_stripline` and `coupled_layered_coplanar_stripline` extend the
[buried coplanar sections](coplanar_stripline.md) to two independent dielectric
layers. A single signal or an equal-width horizontal pair shares its height and
thickness with two finite rectangular side grounds. Both outer planes and both
side grounds have the same reference potential. No ground is inserted between
the two signals. The section is longitudinally uniform and quasi-static.

```python
from sipi import coupled_layered_coplanar_stripline, CrossSectionDocument

parameters = dict(width=.3e-3, gap=.3e-3, ground_gap=.3e-3, ground_width=.8e-3,
    lower_height=.4e-3, upper_height=.6e-3, lower_eps_r=3., upper_eps_r=5.,
    thickness=35e-6, lower_tan_delta=.01, upper_tan_delta=.03, box_width=6e-3)
mesh = dict(edge_size=5e-6, far_size=.125e-3, grade=.15)
section = coupled_layered_coplanar_stripline(**parameters)
document = CrossSectionDocument(section, mesh=mesh)
assert CrossSectionDocument.loads(document.dumps()).dumps() == document.dumps()
assert document.analyze().z_diff_forward > 0
```

All lengths are metres. `lower_height` is the bottom-plane to dielectric-interface
distance. Every trace's **bottom face** is at this interface. `upper_height` runs
from the interface to the top plane and **includes copper**. Total plane spacing
is `lower_height+upper_height`; clearance above the metal is
`upper_height-thickness`, which must be positive. The layer names are `lower`
and `upper`, with their own `eps_r >= 1` and nonnegative `tan_delta`.
Finite-thickness fields do not average these coefficients.

`width`, `gap`, pair-only `ground_gap`, `ground_width`, optional signal
`top_width`, and `box_width` retain the [homogeneous template contract](coplanar_stripline.md).
The signal can taper; side grounds remain rectangular. Positive gaps are measured
between bottom edges; widened top faces must still avoid overlap. Zero thickness
is allowed for electrostatics, subject to the existing zero-thickness taper rule;
surface loss still requires finite thickness and its skin-depth/flux gates.

With B=`lower_height+upper_height`, omitted box width is
`max(12*B, 4*width, width+2*gap+2*ground_width+4*B)` for a single signal, and
`max(12*B, 4*(2*width+gap), 2*width+gap+2*ground_gap+2*ground_width+4*B)`
for a pair. Insulated side walls approximate a distant outer boundary. Hold
physical ground widths/gaps fixed while increasing box width to check it.

## Saved geometry, stack tolerances and goals

Geometry JSON, study/1–4 and design/1–3 reuse these template names. Record the
engine revision: older readers reject unsupported names. Single-signal quantities
use `z0`; the pair accepts `z_diff` and `z_diff_forward`. These are the existing
real quasi-static diagnostics, not a complex lossy impedance target.

`fixed_plane_spacing_m` requires exactly one sampled layer height. The other is
derived as the total minus that sample, retaining upper-height-includes-copper
semantics. Pair `fixed_pitch_m` requires width sampling and derives `gap=pitch-width`.
Both constraints may be applied together; side grounds move to preserve
`ground_gap`. Nominal dimensions must satisfy both constraints. All finite-bound
corners are checked before solving, while invalid unbounded normal samples are
retained as failed rows without resampling.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import execute_saved, normalize_saved

study = ImpedanceStudyDocument("coupled_layered_coplanar_stripline", parameters,
    quantity="z_diff", mesh=mesh, fixed_pitch_m=.6e-3, fixed_plane_spacing_m=1e-3,
    sampling=dict(kind="normal", count=2, seed=19, correlation=[[1., .6], [.6, 1.]],
        variables=[dict(name="lower_height", mean=.4e-3, std=.02e-3),
                   dict(name="width", mean=.3e-3, std=.01e-3)]))
assert normalize_saved(study.dumps()) == study.dumps()
report = execute_saved(study.dumps(), max_evaluations=2)
assert len(report["result"]["rows"]) == 2
```

Fixed-frequency scalar or principal-axis material overrides and sampled material
leaves address `lower` and `upper` independently. Existing [iid yield assessment](yield.md)
uses the same saved studies and keeps unresolved rows. Small example samples
do not establish manufacturing yield or measured dielectric accuracy.

```python
from sipi import ImpedanceDesignDocument

goal = ImpedanceDesignDocument("coupled_layered_coplanar_stripline",
    dict(parameters, gap=.5e-3), variable="width", bounds=[.15e-3, .65e-3],
    target=100., quantity="z_diff", fixed_pitch_m=.8e-3,
    tolerance=.5, max_evaluations=24, mesh=mesh)
assert normalize_saved(goal.dumps()) == goal.dumps()
result = goal.solve()
assert abs(result.residual) <= .5 and abs(result.refined_residual) <= .5
```

The bounded one-variable search must pass the requested and refined meshes.
This is not a continuous multivariable optimizer or a measured production goal.

## Independent checks and scope

`tests/sipi/test_layered_coplanar_stripline.py` checks independent scikit-fem
piecewise complex/vacuum P1 assembly at 1e-10 normalized C/C_loss/C0 error.
Identical-mesh scaling of all permittivities uses 1e-12. Equal-material reduction
to homogeneous templates and zero-thickness vertical reflection use 0.5%.
Reflection swaps lower/upper heights and materials: **finite copper is not
invariant under this swap**, because it extends into the upper layer.
Representative C/Z changes are limited to 1.5% under refinement and 0.5% under
box doubling. Reciprocity and positive-definite matrices are also checked.

For zero-thickness coplanar sheets at a flat interface with remote planes and
ground ends, the analytic half-space limit has
`eps_eff=(lower_eps_r+upper_eps_r)/2` and
`eps_loss_eff=(lower_eps_r*lower_tan_delta+upper_eps_r*upper_tan_delta)/2`.
The [CPW elliptic-integral formula](coplanar_stripline.md) gives C and Z with
`eps_eff`, and C_loss with `eps_loss_eff`. The test requires each observable within
2% and each error to decrease with mesh refinement. This limit is used only as
an independent check, never to replace the two-material field calculation.

No stitching-via connection, pad transition, floating reference, radiation or
three-dimensional return-path model is added. Default geometry/mesh sizes do not
certify convergence for arbitrary dimensions or dielectric contrast. See
[manufacturing sections](manufacturing_sections.md), [studies](study.md),
and [impedance design](design.md).
