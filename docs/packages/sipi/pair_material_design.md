# Geometry and material pair targets

`seek_pair_impedances` can adjust two positive bounded parameters shared by
`factory(p0,p1)` and `material_factory(p0,p1)`. The first returns a cross-section;
the second returns a region-name to dielectric-model mapping. A fixed nonnegative
`frequency` is required, and `materials` cannot be supplied simultaneously.
Both factories must describe the same deterministic input for each parameter
tuple. Controls are checked before either callback. The existing symmetric
pair, real capacitance and vacuum-inductance restrictions remain unchanged.

The example uses width in metres and dimensionless Debye strength. It starts
at the known reference dimensions, so two attempts suffice. To exercise the
actual search, use `initial=(.35e-3,5.5)` and `max_evaluations=64`.

```python
import json
from sipi import seek_pair_impedances
from sipi.templates import coupled_stripline
from sipi.dielectric import DebyeDielectric

def section(width, strength):
    return coupled_stripline(width=width, gap=.1e-3, plane_spacing=1e-3,
        eps_r=1., box_width=8e-3)

def material(width, strength):
    return {'dielectric': DebyeDielectric(2., [strength], [1e9])}

result = seek_pair_impedances(section, ((.3e-3,.7e-3),(2.,6.)),
    (69.86609070536932,30.721416289368904), tolerances=(.5,.2),
    frequency=1e9, material_factory=material, initial=(.5e-3,4.),
    max_evaluations=2, mesh=dict(edge_size=1e-6,far_size=.125e-3,grade=.1))
assert len(result.history) == 2
assert all(abs(r)<=t for r,t in zip(result.refined_residuals,result.tolerances))
assert result.history[0].material_evaluation_json == result.history[1].material_evaluation_json
assert json.loads(result.material_evaluation_json)['frequency_hz'] == 1e9
```

## Snapshots, budgets and failures

Each uncached parameter attempt includes geometry, material encoding, field
extraction and diagnostics, counting once even when one step fails. Jacobian
probes count; repeated parameter tuples served by the objective cache do not.
Mesh reuse during a new parameter evaluation still counts as one attempt.
One attempt remains reserved for refinement.
Each completed `PairImpedanceEvaluation` retains `material_evaluation_json`;
its dictionary contains `material_evaluation` when a mapping exists. Ordinary
geometry-only rows retain their previous dictionary shape and four-argument
construction. Fixed mappings are also captured per row.

The selected geometry and encoded model are frozen before refinement. Neither
factory is called again for that check. Caller mutations to the original
mapping do not change captured inputs. The result retains the selected model,
and each history row must be replayed with its own geometry and material pair.

`PairImpedanceGoalError` preserves completed rows, actual attempts, stage,
cause and available current geometry/model. A material-construction failure
has no valid current model; it does not borrow the previous row's mapping.
An encoded model that fails field validation remains available in the error.
Cached candidates from an unsuccessful optimizer also retain their input and
model. Factory functions are not serialized. Saved `pair-impedance-design/1`
continues to support fixed materials only; this API changes no input schema.

[Saved version 2 goals](pair_material_document.md) use explicit named numeric
material bindings instead of serializing the callback.

## Repeated geometry within one search

Material evaluations with the same complete cross-section document reuse one
mesh and its vacuum capacitance inside that search. Geometry, boundary and
signal/material names and order, default materials and explicit mesh settings
all participate in the key. A changed document discards the entry before a new
mesh is built. Refinement uses its separate finer mesh. There is no global or
cross-search cache, and no retained field vectors.

Every uncached parameter evaluation still validates and evaluates its current
material, computes its material-dependent capacitance/loss and performs the
same pair diagnostics. Factory calls, attempted-evaluation budgets and error
context are unchanged. The independent objective cache continues to handle
repeated parameter tuples. This can reduce repeated meshing in fixed-geometry
material searches without claiming unique parameter recovery or a general
elapsed-time improvement.

The reuse tests cover a real diagonal-tensor search, a second independent
search, actual refinement mesh failure, changed-material field failure,
invalid material on reused geometry and unchanged attempted-evaluation limits.
These control/compatibility checks complement the physical criteria below.

## Independent acceptance and scope

The test uses the Cohn thin coupled-stripline expressions, gap .1 mm, plane
spacing 1 mm and homogeneous Debye permittivity `2+strength/(1+j)` at 1 GHz.
Width .5 mm and strength 4 give the two targets above at real permittivity 4.
Starting at (.35 mm,5.5), recovered width and strength must each be within 2%
of the reference. Both requested mesh `(1um,.125mm,.1)` and its half refinement
must meet absolute differential/common tolerances (.5,.2) ohm. The selected
geometry/model must also meet them on box16 mm and against the independent
Cohn expressions. Every row's encoded model is checked, and first/selected
field replays agree at relative 1e-10. Controls separately check failures,
actual budgets, model identity and refinement without callback reuse.

These are explicit fixture gates, not measured-material calibration or a
general accuracy estimate. A single-frequency two-target search does not
identify a complete dispersion model, prove uniqueness, establish broadband
performance or support arbitrary lossy/modal optimization. The caller must
choose physically meaningful parameters and establish identifiability.

[Pair design](pair_design.md) · [Saved goals](pair_design_document.md) ·
[한국어](../../locales/ko/pages/packages/sipi/pair_material_design.md)
