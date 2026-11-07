# Gaussian conductivity profile at an explicit exterior plane

[Saved profile inputs](conductivity_profile_document.md) preserve the exterior cutoff and apply pre-integration frequency budgets.

`GaussianConductivityProfile` computes the 1D full-Maxwell surface impedance
of a nonmagnetic conductor with a prescribed Gaussian conductivity transition.
It returns the port's position as well as its impedance. It is a separate
half-space constitutive kernel; it is not accepted as a `roughness=` multiplier
or added to a transmission line's mean-plane external inductance.

```python
import numpy as np
from sipi import GaussianConductivityProfile

profile = GaussianConductivityProfile(conductivity=58e6, rms_m=1e-6)
result = profile.analyze([1e9, 4e9, 10e9])
assert result.reference_plane_m == -8e-6
assert np.all(result.impedance.real > 0)
assert not result.impedance.flags.writeable
assert not result.frequency.flags.writeable
assert np.all(result.skin_depth > 0)
```

## Physical and numerical contract

All inputs use SI units: conductivity in S/m, RMS height `rms_m` in metres,
frequency in Hz, output E/H in ohms per square. `rms_m` is Rq, not Ra or Rz;
no conversion, packing assumption or measured material fitting is inferred.
The coordinate x increases **into the metal**, with x=0 at the statistical
mean plane. Use `exp(+j omega t)`, permeability mu0 and permittivity eps0
everywhere. Within the transition:

```text
sigma(x) = sigma_bulk * Phi(x/Rq)
delta = 1/sqrt(pi*f*mu0*sigma_bulk)
Rs = sqrt(pi*f*mu0/sigma_bulk)
rho = Rq/delta, xi = omega*eps0/sigma_bulk, u = x/Rq
y = Z/Rs
dy/du = rho * ((Phi(u) + j*xi)*y*y - 2j)
y(+cutoff) = (1+j)/sqrt(1+j*xi)
```

`Phi` is the standard normal CDF. Beyond the two cutoffs, conductivity is
zero on the exterior side and sigma_bulk on the interior side. This defines
the truncated model explicitly. `cutoff_rms` defaults to 8 and is restricted
to [5,10]. Output is evaluated at **x=-cutoff_rms*Rq**, not the mean plane.
The bulk boundary uses the full-Maxwell intrinsic impedance, including
displacement current. Zero RMS returns that smooth impedance at x=0 without
integration. This differs slightly from the good-conductor approximation
`(1+j)*Rs` in the older surface-loss adapter.

The bounded contract requires positive conductivity, nonnegative RMS,
1..1024 strictly increasing positive frequencies, `rho<=10` and `xi<=1e-3`.
Booleans, nonfinite values, unrepresentable scales and unsupported ranges
fail before integration. Inclusive bounds permit only floating-point
roundoff in the log arithmetic; samples are not clamped, and values 1e-9
relatively outside either bound are rejected. The fixed DOP853 tolerances
are relative 2e-11 and absolute 2e-12 in normalized impedance. Integration
failure, nonfinite output or nonpositive resistance fails explicitly.
Input arrays are copied; result frequency/impedance arrays are read-only.

## Reference plane and energy

At the exterior plane the real impedance represents inward dissipation.
Reactance is the difference of magnetic and electric storage; it can be
negative at electrically long numerical boundary cases. It is never clipped
or replaced with its absolute value. A positive bulk conductivity alone does
not make this exterior-port impedance an inductance-only correction.

Changing cutoff also moves the port. To compare two cutoffs, translate both
to the same exterior plane through the exact lossless vacuum transmission
relation, with `eta=sqrt(mu0/eps0)` and `k=omega*sqrt(mu0*eps0)`:

```text
Z_at_farther_exterior = (Z + j*eta*tan(k*d)) / (1 + j*Z/eta*tan(k*d))
```

Simple subtraction of air inductance is only a magnetoquasistatic limit.
Combining this kernel with general 2D external fields, finite copper,
curvature/corners or face-current redistribution needs a separate reference
plane and geometry contract. No saved line schema, fitting, physical
frequency-range calibration, transient/causality certification, measured
foil accuracy or browser/Windows acceptance is supplied by this API.

## Independent checks and sources

The Gaussian conductivity premise is described by
[Gold et al., 2019, section 3.3, equation 2](https://ars.copernicus.org/articles/17/51/2019/)
(CC BY 4.0). The explicit truncated exterior-port definition above is our
contract; agreement with every effective-material formulation in that paper
is not inferred. No article figures, measured data or external solver source
are copied into this package.

`tests/sipi/test_conductivity_profile.py` compares to the independent
[scikit-rf 2.2.0 surface solver](https://scikit-rf.readthedocs.io/en/latest/api/generated/skrf.tlineFunctions.surface_impedance.html),
matching its +/-5Rq transition, bulk load, eps0/mu0 and output plane.
That BSD-3-Clause tool is test-only; its exact v2.2.0
[license](https://raw.githubusercontent.com/scikit-rf/scikit-rf/v2.2.0/LICENSE.txt)
and installed source were checked. SciPy integration is an existing runtime
dependency; no new dependency or bundled binary is introduced.

The acceptance gates are:

- Two RMS scales (1 and 100 um), nine rho values .001..10: complex tool
  agreement <1e-6, with no tool warnings.
- Eighteen combinations of rho [.001,.01,.1,1,3,10] and xi [1e-9,1e-6,1e-3]:
  tool agreement <1e-6; independent **linear E/H** integration and separate
  dissipation/magnetic-minus-electric energy quadrature agree within 1e-8.
  The extreme frequencies in this dimensionless grid test the numerical
  contract, not measured metal behavior there.
- Piecewise constant transmission layers, 2048→4096: impedance error decreases
  and finishes below 1e-5. After exact vacuum translation to x=-10Rq,
  cutoff8→10 difference is <1e-8; cutoff5→10 is <1e-4.
- Zero-RMS intrinsic impedance agrees within 1e-12. Scaling conductivity and
  frequency by k while dividing RMS by k preserves impedance within 1e-10.
  Strict input, copied-result, failed-solve and unsupported-adapter checks
  preserve the boundary between this kernel and line extraction.

[Surface-loss adapter](conductor.md) · [한국어](../../locales/ko/pages/packages/sipi/conductivity_profile.md)
