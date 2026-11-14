# Explicit core and coating interfaces in 2D metal

`mesh_conductor_section(..., metal_cores={name: vertices})` inserts a material
interface inside an existing finite trace. The trace is the **finished outer
metal boundary**. `vertices` defines one simple core polygon strictly inside
it; the remaining metal is the coating. The API does not infer thickness,
offset corners, expand the conductor, or simulate a deposition process.
Rectangular, tapered and polygonal traces and explicit grounded traces may
carry a core. Generated reference plates remain homogeneous.

Core boundaries must not touch or leave their trace. Vertices are in the same
metre coordinate frame as the cross-section, without a duplicate closing
point. Names must identify existing traces. Invalid names, polygons, nonfinite
coordinates, booleans and boundary contact fail before meshing. Very small
features remain subject to the shared mesher's resolution/size limits.

```python
import numpy as np
from sipi import microstrip
from sipi.conductor_mesh import mesh_conductor_section

section = microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                     eps_r=4., tan_delta=.02, box_width=.002, air_height=.5e-3)
core = ((-.18e-3, .52e-3), (.18e-3, .52e-3),
        (.18e-3, .58e-3), (-.18e-3, .58e-3))
volume = mesh_conductor_section(
    section, metal_cores={'signal': core}, ground_thickness=.1e-3,
    padding=.002, metal_size=25e-6, far_size=.25e-3, grade=.1,
    dielectric_interfaces=True,
)
sigma = np.zeros(volume.mesh.num_triangles)
sigma[volume.signals['signal']] = 20e6   # coating conductivity, S/m
sigma[volume.core_triangles['signal']] = 58e6
sigma[volume.ground] = 58e6
result = volume.impedance([0, 1e3, 1e4, 1e5], conductivity=sigma, keep_fields=True)
assert max(result.current_error) < 1e-10
```

The generated mesh conforms to both core and outer metal boundaries.
`volume.signals[name]` contains **core and coating together**. The optional
read-only `core_triangles` mapping selects the core subset; the coating is
its set difference from the original trace's full metal group. A grounded
trace's core is included in the common `ground` current group. No artificial
voltage or extra port is placed on the interface: the same longitudinal E
constant drives both materials and the field solve redistributes current.
The geometry choice and material coefficients remain separate.

Dielectric extraction removes the entire core-plus-coating conductor. Core
conductivity therefore does not change the outer electric geometry or C/G on
a given mesh. The explicit interface can change the discretization when the
mesh is regenerated; compare mesh and outer-domain convergence separately.
Uniform permeability and all diffusion good-conductor, local skin-depth,
current, Joule power and magnetic-energy gates remain in force.
`metal_cores=None` and `{}` use the original meshing path. Existing volume-line
v1/v2 JSON does not save these interfaces; it still describes homogeneous
conductors within each named region.

## Validation boundary

`test_metal_cores.py` checks exact core/coating polygon areas and interface
perimeter, DC resistance `1/sum(sigma*area)` plus the return resistance, local
DC current densities, tapered/polygon/ground cores, reserved-looking trace
names, immutable inputs and rejected invalid cores. An independent
scikit-fem P1 augmented solve uses physical coordinate masks rather than the
returned core indices and compares Z, Jz and Az at normalized 1e-9.

For the example's .4 by .1 mm conductor, 20 micrometre coating on all sides,
58/20 MS/m core/coating and 58 MS/m return, the 25→12.5 micrometre metal mesh
with separately halved far size/grade changes R by 8.69e-6 and L by .002308
relative over DC/1/10/100 kHz; each gate is .01. Increasing fine-mesh padding
from 2 to 4 mm changes L by .01194 (gate .02). Independent Z/J/A errors are
at most 1.89e-14 on that common mesh. These measurements apply to the stated
case, not arbitrary thin plating, nonlinear magnetic coatings, temperature
laws, 3D transitions or measured foil accuracy.

[한국어](../../locales/ko/pages/packages/sipi/metal_cores.md)

## Save the interface and its material

`VolumeLineDocument(..., metal_cores=...)` selects `sipi.volume-line/3`.
The nonempty mapping associates each existing trace name with exactly
`vertices` and a positive scalar `conductivity` in S/m. Supply named base
conductivities (`signals` and `ground`), as in v2: they apply to coating and
uncoated metal. Each core overrides that base value inside its polygon.

```python
from sipi import CrossSectionDocument, microstrip
from sipi.volume_line import VolumeLineDocument
from sipi.execution import normalize_saved, execute_saved

section = microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                     eps_r=4., tan_delta=.02, box_width=.002, air_height=.5e-3)
doc = VolumeLineDocument(
    CrossSectionDocument(section), [0, 1e3, 1e4], materials={}, length=.1,
    conductivity=dict(signals={'signal': 20e6}, ground=58e6),
    metal_cores={'signal': dict(conductivity=58e6, vertices=[
        [-.18e-3, .52e-3], [.18e-3, .52e-3],
        [.18e-3, .58e-3], [-.18e-3, .58e-3]])},
    mesh=dict(ground_thickness=.1e-3, padding=.002, metal_size=25e-6,
              far_size=.25e-3, grade=.1, min_angle=28.),
)
text = doc.dumps()
assert normalize_saved(text) == text
output = execute_saved(text)
assert output['status'] == 'complete'
```

Normalization validates and copies geometry/materials without meshing. Loading
and execution regenerate the conforming mesh and assign conductivities by
physical name and coordinates; triangle numbers are never saved. An explicit
grounded trace may have a core with its own conductivity while remaining part
of the common return. A circuit's `kind='volume-line'` input accepts the same
v3 document. Ordinary solver failures, including insufficient skin-depth
resolution, still propagate as errors.

v1/v2 documents retain their original schemas and serialized values. They
reject the new field; v3 requires it and named base conductivity. No automatic
version upgrade, scalar-to-named conversion or inferred coating thickness is
performed. `metal_cores=None` in the constructor retains v1/v2 selection; an
empty mapping is invalid for v3. Tests compare saved and direct R/L/C/G/S/J,
analytic DC resistance at 1e-10, fresh-mesh material assignment, circuit
termination and strict invalid inputs. The mesh/reference limits above still
apply. Saved interfaces do not add temperature, magnetic material variation,
multiple nested coating layers or arbitrary conductivity fields.
