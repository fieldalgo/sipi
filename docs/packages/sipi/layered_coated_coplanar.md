# Planar-coated coplanar signals above two substrates

[한국어](../../locales/ko/pages/packages/sipi/layered_coated_coplanar.md)

These factories combine two independently specified substrate materials,
a full-width planar coating and finite rectangular side grounds:

| Signals | Bottom plane grounded | No backing plane |
|---|---|---|
| One | `layered_coated_grounded_coplanar` | `layered_coated_unbacked_coplanar` |
| Equal pair | `coupled_layered_coated_grounded_coplanar` | `coupled_layered_coated_unbacked_coplanar` |
| Unequal pair | `asymmetric_coupled_layered_coated_grounded_coplanar` | `asymmetric_coupled_layered_coated_unbacked_coplanar` |

Substrate heights exclude copper. The coating starts at their upper surface,
fills the gaps and includes all copper; `coating_height` must exceed every
signal and ground thickness. `air_height` begins above the film. This is a flat
layer, not a film of uniform normal thickness around a tapered trace.

Single-line `gap` separates bottom signal edges from the side grounds. In pairs,
`gap` separates bottom signal edges and `ground_gap` separates the outside
signals from the grounds. Grounds have explicit finite `ground_width`. Equal
signals and grounds share thickness. Unequal signals have independent bottom
widths, thicknesses and centered top widths; `ground_thickness` is separate.
Positive is left, negative right. There is no center ground or inferred 3D
connection between the side grounds.

Grounded variants have a grounded bottom computational boundary,
with open top and sides. Unbacked variants instead
have air below the finite substrate and open boundaries on all four sides;
only the two finite side grounds fix the potential. `lower_air_height` translates
both substrate layers, the film and all copper. Its default is ten times the
sum of the two substrate heights, excluding film and copper. Upper and lower
air extents require separate convergence checks.

```python
from sipi import layered_coated_unbacked_coplanar, CrossSectionDocument
section = layered_coated_unbacked_coplanar(
    width=.5e-3, gap=.2e-3, ground_width=1e-3,
    thickness=35e-6, top_width=.4e-3,
    lower_height=.3e-3, upper_height=.7e-3,
    lower_eps_r=3., upper_eps_r=5.,
    lower_tan_delta=.01, upper_tan_delta=.03,
    coating_height=80e-6, coating_eps_r=3.3, coating_tan_delta=.02,
    lower_air_height=.01, air_height=.01, box_width=.02)
text = CrossSectionDocument(section).dumps()
```

The factories support direct Python and geometry JSON. Named parameter-study,
width-goal and dedicated form integration is separate. Single-line `z0`,
equal-pair even/odd diagnostics and unequal-pair real `z_diff_forward` at
Icommon=0 keep their existing meanings; independent symmetric modes are not
assumed for unequal signals.

Representative pairs add 0.3 mm inter-signal and 0.2 mm outside gaps. Unequal
signals use 0.4/0.7 mm widths, 25/45 µm copper, 0.32/0.55 mm top widths and
35 µm side grounds. Independent height-based complex and vacuum material
assignment in scikit-fem 12.0.2 provides a P1 energy comparison at normalized
1e-10. Edge/far/grade refinement from 5 µm/0.25 mm/0.2 to
2.5 µm/0.125 mm/0.1 uses a 1% capacitance/impedance-change gate; individually
doubling box width, above-film air and unbacked lower air uses 0.5% gates.
Uniform-substrate and air-valued-film limits use the corresponding existing
factories within 0.5%, with the same total upper height in the air-film limit.
Vacuum identities, reciprocity, positive energy, translation, ground clearances,
JSON round trips and invalid-layer rejection supplement the field checks.
These representative bounds do not qualify arbitrary layouts or measured boards.
