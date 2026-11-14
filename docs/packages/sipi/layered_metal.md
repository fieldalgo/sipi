# Planar layered-metal surface impedance

`layered_surface_impedance` computes E/H at the finished outer surface of
perfectly contacted, planar metal layers over a semi-infinite base metal.
This local magnetoquasistatic (MQS) diffusion model resolves thin coatings without
requiring each coating to be thicker than its skin depth.

```python
from sipi import MetalLayer, layered_surface_impedance

result = layered_surface_impedance([1e6, 1e8, 1e10], conductivity=58e6,
    layers=[MetalLayer(.2e-6, 14e6, 3.), MetalLayer(1e-6, 40e6)])
assert result.impedance.shape == (3,)
assert result.skin_depth.shape == (3, 3)
print(result.impedance)  # ohm/square at the outer metal surface
```

Layers run **from outside inward**. `conductivity` and `relative_permeability`
on the function describe the base half-space. Each `MetalLayer` gives thickness
in meters, conductivity in S/m and positive real relative permeability. Zero
thickness removes that layer. Zero layers reproduce the existing smooth bulk
impedance exactly. Splitting a uniform layer preserves the physical model.

Use 1..1024 increasing positive frequencies and 0..32 finite layers. All
materials must satisfy the existing good-conductor bound
`sigma/(omega*eps0) >= 1000`. Conductivity and permeability are positive,
isotropic, linear and frequency independent. Result arrays are copied and
read-only; skin-depth columns follow the layers and then the base.

The implementation propagates impedance from the base to the surface using
`eta*(Zback+eta*tanh(k*d))/(eta+Zback*tanh(k*d))`, with `k=(1+j)/delta` and
`eta=(1+j)*sqrt(pi*f*mu/sigma)`. Scaled impedances avoid overflowing the
transfer matrix. For `d/delta >= 350`, tanh is one to floating-point precision;
the exponentially suppressed back surface has no representable effect. Input
and nonrepresentable-result errors raise instead of producing a valid model.

The reference plane is the **outer metal surface**, with no added exterior-air
inductance. This API does not automatically apply the planar half-space model
to finite thickness, corners or curved 2D traces. It does not generate plating
geometry or combine roughness, contact resistance, complex magnetic loss,
hysteresis or measured material fitting. Use explicit core geometry and the
volume-diffusion solver when finite metal geometry must be resolved.

Independent tests compare a 2x2 diffusion matrix exponential and a depth-scaled
ODE, including the integral of sigma*|E|^2 and bulk-tail power. Finite base-depth
checks at 8/12/16 skin depths verify the half-space limit. Layer-order,
homogeneous partition, zero/thick-layer and diffusion-scale invariants are
separate checks. No 2D mesh or exterior boundary is used here; these remain
separate requirements for a subsequent cross-section adapter.

[한국어](../../locales/ko/pages/packages/sipi/layered_metal.md)
