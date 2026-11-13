# Normal-thickness coatings above two substrate layers

**English** | [한국어](../../locales/ko/pages/packages/sipi/layered_conformal_microstrip.md)

`layered_conformal_coated_microstrip`, `coupled_layered_conformal_coated_microstrip`
and `asymmetric_coupled_layered_conformal_coated_microstrip` split the substrate
under an existing straight-sided conformal coating into two explicit materials.
Both substrate heights exclude copper. The lower plane is ground; the top and
sides are open. Single, equal-pair and unequal-pair copper geometry retain their
existing definitions, including bottom-edge gap and independent unequal widths,
thicknesses and narrowing top widths.

`coating_thickness` is normal to the substrate, trace tops and sloping sides.
The coating is one polygon region, with mitered corners and united touching
envelopes. Air height starts above the highest coated trace. The film is kept
when the substrate is split; a planar coating layer cannot replace this region.
Overhangs, clipped films, unresolved dimensions and enclosed air pockets are
rejected. This is not a rounded-corner, meniscus or measured deposition model.

```python
from sipi import layered_conformal_coated_microstrip, CrossSectionDocument
section = layered_conformal_coated_microstrip(
    width=0.5e-3, thickness=35e-6, top_width=0.4e-3,
    lower_height=0.3e-3, upper_height=0.7e-3,
    lower_eps_r=3., upper_eps_r=5.,
    lower_tan_delta=0.01, upper_tan_delta=0.03,
    coating_thickness=20e-6, coating_eps_r=3.3, coating_tan_delta=0.02,
    air_height=10e-3, box_width=20e-3)
text = CrossSectionDocument(section).dumps()
```

Direct Python, geometry JSON, named templates, parameter studies and width
goals share the same section contract. Dedicated forms remain a separate step. Single-line `z0`, equal-pair
even/odd diagnostics and unequal-pair `z_diff_forward` keep their meanings;
unequal signals do not imply independent symmetric modes.

The representative field checks use 0.3/0.7 mm substrates, relative permittivity
3/5, loss tangent 0.01/0.03 and a 20 µm film with relative permittivity 3.3 and
loss tangent 0.02. Single/equal traces use 0.5 mm bottom width, 0.4 mm top width
and 35 µm thickness. The unequal pair uses 0.4/0.7 mm bottom widths,
0.32/0.55 mm top widths and 25/45 µm thicknesses. Pair gap is 0.3 mm.

An independent signed-distance material mask and scikit-fem P1 complex/vacuum
assembly require normalized error at most 1e-10. Edge 5 µm, far 0.25 mm and
grade 0.2 are halved for the mesh gate (C and the applicable impedance within
1%). Doubling box width or upper air separately at that refined mesh must
change them by at most 0.5%. Uniform-substrate, unit-permittivity-film and
zero-metal planar-film limits each require agreement within 0.5%. Normal
surface distance, vacuum identities, reciprocity, positive energy and JSON
round trips supplement these selected-geometry checks. They do not qualify
arbitrary boards or measured accuracy.


## Saved studies and width goals

Single/equal/unequal objectives are `z0`, `z_diff` and `z_diff_forward`;
equal pairs also accept explicit `z_diff_forward`. Fixed-pitch sampling keeps
signal centers 0.8 mm apart for the equal example and 0.85 mm apart for the
unequal example. The polygon film is rebuilt with its original 20 µm normal
thickness. Negative normal-film samples remain failed rows without meshing.
Coating-permittivity sweeps preserve geometry and replay through common saved
execution; deterministic PCG64 samples are checked independently.

Representative width goals are 90/105/105 Ω within 0.4–0.7 mm width or
0.32–0.8 mm unequal left width. A 0.05 Ω search gate precedes a separate
refinement that halves edge, far and grade; requested and refined residuals
must both stay within 0.5 Ω. Direct and saved histories/refined results agree
exactly. This selected-geometry check is separate from nominal outer-domain
convergence and does not broaden the qualified geometry range.
