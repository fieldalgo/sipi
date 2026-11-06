# Two-dielectric striplines

**English** | [한국어](../../locales/ko/pages/packages/sipi/layered_stripline.md)

`layered_stripline` and `coupled_layered_stripline` place a signal or equal-width
signal pair at the interface between two dielectrics and two ground planes.
Each layer retains its own relative permittivity and loss tangent in the FEM.
No material averaging is performed by either template.

```python
from sipi import CrossSectionDocument, layered_stripline

section = layered_stripline(
    width=.5e-3, lower_height=.3e-3, upper_height=.7e-3,
    lower_eps_r=3.5, upper_eps_r=4.2, thickness=.035e-3,
    lower_tan_delta=.01, upper_tan_delta=.015, box_width=12e-3)
doc = CrossSectionDocument(section,
    mesh=dict(edge_size=2e-6, far_size=.125e-3, grade=.15))
restored = CrossSectionDocument.loads(doc.dumps())
print(restored.analyze().z0)
```

All lengths are metres. Required inputs are `width`, `lower_height`,
`upper_height`, `lower_eps_r`, `upper_eps_r`; the pair also requires `gap`.

| Position | y coordinate |
|---|---|
| Bottom ground | 0 |
| Dielectric interface and signal bottom | `lower_height` |
| Signal top | `lower_height + thickness` |
| Top ground | `lower_height + upper_height` |

Thus **upper_height includes the copper thickness**. Its dielectric is present
beside and above the copper, while the lower dielectric ends at the copper's
bottom face. Top clearance is `upper_height - thickness`, which must be positive.
This convention describes a particular lamination interface; it does not centre
the copper on that interface. Different constructions can use explicit
`CrossSection` layers, traces and local dielectric regions.

`thickness=0` and `top_width=None` default to an ideal thin rectangular strip.
`top_width` permits a symmetric signal taper when thickness is positive. For a
pair, `gap` is between bottom edges and signal centres are `±(width+gap)/2`.
Outward taper reduces the actual gap; touching/overlapping metal and ground
contact are rejected. Signal names are `signal`, or `positive`, `negative`.
Layer names are `lower`, `upper`; their optional `lower_tan_delta` and
`upper_tan_delta` default to zero. Permittivities must be at least 1, loss
nonnegative, and all inputs finite real numbers (not booleans).

Both horizontal ground planes are at zero potential. Side walls are open,
meaning zero normal displacement on the finite box. Default `box_width` is
`max(12*(lower_height+upper_height), 4*width)` for one trace and also at least
`4*(2*width+gap)` for a pair. Enlarge the width and refine the mesh separately;
a default domain is not a truncation guarantee. There is no air layer.

## JSON, tolerance studies and impedance design

Existing cross-section JSON stores the two layer materials and explicit trace
positions. No schema change is required. `sipi.impedance-study/1` adds names
`layered_stripline` (`quantity='z0'`) and `coupled_layered_stripline`
(`quantity='z_diff'`). All four sampling modes support either material/height
independently. Earlier readers reject these new names; record the engine version.

Changing one height also changes total ground-plane spacing. A fixed total
spacing constraint needs an explicit factory deriving the other height; it is
not implicit in sampling. Paired `fixed_pitch_m` instead derives
`gap = pitch - width`, preserving horizontal signal centres. Bounded inputs
validate all corner geometries; invalid unbounded normal samples remain failed
rows without resampling or partial summaries.

Use the ordinary `seek_impedance` with a factory over width (or another positive
parameter), and select `z_diff` for a pair. Both the requested and separate
refined mesh must meet the target tolerance. See [design](design.md) and
[study](study.md); successful search is not a manufacturing-yield guarantee.

## Independent symmetric-interface limit

For zero metal thickness and **equal layer heights**, the dielectric interface
is a reflection plane of the electrostatic potential. Outside the signal strips,
the normal field on that plane is zero. Both halves therefore have the same
geometric capacitance contribution regardless of their dielectric constants.
For real permittivities, the exact reduction is

`C = C0*(eps_lower + eps_upper)/2`.

The same argument with complex permittivities gives

`tan_eff = (eps_lower*tan_lower + eps_upper*tan_upper)/(eps_lower + eps_upper)`.

Cohn's independent conformal-map stripline and edge-coupled-stripline formulas
can thus use `eps_eff=(eps_lower+eps_upper)/2` for this special case. Inductance
comes from the vacuum geometry. This argument does **not** justify arithmetic
averaging for unequal heights or finite copper thickness; those geometries are
solved with explicit layer materials.

The test case uses width `.5 mm`, layer heights `.5/.5 mm`, permittivities `2/6`,
zero thickness, pair gap `.3 mm`, and box width `12 mm`, then `24 mm`.
Coarse `(edge_size,far_size,grade)` is `(8 um,.25 mm,.3)`;
fine is `(.5 um,.0625 mm,.075)`. Acceptance criteria fixed before measurement:

- Fine single/even/odd impedance errors at most 0.5% against Cohn; each decreases
  from the coarse result.
- Doubling box width changes impedance by at most 0.2%.
- Effective permittivity and weighted loss (`tan_lower=.01`, `tan_upper=.02`)
  agree within 0.3% relative.
- A 50-ohm single-line width search agrees with the independently rooted Cohn
  width within 1%; both mesh residuals are at most 0.2 ohm.

Linux CPython 3.12.14 measurements:

| Quantity | Cohn (ohm) | Fine FEM (ohm) | Relative error |
|---|---:|---:|---:|
| Single-line Z | 50.216225 | 50.185967 | 0.0603% |
| Pair even Z | 56.383287 | 56.359933 | 0.0414% |
| Pair odd Z | 43.135982 | 43.104478 | 0.0730% |

The 50-ohm width search returns `.503125 mm` versus the Cohn root
`.503967674 mm`; requested/refined residuals are `.01927/.03625 ohm`.
These measurements apply to the stated test case and environment.

The tests also check unequal-height finite tapered copper, JSON preservation of
C/C0/L/loss, explicit geometry, invalid inputs, independent material samples,
fixed pitch and retained invalid normal rows. Those checks establish input and
composition behavior; the symmetric ideal limit is not blanket validation of
arbitrary material stacks, finite metal or measured boards.

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python -m pytest -q -s tests/sipi/test_layered_stripline.py
```
