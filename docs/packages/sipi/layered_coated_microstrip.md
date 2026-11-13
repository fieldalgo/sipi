# Planar-coated surface lines above two substrates

[한국어](../../locales/ko/pages/packages/sipi/layered_coated_microstrip.md)

Three factories place surface conductors above a backing plane and two substrate
layers inside a flat dielectric film spanning the entire computational width:

- `layered_coated_microstrip`: one signal.
- `coupled_layered_coated_microstrip`: equal signals, positive left.
- `asymmetric_coupled_layered_coated_microstrip`: independent bottom widths,
  thicknesses and centered top widths, positive left and negative right.

Both substrate heights exclude copper. Copper bottoms lie at
`lower_height + upper_height`. `coating_height` starts there, includes copper and
must exceed every conductor's thickness. `air_height` starts **above the film**;
any positive value is accepted as geometry, but small air clearance needs its own
outer-domain check. The coating is planar and fills the signal gap. It does not
represent a film of uniform thickness normal to tapered metal. Only the bottom
plane is grounded; top and side boundaries are electrically insulated.

```python
from sipi import layered_coated_microstrip, CrossSectionDocument
section = layered_coated_microstrip(
    width=.5e-3, thickness=35e-6, top_width=.4e-3,
    lower_height=.3e-3, upper_height=.7e-3,
    lower_eps_r=3., upper_eps_r=5.,
    lower_tan_delta=.01, upper_tan_delta=.03,
    coating_height=80e-6, coating_eps_r=3.3, coating_tan_delta=.02,
    air_height=.01, box_width=.02)
text = CrossSectionDocument(section).dumps()
```

For a pair, `gap` separates bottom copper edges and the complete bottom span is
centered. Single-line `z0`, equal-pair even/odd summaries and unequal-pair real
`z_diff_forward` at Icommon=0 retain their existing definitions. Unequal signals
do not imply independent symmetric modes. These factories support direct Python
and geometry JSON. Named editable-template inputs, saved parameter studies,
width-goal registration and dedicated forms are separate integrations.

The representative pair adds a 0.3 mm gap. The unequal case uses 0.4/0.7 mm widths,
25/45 µm thicknesses and 0.32/0.55 mm top widths. Tests independently assign
complex material by height in scikit-fem 12.0.2, comparing complex and vacuum P1
energy matrices at a 1e-10 normalized gate. Edge/far/grade refinement from
5 µm/0.25 mm/0.2 to 2.5 µm/0.125 mm/0.1 must change capacitance and the stated
impedance diagnostic by at most 1%. Doubling box width or air height separately
at the fine mesh uses a 0.5% gate. Equal-substrate and air-valued coating limits
are each compared to the corresponding existing factory within 0.5%, preserving
total outer height in the air limit. Vacuum identities, positive energy,
reciprocity, JSON round trips and invalid-layer rejection supplement these
checks. This qualifies the recorded representative sections, not every geometry
or measured PCB. Existing factories and numerical acceptance gates are preserved.
