# Grounded coplanar copper above two substrate layers

[한국어](../../locales/ko/pages/packages/sipi/layered_grounded_coplanar.md)

Three factories retain finite side grounds and a bottom reference plane while
specifying two separate substrate layers beneath all copper:

- `layered_grounded_coplanar`: one signal; `gap` is its bottom-edge ground gap.
- `coupled_layered_grounded_coplanar`: equal signals; `gap` separates them and
  `ground_gap` separates each outer signal edge from its adjacent ground.
- `asymmetric_coupled_layered_grounded_coplanar`: independent left/right signal
  widths, thicknesses and optional centred top widths. Ground thickness is explicit.

Both `lower_height` and `upper_height` exclude copper. Every conductor bottom is
at their sum. Each layer has separate permittivity and loss tangent. The lower
plane and both finite side grounds share reference potential; the upper and side
box boundaries are open. Air height includes copper. Grounds are rectangular.
The single and equal-pair factories share copper thickness with their grounds;
the unequal factory never infers ground thickness from a signal. Signal taper
widths do not change the stated bottom-edge gap definitions. There is no central
ground between signals. The complete signal bottom span stays centred.

```python
from sipi import layered_grounded_coplanar, CrossSectionDocument
section = layered_grounded_coplanar(
    width=.5e-3, gap=.2e-3, ground_width=1e-3,
    thickness=35e-6, top_width=.4e-3,
    lower_height=.3e-3, upper_height=.7e-3,
    lower_eps_r=3., upper_eps_r=5.,
    lower_tan_delta=.01, upper_tan_delta=.03,
    box_width=.02, air_height=.01,
)
document = CrossSectionDocument(section,
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
line = document.analyze()
```

These are geometry factories; save their output with `CrossSectionDocument`.
Named study/design registration and dedicated forms are separate integration
steps. Scalar `z0` applies to the single line, even/odd summaries to the equal
pair. The unequal pair uses the real lossless `z_diff_forward` launch at Icommon=0;
it does not assume independent symmetric modes. Copper loss, roughness,
frequency-dependent materials and 3D ground connectivity are not inferred.

The representative tests use the dimensions above. The equal pair adds a 0.3 mm
signal gap and a 0.2 mm ground gap. The unequal pair uses 0.4/0.7 mm widths,
25/45 µm thicknesses, 0.32/0.55 mm top widths and 35 µm grounds. Independent
scikit-fem 12.0.2 P1 energy uses separately assigned height-based complex material
and vacuum coefficients on the same geometric mesh. The preregistered normalized
matrix gate is 1e-10. Separate mesh change in C and the appropriate impedance is
bounded by 1%; doubling box width or air height individually is bounded by 0.5%.
The equal-material comparison with a single substrate is bounded by 0.5%.
These checks qualify those geometries, not all ground widths or measured boards.

Run `PYTHONPATH=src OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q tests/sipi/test_layered_grounded_coplanar.py`
in the qualified reference environment. Preserve failed trials and use separate
mesh/outer checks when choosing a different physical range.
