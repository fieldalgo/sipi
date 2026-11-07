# Explicit ten-point Rz surface model

`CannonballHuray` maps positive **ten-point mean roughness Rz(m)** to the existing
[causal Huray law](roughness.md). Select it when that statistic and approximation apply.
Here ten-point Rz means the mean of the five highest peaks plus the magnitudes
of the five deepest valleys over the stated sampling length, relative to the mean line.

```python
from sipi.roughness import CannonballHuray
from sipi.conductor import surface_impedance

model = CannonballHuray(rz_10point_m=3e-6)
print(model.radius_m, model.surface_ratio)
print(model.to_huray())
print(surface_impedance([1e9, 4e9, 10e9], conductivity=58e6, roughness=model))
```

The immutable model uses the published rounded `radius_m = 0.06*rz_10point_m`,
and full-sphere area ratio `14*pi/9` (not rounded to 4.9). Fourteen equal spheres
occupy a `36*r**2` tile with a base-area ratio of one. The triangular-profile and
9/4/1 FCC stacking assumptions are heuristic, not measured surface geometry.
See Lambert (Bert) Simonovich, *PCB Interconnect Modeling Demystified*, DesignCon
2019, pp. 12–13, equations 11–14 ([paper](https://swb.skku.edu/emc/infromation.do?articleNo=21942&attachNo=19820&mode=download)),
and the [author's explanation](https://blog.lamsimenterprises.com/2019/03/29/cannonball-huray-model-demystified/).
No source figures, code or measurement data are distributed.

`factor(skin_depth)` accepts nonempty positive finite 1D depths and returns a
**complex multiplier**, not the resistance ratio. The conductor adapter delegates
stable R/X factors to `CausalHuray`. High/low-frequency multipliers tend to
`1+7*pi/3` and 1. These mathematical limits do not permit surface extraction at DC.
`to_huray()` exposes the equivalent immutable population.

Zero, negative, nonfinite, boolean and unrepresentable-radius inputs are rejected.
Use `roughness=None` or saved `kind="smooth"` for zero roughness. Ra, Rq or other
Rz definitions are not converted. No matte/drum averaging, treatment correction
or dielectric adjustment is automatic. All surfaces share one model. Existing
good-conductor, skin-depth, thickness and current-convergence gates remain;
roughness must also be physically small relative to dimensions, curvature and gaps.
Smooth finite-metal diffusion is unchanged. A causal material law alone does not
certify the complete line's causality or its agreement with measured foil.

## Saved inputs and verification

In the surface conductor of `sipi.transmission-line/2`, select:

```json
{"kind": "cannonball-huray", "rz_10point_m": 0.000003}
```

Conductivity, relative permeability and ground thickness remain required. Rz is
saved explicitly. Unknown/missing fields, duplicate keys and version-1 mixing
fail before meshing. Shared-mesh RLGC/network calculation uses the same model.
Existing smooth, Hammerstad, Groiss and explicit Huray definitions/serialization
remain unchanged. Nonzero `roughness_rms` cannot be combined with this model.

Independent sphere centres and triangular-profile quadrature give radius/Rz
0.05978657793452507; the published 0.06 differs by 0.357% (preregistered rounding
limit 0.5%, **not physical accuracy**). Positive-relaxation quadrature checks the
complex law to `1e-10`; scaling and real-loss identities use `1e-12`.
Analytic coax extraction at radial 64/128/256 and angular 256 cells requires
decreasing R/internal-L errors and a final error below 1%. A microstrip pair halves
edge/far/grade, requiring changes below 5% and current error below 5%.
Saved replay and equivalent populations require RLGC `1e-12` and S `1e-10`.
Extreme/rejected inputs, passivity and reciprocity are checked separately.
These tests do not reproduce the source paper's measured coupons. SciPy supplies
independent test quadrature; no runtime dependency is added.

[한국어](../../locales/ko/pages/packages/sipi/cannonball.md)
