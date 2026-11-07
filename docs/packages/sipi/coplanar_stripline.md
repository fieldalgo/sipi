# Buried coplanar striplines

[한국어](../../locales/ko/pages/packages/sipi/coplanar_stripline.md)

`coplanar_stripline` places one signal and two finite-width side grounds between
two grounded planes in a uniform dielectric. `coupled_coplanar_stripline` places
an equal-width horizontal signal pair between those side grounds. Both are
longitudinally uniform quasi-static sections. All reference conductors have the
same PEC potential; separate reference-current groups do not create extra ports.

```python
from sipi import coupled_coplanar_stripline, CrossSectionDocument

parameters = dict(width=.3e-3, gap=.3e-3, ground_gap=.3e-3,
    ground_width=.8e-3, plane_spacing=1e-3, trace_height=.4e-3,
    eps_r=4., thickness=35e-6, tan_delta=.02, box_width=6e-3)
mesh = dict(edge_size=5e-6, far_size=.125e-3, grade=.15)
section = coupled_coplanar_stripline(**parameters)
document = CrossSectionDocument(section, mesh=mesh)
assert CrossSectionDocument.loads(document.dumps()).dumps() == document.dumps()
line = document.analyze()
assert line.even_odd()["z_diff"] > 0
```

All lengths are metres. The geometry contract is:

| Parameter | Meaning |
|---|---|
| `plane_spacing` | Total dielectric domain height B, including metal thickness |
| `trace_height` | Explicit **bottom-face** height h for every trace; 0 < h and h + thickness < B |
| `width` | Signal bottom-face width; both signals have this width in a pair |
| `top_width` | Optional signal top-face width; side grounds remain rectangular |
| `gap` | Single: signal-to-ground bottom-edge separation; pair: signal-to-signal bottom-edge separation |
| `ground_gap` | Pair only: outer signal-to-ground bottom-edge separation |
| `ground_width` | Physical finite width of each side ground |
| `thickness` | Common nonnegative metal thickness, including the side grounds |
| `box_width` | Independent outer-domain width, with insulated side walls |

Names are `signal`, or `positive` on the left and `negative` on the right;
side grounds are `ground_left` and `ground_right`. The uniform material is
`dielectric`. Top/bottom planes lie at B and zero. No ground is inserted between
the two signals. Positive dimensions, nonnegative loss, separation from planes,
nonoverlap and containment in the box are validated. Widening a tapered signal
can invalidate an otherwise positive bottom-edge gap.

For a single trace, the side-ground center distance is
`d=(width+ground_width)/2+gap`; for a pair it is
`d=width+gap/2+ground_gap+ground_width/2`. If `box_width` is omitted,
the single uses `max(12*B, 4*width, 2*d+ground_width+4*B)` and the pair uses
`max(12*B, 4*(2*width+gap), 2*d+ground_width+4*B)`.
Defaults are starting domains, not convergence certificates. Increase the box
with **fixed physical ground widths and gaps** to test the outer boundary.
Changing ground width changes the physical geometry.

Zero-thickness sheets are supported for electrostatics and the analytic CPW
limit. Existing surface-conductor loss requires nonzero thickness and its
skin-depth/flux checks; this template does not relax those checks. Finite
rectangular or tapered signals can use the existing [face surface laws](face_conductor.md)
and [reference surface laws](reference_surfaces.md).

## Saved studies and impedance goals

The existing geometry JSON and study/design schemas accept these names.
Older builds reject unknown template names, so record the exact engine revision.
Single-signal studies use `z0`; the pair accepts `z_diff` and `z_diff_forward`.
These are real quasi-static impedance diagnostics, excluding conductor R and
dielectric G. Existing line/network models provide frequency-dependent loss.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.yield_assessment import ImpedanceYieldDocument
from sipi.execution import execute_saved, normalize_saved

study = ImpedanceStudyDocument("coupled_coplanar_stripline", parameters,
    quantity="z_diff", mesh=mesh, fixed_pitch_m=.6e-3,
    sampling=dict(kind="uniform", count=2, seed=17,
        variables=[dict(name="width", lower=.28e-3, upper=.32e-3)]))
assert normalize_saved(study.dumps()) == study.dumps()
report = execute_saved(ImpedanceYieldDocument(study, minimum=1., maximum=1000.).dumps(),
                       max_evaluations=2)
assert len(report["result"]["rows"]) == 2
```

This two-sample example demonstrates replay, not manufacturing yield confidence.
`fixed_pitch_m` keeps `width+gap` constant for the pair. Side grounds move to
preserve `ground_gap`; their absolute positions are not fixed. Correlated normal
sampling retains invalid rows without resampling. The single rejects horizontal
fixed pitch, and both templates reject the two-layer fixed-plane-spacing
constraint. Scalar/principal-axis material bindings address `dielectric` using
the existing fixed-frequency study contract.

```python
from sipi import ImpedanceDesignDocument

goal = ImpedanceDesignDocument("coupled_coplanar_stripline", dict(parameters, gap=.5e-3),
    variable="width", bounds=[.15e-3, .65e-3], target=100., quantity="z_diff",
    fixed_pitch_m=.8e-3, tolerance=.5, max_evaluations=24, mesh=mesh)
assert normalize_saved(goal.dumps()) == goal.dumps()
result = goal.solve()
assert abs(result.residual) <= .5 and abs(result.refined_residual) <= .5
```

The same target must pass the requested and separately refined meshes.
This bounded one-variable result is not a global optimum or a measured tolerance.

## Numerical validation and scope

`tests/sipi/test_coplanar_stripline.py` compares complex/vacuum C and C_loss with
independent scikit-fem P1 assembly at 1e-10 normalized matrix error. Identical-mesh
uniform material/loss scaling uses 1e-12. Independently remeshed vertical
reflection permits 0.5%; representative mesh changes in C/Z are limited to 1.5%,
and doubling box width to 0.5%. Moving side grounds far away compares with the
existing offset/paired stripline models within 2%.

The thin homogeneous CPW limit uses k = w/(w+2g), with complete elliptic integrals
K in modulus notation: C = 4 eps0 eps K(k)/K(sqrt(1-k²)),
Z = sqrt(mu0/eps0) K(sqrt(1-k²))/(4 sqrt(eps) K(k)). SciPy `ellipk` takes the
**squared modulus**. With planes and ground ends far away, both C/Z must be within
2% of this limit and improve under mesh refinement. This finite-geometry test
does not prove the same error for every user geometry.

These checks do not model stitching vias, pad transitions, radiating or floating
ground traces, three-dimensional return-current paths, or measured material
accuracy. Grounding is an explicit idealization; a finite strip with no physical
connection to the reference network requires a different electrical model.

See [manufacturing sections](manufacturing_sections.md), [studies](study.md),
[yield assessment](yield.md) and [impedance design](design.md).
