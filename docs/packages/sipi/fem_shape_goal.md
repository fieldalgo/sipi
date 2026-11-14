# Bounded goals with checked FEM currents

`seek_fem_shape_line_quantity` accepts a callable that returns an explicit
`FEMShapeTransmissionLineDocument`. It searches one positive bounded parameter
for Re Zc (`impedance_real`), Re gamma (`attenuation`), Re Zdd at Ic=0
(`differential_forward_impedance_real`) or Re Zcc at Id=0
(`common_forward_impedance_real`). A scalar target needs one signal; a paired
target needs two ordered signals. Paired launches retain asymmetric coupling
and are not asserted to be independent propagation modes.

```python
from sipi import CrossSectionDocument, FEMShapeTransmissionLineDocument
from sipi import stripline, seek_fem_shape_line_quantity

metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness=dict(kind='smooth'))
def line(width):
    section = stripline(width=width, plane_spacing=.002, eps_r=4.,
                        thickness=.00005, box_width=.008)
    return FEMShapeTransmissionLineDocument(
        CrossSectionDocument(section, mesh=dict(edge_size=5e-6,
                             far_size=.0002, grade=.1)),
        [2e9], materials={}, conductors={'signal': metal}, reference=metal,
        ground_thickness=35e-6, length=0.)

# design = seek_fem_shape_line_quantity(line, [.00039, .00041], 70.35,
#     quantity='impedance_real', tolerance=.2, max_evaluations=12)
assert line(.0004).to_dict()['length_m'] == 0.
```

The factory must retain one positive frequency, the ordered signal names and
zero length. Geometry or material parameters may vary. This callable interface
does not serialize the factory or infer a manufacturing distribution. Both
endpoints must calculate successfully. An endpoint inside the tolerance is
eligible; otherwise their residual signs must bracket the target. Bisection
is not proof of continuity, monotonicity, uniqueness or global optimality.

Reserve one complete attempt for the frozen selected input. Resolve its mesh
options and halve `edge_size`, `far_size` and `grade`, keeping `min_angle` and
all physical inputs. Refinement does not call the factory again. Both results
must satisfy the same absolute target tolerance. This explicit FEM API also
requires `abs(refined_value-value)/refined_value <= 0.005`; two zero attenuation
values count as zero change, while a nonzero change to zero is rejected.
This additional check does not alter the original `seek_line_quantity` API.
It is not an outer-domain or physical accuracy bound.

Budgets include every factory, validation, extraction and diagnostic attempt,
including failed attempts. Internal capacitance/velocity solves are not counted
separately, so the budget is not a time or memory limit. There are no retries,
clipping, relaxed derivative gates or fallback to another current method.
KeyboardInterrupt/SystemExit propagate.

`FEMShapeLineQuantityDesign` retains the selected and refined line results,
input snapshots, all successful search evaluations and both complete current
records. `FEMShapeLineQuantityGoalError` retains attempts, successful history,
failed parameter/input, phase and original exception chain. Typed line errors
keep complete or partial field observations in `cause_details`. A diagnostic or
refinement acceptance error keeps its completed current in `current_solver`.
A field that was never computed is not synthesized. Error dictionaries are
JSON-compatible, with the saved line's explicit failed-observation markers.

Validation includes actual scalar and differential width goals, an independent
matrix/scalar square-root characteristic calculation, frozen-input refinement,
budgets, failure retention and original goal regressions. Separate actual-field checks also solve a dielectric-loss target of 1.0 Np/m
(absolute tolerance 0.01 Np/m, tan_delta in 0.01..0.03) and a common-launch
target of 45.8 ohm (absolute tolerance 0.1 ohm, width in 0.39..0.41 mm), at
2 GHz. Each uses four actual attempts, including frozen-input refinement, and
independent characteristic square roots. Attenuation is 0.991319/0.991450 Np/m
at tan_delta 0.02; common impedance is 45.789133/45.821079 ohm at width 0.4 mm.
Other transport-only checks still reuse observed fields explicitly and are not
additional physical inverse-recovery experiments. The current implementation does
not certify outer-domain sufficiency, continuous-band behavior or empirical
accuracy. Existing criteria and saved documents remain unchanged. Full platform
regression and a saved factory wrapper are separate work.

[한국어](../../locales/ko/pages/packages/sipi/fem_shape_goal.md)
