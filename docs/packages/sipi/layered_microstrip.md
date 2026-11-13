# Surface lines above two substrate layers

[한국어](../../locales/ko/pages/packages/sipi/layered_microstrip.md)

`layered_microstrip` and `coupled_layered_microstrip` place one signal or an
equal-width pair above two dielectric substrate layers. Both layers lie below
copper. The bottom ground is at zero; the copper bottom is at
`lower_height + upper_height`. Heights exclude copper, unlike the upper-height
contract for an interface stripline. Open top and side boundaries represent a
finite truncation of the surrounding air.

```python
from sipi import layered_microstrip, CrossSectionDocument

section = layered_microstrip(
    width=0.5e-3, thickness=35e-6,
    lower_height=0.3e-3, upper_height=0.7e-3,
    lower_eps_r=3.0, upper_eps_r=5.0,
    lower_tan_delta=0.01, upper_tan_delta=0.03,
    air_height=10e-3, box_width=20e-3,
)
document = CrossSectionDocument(section, mesh={
    'edge_size': 2.5e-6, 'far_size': 0.125e-3, 'grade': 0.1,
})
line = document.analyze()
print(line.z0)
```

All lengths are metres. Each substrate height is positive, relative permittivity
is at least one and loss tangent is nonnegative. Copper thickness may be zero;
a different `top_width` needs finite thickness. Tapers are centred and the bottom
width remains explicit. The pair also requires a positive bottom-edge `gap`;
`positive` is the left conductor and `negative` is the right. Its equal signals
and lateral symmetry support the existing even/odd diagnostics.

`air_height` is the entire air-layer height above the substrate, including copper.
Its default is ten total substrate heights plus copper thickness. The default
box is at least twenty total substrate heights, also respecting the existing
single/pair span rule. Explicit domains that clip copper are rejected. Enlarge
the air and box independently and refine the mesh before using a result.

These factories use the existing electrostatic/complex dielectric extraction;
they do not infer frequency dispersion, copper resistance or a roughness model.
They return ordinary `CrossSection` objects. Save them as `CrossSectionDocument`
and pass width factories to `seek_impedance`, whose separate refined solve stays
required. Editable template registration, saved study/goal forms and a dedicated
workbench form are a subsequent integration step; these two API factories do not
change the existing registered-template inputs.

Validation uses scikit-fem 12.0.2 with independent material assignment and complex
and vacuum energy assembly. For the specified single/pair case in
`tests/sipi/test_layered_microstrip.py`, maximum normalized C/C_loss/C0 differences
are below `1e-10`. Vacuum identities and the equal-material limit are checked
separately. The preregistered mesh-change gate is 1%; independent box/air doubling
gates are 0.5%. Observed maxima are about 0.3373%, 0.3105% and 0.0147%, respectively.
These bounds describe the selected numerical checks, not measured-board accuracy
or all geometries. The uniform-substrate comparison is within 0.5%; it does not
replace the independent assembly or the domain checks.
