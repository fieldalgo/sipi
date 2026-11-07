# Goals using lossy scalar-line quantities

[Saved goal JSON](line_goal_document.md) reuses existing geometry/material study inputs.

[한국어](../../locales/ko/pages/packages/sipi/line_goal.md) · [Saved line inputs](line_model.md) · [Propagation](propagation.md)

`sipi.line_goal.seek_line_quantity` varies one positive parameter of a caller's
`TransmissionLineDocument` factory. It uses the extracted conductor and
dielectric R/L/G/C, including the selected surface laws, to target either:

| Quantity | Definition | Unit |
|---|---|---|
| `impedance_real` | real part of forward traveling-wave Zc | ohm |
| `attenuation` | real part of forward propagation constant gamma | Np/m |

Re(Zc) is neither its magnitude nor a terminal load. Attenuation is amplitude
decay per length, not finite-line insertion loss, which also depends on mismatch.
The existing `seek_impedance` retains its real quasi-static definition. A real
Zc target does not constrain its imaginary part; inspect the retained complex
propagation result. Frequency is one fixed positive sample, not an entire band.

```python
from sipi import CrossSectionDocument, stripline
from sipi.line_model import TransmissionLineDocument
from sipi.line_goal import seek_line_quantity

def line(width=.5e-3, loss=.02, metal=True):
    section = stripline(width=width, plane_spacing=1e-3,
        thickness=50e-6 if metal else 0., eps_r=4., tan_delta=loss, box_width=4e-3)
    conductor = (dict(kind='surface', conductivity=58e6, relative_permeability=1.,
        roughness_rms=.5e-6, ground_thickness=35e-6) if metal else dict(kind='perfect'))
    cross = CrossSectionDocument(section,
        mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05))
    return TransmissionLineDocument(cross, [1e9], materials={}, conductor=conductor,
                                    length=0., z_ref=75.)

width_goal = seek_line_quantity(lambda width: line(width=width), [.3e-3, .8e-3], 50.,
    quantity='impedance_real', tolerance=.5, max_evaluations=24)
assert abs(width_goal.residual) <= .5 and abs(width_goal.refined_residual) <= .5
assert width_goal.unit == 'ohm'
complex_z = width_goal.result.propagation().z_characteristic[0, 0]
assert width_goal.value == complex_z.real
saved_selected_line = width_goal.document.dumps()
```

The factory may change geometry or material parameters. Every document must
have exactly one signal, an unchanged signal name, one unchanged positive
frequency and `length_m=0`. Bounds are positive in the factory parameter's units.
Pairs and general multiconductor modal targets are rejected: geometric symmetry
alone does not establish exact RLGC symmetry or mode identity across geometry.
The API does not project away coupling.

Both endpoints must be valid. An endpoint within tolerance can be selected;
otherwise residual signs must bracket zero. Bisection does not prove continuity,
monotonicity, uniqueness or a global optimum. The impedance target is positive;
the attenuation target may be zero. Tolerance is explicitly positive in the
quantity's unit. One evaluation is reserved to halve edge size, far size and
grade at the selected input, keeping minimum angle and all physical settings.
Refinement reuses the frozen input without recalling the factory. Both values
must meet the same target tolerance. Outer-domain convergence and model validity
remain separate responsibilities.

```python
import json

loss_goal = seek_line_quantity(lambda loss: line(loss=loss, metal=False), [.01, .1], 1.,
    quantity='attenuation', tolerance=.001, max_evaluations=24)
assert max(abs(loss_goal.residual), abs(loss_goal.refined_residual)) <= .001
assert loss_goal.unit == 'Np/m'
report = loss_goal.to_dict()
assert report['evaluations'] == len(loss_goal.history) <= 24
assert report['history'][-1]['stage'] == 'refinement'
json.dumps(report, allow_nan=False)
```

Results retain requested/refined full line results, replayable documents, values,
residuals, mesh change and every completed evaluation's exact input. Document
accessors return detached snapshots. `to_dict()` contains finite scalar results
and inputs; it neither serializes the factory nor creates a saved-goal schema.
Keep the original factory and controls to repeat the search. A selected material
parameter is an algorithm result, not a measured material fit.

`max_evaluations` is an integer from 3 to 10000. Failed factory, normalization,
extraction and diagnostic attempts all count. One attempt can contain multiple
field solves; this budget does not limit memory or elapsed time. Invalid controls
fail before invoking the factory. Later failures raise `LineQuantityGoalError`
with completed `history`, `attempts`, `stage`, `failed_parameter`, `cause_type`
and available `input_json`, chaining the original exception. Failed rows are not
fabricated as valid results, and a failed refinement cannot return a design.

Validation requires lossy homogeneous Cohn width agreement within 1% and
requested/refined target errors at most 0.1 ohm. For a homogeneous PEC line,
gamma = j*omega*sqrt(mu*epsilon)*sqrt(1-j*tan_delta); attenuation searches compare
the tangent with its closed-form root within 0.5% and both residuals within
0.001 Np/m. A finite-metal width case checks requested/refined/doubled-box target
errors within 0.5 ohm and outer change below 0.5%. Independent scikit-rf Zc/gamma
comparisons require relative error below 1e-10 using identical extracted RLGC;
they verify propagation, not independent field accuracy. Lossless limits,
failure accounting and snapshots are also tested. These checks do not establish
measured manufacturing accuracy, application or Windows acceptance.

```sh
python -m pytest -q tests/sipi/test_line_goal.py tests/sipi/test_line_model.py tests/sipi/test_propagation.py tests/sipi/test_design_documents.py
```
