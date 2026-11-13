# Two-substrate unbacked coplanar sections

[한국어](../../locales/ko/pages/packages/sipi/layered_unbacked_coplanar.md)

Three geometry factories place finite side grounds beside signals above two
independent substrate layers, with air below the finite substrate and no backing
plane:

- `layered_unbacked_coplanar`: one signal; `gap` separates its bottom edges from
  the rectangular grounds. Signal and grounds share copper thickness.
- `coupled_layered_unbacked_coplanar`: equal signals; `gap` separates signals,
  while `ground_gap` separates their outside edges from the grounds.
- `asymmetric_coupled_layered_unbacked_coplanar`: independent signal bottom
  widths, thicknesses and centred top widths; explicit rectangular ground
  thickness. Positive signal is left, negative is right.

Both substrate heights exclude copper. Lower air translates both layers and all
copper together, so every copper bottom is at
`lower_air_height + lower_height + upper_height`. Its default is ten times the
**sum** of substrate heights. Upper air starts at the substrate surface and
includes copper. All outer boundaries are insulated in the electric problem;
only the two finite grounds fix the reference potential. Increasing air is an
independent domain check, not a change to the physical substrate thickness.
There is no central ground, backing plane or inferred 3D ground connection.

```python
from sipi import layered_unbacked_coplanar, CrossSectionDocument
section = layered_unbacked_coplanar(
    width=.5e-3, gap=.2e-3, ground_width=1e-3,
    lower_height=.3e-3, upper_height=.7e-3,
    lower_eps_r=3., upper_eps_r=5.,
    lower_tan_delta=.01, upper_tan_delta=.03,
    thickness=35e-6, top_width=.4e-3,
    lower_air_height=.01, air_height=.01, box_width=.02)
text = CrossSectionDocument(section).dumps()
```

Single-line `z0`, equal-pair even/odd summaries and the unequal pair's real
lossless `z_diff_forward` launch at Icommon=0 retain their existing meanings.
Unequal signals do not imply independent symmetric modes. These API factories
can be saved as cross sections; named study/goal registration and editable forms
are separate integration steps.

The representative pair adds a 0.3 mm signal gap and a 0.2 mm outside ground gap.
The unequal case uses 0.4/0.7 mm signal widths, 25/45 µm thicknesses,
0.32/0.55 mm top widths and 35 µm grounds. Tests independently assign complex
material by height in a scikit-fem 12.0.2 P1 energy solve, including lower and upper
air, with a 1e-10 normalized matrix gate. Mesh change is bounded by 1%; doubling
box width, upper air or lower air individually is bounded by 0.5% for these
geometries. Equal-material comparison against the original unbacked factory is
bounded by 0.5%. Vacuum identities, reciprocity, positive energy and translation
checks supplement these gates. They do not qualify every geometry or measured
board. Existing templates, tolerances and frozen input snapshots stay unchanged.
