# Groiss RMS correction for frequency-domain analysis

`sipi.roughness.GroissRMS(rms_m)` specifies an empirical, **noncausal** correction
to the surface impedance of a good-conductor half-space. The input is the RMS
surface height **Rq in metres**, not Ra or Rz. No conversion is inferred.

```python
from sipi.roughness import GroissRMS
from sipi.conductor import surface_impedance
zs = surface_impedance([1e9, 4e9, 10e9], conductivity=58e6,
                       roughness=GroissRMS(.5e-6))
```

For skin depth δ and positive Rq, `K = 1 + exp(-(δ/(2 Rq))**1.6)` and
`Zrough = K Zsmooth`. Both resistance and reactance are multiplied by the same
real factor. Rq=0 gives exactly the smooth result; K lies between 1 and 2.
Finite extreme input scales use logarithmic evaluation to avoid intermediate
overflow. `factor(skin_depth)` accepts a nonempty positive one-dimensional array
and preserves order. Negative, nonfinite, boolean or nonscalar RMS is rejected.

This contract differs from the existing `roughness_rms` Hammerstad option,
which changes resistance only, and `CausalHuray`, which has distinct causal
resistance/reactance changes. A model object and nonzero `roughness_rms` cannot
be combined. `ConductorLoss.roughness_factor` remains the resistance ratio.
The same object is accepted by `surface_conductor_loss` without changing its
good-conductor, thickness, skin-depth, mesh or current-flux validity gates.

The model is intended for relatively polished surfaces and saturates at twice
the smooth impedance. It does not validate highly rough PCB foil, fit measured
coupons, resolve surface texture or establish a time-domain response. Use it
only for frequency-domain calculations. Passing it to a line input does not make
that line causal. Smooth-metal volume diffusion does not receive this multiplier.

For `TransmissionLineDocument`, explicitly select schema
`sipi.transmission-line/2` and the surface conductor record's
`roughness={"kind":"groiss", "rms_m":0.5e-6}`. Only `kind` and `rms_m` are
allowed in that object. Existing v1 and other v2 model meanings are unchanged;
older readers reject the new kind. Save the SIPI version with the input.
Geometry, materials, frequency samples, RLGC, S and propagation reuse the existing
shared-mesh line path. The saved selection remains explicit on JSON replay.

Validation in `tests/sipi/test_groiss.py` requires:

- Independent SciPy Weibull survival evaluation and quadrature of its density
  across δ/(2Rq)=0.01…10, relative/absolute agreement <=1e-12. This checks the
  specified empirical equation, not physical rough-surface accuracy.
- Exact smooth/saturated limits, monotonicity, finite extreme scales and
  conductivity/permeability/Rq dimensional similarity; invalid and mixed inputs.
- Independent analytic coaxial surface-current geometry: radial refinements
  64→128→256 must reduce R/internal-L errors to <1%. Fixed angular subdivision
  is 256. Single microstrip edge/far/grade refinement by two must change R and
  internal L by <5%, with integrated-current error <5%.
- Strict JSON, one shared mesh, unchanged legacy regressions, direct surface
  extraction agreement <=1e-10, replay, reciprocity/passivity and propagation.

No dependency or binary is added. SciPy 1.18.1 (BSD-3-Clause) provides the numerical
reference in the recorded Linux checks. No new platform or measured accuracy
claim follows from these equation and geometry tests.

The equation and RMS definition are given in Chen and Tian, *Micromachines* 14
(2023), 104, equations 8–9, DOI [10.3390/mi14010104](https://doi.org/10.3390/mi14010104).
The original model is attributed to Groiss et al., *IEEE Transactions on
Magnetics* 32 (1996), 894–897, DOI [10.1109/20.497385](https://doi.org/10.1109/20.497385).
These citations identify the model; they do not imply reproduction of either
paper's experimental results.

[Other roughness models](roughness.md) · [Line input](line_model.md) ·
[한국어](../../locales/ko/pages/packages/sipi/groiss.md)
