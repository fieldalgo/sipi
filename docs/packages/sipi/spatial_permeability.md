# Piecewise linear permeability in 2D current diffusion

`conductor_impedance(..., relative_permeability=mu_r)` accepts either the
original positive scalar or a real array with one positive finite value per
mesh triangle. The array covers **all triangles, including nonconducting
space**. Conductivity and permeability are independent inputs. Materials are
linear, isotropic, nondispersive and lossless magnetically; conductivity still
produces Joule loss. Negative/zero, complex, Boolean and nonfinite values or
incorrect shapes fail before field assembly.

The mesh must conform to material interfaces. The solver uses
`K = integral (1/mu) grad(Az) dot grad(test)` with `mu = mu_0*mu_r` and uses
that same stiffness for magnetic energy. The weak form provides flux
continuity at material boundaries; no additional artificial port or current
constraint is added. Each signal and the common return retain their prescribed
net currents. Total inductance includes internal and external magnetic energy.

```python
import numpy as np
from sipi import microstrip
from sipi.conductor_mesh import mesh_conductor_section

section = microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                     eps_r=4., box_width=.002, air_height=.5e-3)
volume = mesh_conductor_section(
    section, ground_thickness=.1e-3, padding=.002,
    metal_size=25e-6, far_size=.25e-3, grade=.1,
    metal_cores={'signal': [(-.18e-3, .52e-3), (.18e-3, .52e-3),
                            (.18e-3, .58e-3), (-.18e-3, .58e-3)]},
)
sigma = np.zeros(volume.mesh.num_triangles)
sigma[volume.signals['signal']] = 20e6
sigma[volume.core_triangles['signal']] = 58e6
sigma[volume.ground] = 58e6
mu_r = np.ones(volume.mesh.num_triangles)
mu_r[volume.signals['signal']] = 5.
mu_r[volume.core_triangles['signal']] = 2.
result = volume.impedance([0, 1e3, 1e4], conductivity=sigma,
                          relative_permeability=mu_r)
assert max(result.magnetic_energy_error) < 1e-9
```

These are explicit illustrative coefficients, not a calibrated material law.
Magnetic coatings with hysteresis, saturation, frequency dependence, complex
permeability or tensor permeability are outside this model. Assigning a
constant value does not validate such a coating physically.

At each positive frequency the skin-depth gate uses the **colocated** product
`mu[t]*sigma[t]` inside each metal triangle. The reported `skin_depth` is the
minimum over metal; `max_edge_over_skin_depth` is the maximum local ratio.
Products of separate global maxima would reject valid cases with anticorrelated
materials. Nonmetal permeability changes the field but not this metal skin
gate. DC resistance remains fixed by conductivity and area. On a given matched
volume mesh, C/G do not change with permeability. Refinement and outer-domain
checks remain necessary beyond current, power and magnetic-energy identities.

`VolumeLineDocument` v1/v2/v3 still require scalar permeability. Mesh-indexed
arrays are a direct API input, not a portable saved-material definition.

## Verification

`test_spatial_permeability.py` compares a coaxial centre/return with relative
permeability 2/5, conductivity 58/20 MS/m, and gap permeability 3 against
independent cylindrical Bessel solutions at 100 Hz, 10 kHz and 100 kHz.
Radii are .5/1.5/2 mm, with 256 angular sectors and 16/32/64 radial subdivisions.
R/L/Z errors must decrease and finish below 1%; analytical DC magnetic energy
must agree within .1%. Enlarging the magnetic exterior from 3 to 6 mm must
change Z by less than 1e-9 in this field-confined geometry. These bounds are
case-specific, not a claim for arbitrary magnetic materials or boundaries.

Independent scikit-fem augmented equations compare Z, Az and Jz on the same
mesh at normalized 1e-9. Additional checks cover uniform scalar/array agreement
at normalized 1e-13, local skin gates, DC energy monotonicity, unchanged C/G,
passive networks and invalid coefficients. The unchanged scalar path retains
its prior arithmetic and numerical gates.

[한국어](../../locales/ko/pages/packages/sipi/spatial_permeability.md)

## Named magnetic materials in saved volume-line v4

Passing a mapping as `VolumeLineDocument`'s `relative_permeability` selects
`sipi.volume-line/4`. The object has exactly four fields:

- `signals`: one positive real value for each signal name.
- `ground`: one value for every generated plate and explicit grounded trace.
- `nonmetal`: one value for all nonconducting triangles.
- `cores`: one value for each explicit core name, overriding its metal's value.

This requires named base conductivity (`signals` and `ground`) and saves
`metal_cores` using the v3 coordinate/conductivity contract. An empty core
mapping is allowed in v4 and remains explicit in its JSON. Names such as
`ground` or `nonmetal` inside `signals` are still ordinary signal names.
No triangle indices are stored; fresh meshes receive materials by name.

```python
from sipi import CrossSectionDocument, microstrip
from sipi.volume_line import VolumeLineDocument
from sipi.execution import normalize_saved, execute_saved

section = microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                     eps_r=4., box_width=.002, air_height=.5e-3)
doc = VolumeLineDocument(
    CrossSectionDocument(section), [0, 1e3, 1e4], materials={}, length=.1,
    conductivity=dict(signals={'signal': 20e6}, ground=58e6),
    relative_permeability=dict(signals={'signal': 5.}, ground=3., nonmetal=1.,
                               cores={'signal': 2.}),
    metal_cores={'signal': dict(conductivity=58e6, vertices=[
        [-.18e-3, .52e-3], [.18e-3, .52e-3],
        [.18e-3, .58e-3], [-.18e-3, .58e-3]])},
    mesh=dict(ground_thickness=.1e-3, padding=.002, metal_size=25e-6,
              far_size=.25e-3, grade=.1, min_angle=28.),
)
text = doc.dumps()
assert doc.to_dict()['schema'] == 'sipi.volume-line/4'
assert normalize_saved(text) == text
assert execute_saved(text)['status'] == 'complete'
```

Validation rejects missing/extra names or fields, array values, invalid
coefficients and incompatible schema versions before meshing. Scalar
permeability still selects the earlier versions; they do not silently accept
this object. v4 does not infer unnamed materials or promote scalar conductivity.
The common executor and a circuit's `kind='volume-line'` source replay the same
input. Insufficient skin resolution still raises an error. Tests compare saved
and direct R/L/C/G/S/J, material assignment after remeshing, DC area resistance,
circuit response and uniform-v2 agreement at normalized 1e-13. The analytical
and independent field gates above remain unchanged.

This saved format assigns a single nonmetal permeability; multiple magnetic
dielectric regions still require a directly supplied conforming field. It does
not introduce dispersive, nonlinear or lossy magnetic models.
