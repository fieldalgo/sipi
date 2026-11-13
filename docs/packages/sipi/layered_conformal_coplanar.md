# Normal-thickness coated coplanar sections above two substrates

**English** | [한국어](../../locales/ko/pages/packages/sipi/layered_conformal_coplanar.md)

`layered_conformal_coated_grounded_coplanar` and
`layered_conformal_coated_unbacked_coplanar`, with `coupled_` and
`asymmetric_coupled_` variants, combine two substrate materials, finite side
grounds and a straight-sided normal-thickness coating. Both substrate heights
exclude copper. `coating_thickness` is normal to the substrate and copper
surfaces; offset edges meet at miters. Air height starts above the highest
coated conductor. All signal and ground envelopes remain in the polygon film.
Overhangs, implicit clipping, unresolved films and enclosed air pockets are
rejected; no rounded corner, meniscus or measured deposition model is implied.

Grounded variants retain a bottom ground plane and open top/sides. Unbacked
variants have open outer boundaries and explicit lower air, which translates
both substrate layers, all copper and the coating polygon. Its default is ten
times the sum of the substrate heights. Only the two finite side grounds set
the reference there. Their common potential does not model a 3D connection.

Single `gap` separates signal and ground bottom edges. Pair `gap` separates
signals; `ground_gap` measures the outside signal-to-ground clearances.
Unequal signals have independent bottom/top widths and thicknesses; rectangular
grounds retain explicit width and thickness. Ground width, box width and both
air domains are separate parameters requiring separate sensitivity checks.

```python
from sipi import layered_conformal_coated_unbacked_coplanar, CrossSectionDocument
section = layered_conformal_coated_unbacked_coplanar(
    width=0.5e-3, gap=0.2e-3, ground_width=1e-3,
    thickness=35e-6, top_width=0.4e-3,
    lower_height=0.3e-3, upper_height=0.7e-3,
    lower_eps_r=3., upper_eps_r=5.,
    lower_tan_delta=0.01, upper_tan_delta=0.03,
    coating_thickness=20e-6, coating_eps_r=3.3, coating_tan_delta=0.02,
    air_height=10e-3, lower_air_height=10e-3, box_width=20e-3)
text = CrossSectionDocument(section).dumps()
```

Direct Python and geometry JSON are supported; named studies/goals and forms
are separate integration steps. Single `z0`, equal-pair even/odd diagnostics
and unequal-pair `z_diff_forward` retain their existing meanings.

Representative checks use the example stack and film. Equal signals have
0.5/0.4 mm bottom/top width and 35 µm thickness; unequal signals use
0.4/0.7 mm bottom widths, 0.32/0.55 mm top widths and 25/45 µm thicknesses.
Pair gap is 0.3 mm; ground clearance is 0.2 mm, ground width 1 mm and ground
thickness 35 µm. Independent straight-side normal-offset material masks and
scikit-fem P1 complex/vacuum assembly must agree within normalized 1e-10.
Halving edge 5 µm, far 0.25 mm and grade 0.2 must change C and the applicable
impedance by at most 1%. At the refined mesh, doubling box width, upper air
or unbacked lower air separately requires at most 0.5% change. Uniform
substrate, unit-permittivity-film and zero-metal planar-film limits each
require 0.5% agreement. Normal distance, translation, finite-ground gaps,
vacuum identities, positive energy, reciprocity and JSON are checked too.
These selected bounds do not qualify arbitrary boards or measured accuracy.
