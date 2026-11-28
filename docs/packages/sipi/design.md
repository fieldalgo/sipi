# Cross-section templates, documents and impedance design

[Normal-thickness coating](conformal_coating.md) supports single/pair sections, saved studies and goals.

**English** | [한국어](https://github.com/fieldalgo/sipi/blob/main/docs/locales/ko/pages/packages/sipi/design.md)

[SIPI overview](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/overview.md)

These APIs use the ordinary quasi-static engine; they add input reproducibility
and bounded search, not additional physics. All lengths are metres, impedances
and residual tolerances are ohms. See the overview for physical limitations.

## Templates

Each function returns a `CrossSection`. Required arguments are keyword-only.

| Function | Required inputs | Geometry |
|---|---|---|
| `microstrip` | `width`, `substrate_height`, `eps_r` | Surface signal above a bottom ground plane |
| `stripline` | `width`, `plane_spacing`, `eps_r` | Signal centred between two ground planes in one dielectric |
| `coupled_microstrip` | `width`, `gap`, `substrate_height`, `eps_r` | Two equal-width surface signals; `gap` is edge to edge |
| `grounded_coplanar` | `width`, `gap`, `ground_width`, `substrate_height`, `eps_r` | Surface signal between finite-width grounds, with a bottom ground plane |
| `coupled_grounded_coplanar` | `width`, `gap`, `ground_gap`, `ground_width`, `substrate_height`, `eps_r` | Equal-width signal pair between two finite grounds; separate inter-signal and outer-ground gaps |

All accept `thickness=0`, `tan_delta=0` and `box_width=None`. Surface templates
also accept `air_height=None`, defaulting to `10 * substrate_height + thickness`.
Stripline plane spacing includes the conductor thickness. Every side wall is
open (zero normal displacement); the stripline top is grounded and other tops
are open.

**Default boxes changed on 2026-11-28.** `box_width=None`, `air_height=None` and
`lower_air_height=None` follow a box rule, `sipi.templates.box_rule('v1' | 'v2')`.
New calls use **v2**:

| Rule | Surface templates with a ground plane (microstrip, coupled, coated, conformal, grounded coplanar, layered and asymmetric variants) | Unbacked coplanar templates | Stripline families |
|---|---|---|---|
| `v1` (before 2026-11-28) | width `max(20*h, 4*w)` (coupled `4*(2*w+gap)`, coplanar `w+2*gap+2*ground_width+4*h` and pair/asymmetric forms also in the max); air `10*h + t` | as grounded coplanar, plus lower air `10*h` | `max(12*b, 4*w)` and pair/offset forms |
| `v2` (default) | every v1 width term ×4 (microstrip `max(80*h, 16*w)`); air `4*(10*h + t)` | width, air and lower air ×2 | unchanged |

Use `with sipi.templates.box_rule('v1'): ...` to reproduce earlier boxes;
`sipi.templates.current_box_rule()` reports the active rule. Explicit
`box_width`, `air_height` and `lower_air_height` are used as given under both
rules. The rule is chosen so that open-wall truncation stays within about 0.1 %
in `eps_eff`, Z0 and the common mode on the studied sections (table below);
it costs about 5–40 % more mesh nodes. Saved documents keep their boxes: every
document that rebuilds a template from its name and parameters (template
section /1, impedance, pair, sampled, corner and line-quantity designs and
studies, panel forward-pair documents, FEM-shape, yield) and the workbench
forms still build v1 boxes, so their results are unchanged. Only
[`sipi.template-section/2`](template_document.md#version-2-v2-boxes) records v2
boxes. New design and study versions with v2 boxes are follow-up work.

**Fixed mesh sizes on v2 boxes.** With the default mesh rule (`far_size` =
max(width, height) / 24) the far field scales with the box, so v2 adds few
points. A caller that passes an absolute `far_size` and `grade` meshes up to
16 times the far-field area at that size, and refinement studies that were
near the 300,000-point mesher limit can pass it. Measured nodes (v1 → v2;
one thread, openphysics 60322040):

| Section | Default mesh | Default halved | Halved twice | `edge_size` 2.5 µm, `far_size` 0.1 mm, `grade` 0.05 |
|---|---:|---:|---:|---:|
| microstrip, w 0.3, h 0.2 mm, 35 µm | 4,099 → 5,500 | 15,441 → 17,979 | 60,627 → 67,871 | 15,891 → 40,204 |
| coupled microstrip, w 0.5, gap 0.3, h 1 mm, 35 µm | 10,573 → 21,200 | 32,601 → 44,055 | 120,874 → 136,703 | 75,572 → over the limit |
| grounded coplanar, w 0.3, gap 0.15, h 0.2 mm, 35 µm | 19,206 → 21,073 | 73,213 → 77,191 | 287,503 → over the limit | 41,846 → 66,946 |
| unbacked coplanar, same dimensions | 20,501 → 21,598 | 78,429 → 81,813 | over the limit under both | 50,321 → 61,420 |

Raise `far_size` in proportion to the box, pass `box_width` and `air_height`,
or build the template under `box_rule('v1')`. When `far_size` is below half of
the default rule's value, the point-limit error names this first.

These defaults are starting domains, not truncation guarantees. Enlarge the box
and air independently to check truncation; also enlarge coplanar ground width.

Measured microstrip truncation (zero thickness, `h = 1 mm`, open walls; mesh
`edge_size = min(w, h) / 100`, `grade = 0.15`, `far_size = 2 h`; Linux,
Python 3.13, NumPy 2.5.5, SciPy 1.18.1). Values are relative to a
160h-wide box with 80h of air. Both shrink four- to fivefold per doubling,
so that reference may itself be up to about 0.02 % high in `eps_eff`.

| Box (width × air) | `w/h` 0.25 | `w/h` 1 | `w/h` 4 |
|---|---|---|---|
| v1 template default, 20h × 10h | `eps_eff` +0.40/+0.45 %, Z0 +0.28/+0.26 % | +0.65/+0.73 %, +0.47/+0.43 % | +1.40/+1.60 %, +1.02/+0.92 % |
| 40h × 20h (validation box) | +0.10/+0.11 %, +0.07/+0.06 % | +0.16/+0.18 %, +0.11/+0.10 % | +0.34/+0.38 %, +0.23/+0.21 % |
| 80h × 40h | +0.02/+0.03 %, +0.01/+0.01 % | +0.03/+0.04 %, +0.03/+0.02 % | +0.07/+0.08 %, +0.05/+0.05 % |

Each cell gives `εr` 4.3/9.8. Open walls make both `eps_eff` and Z0 high,
growing with `w/h`. An independent comparison found 0.1–0.3 % in `eps_eff`
for the 40h × 20h box, consistent with this table. The template default box
v1 row is the old template default; for microstrip the v2 default is the
80h × 40h row. The v1 box is a starting domain; with v1, pass `box_width` and
`air_height` (for example 80h and 40h) when truncation must stay below 0.1 %,
or compare open and grounded walls. Over nine template families, two
thicknesses and three `w/h` (h = 0.2 mm), v2 boxes left at most +0.10 % in
`eps_eff` and +0.12 % in the even-mode `eps_eff` of coupled microstrip
against an extrapolated unbounded box; the differential mode moved by less
than 0.03 %. Default panel controls were rechecked on v2 boxes: from 64 to
128 panels per edge C0 changed by at most 1.5e-6 and the current Gram parts by
at most 4.0e-3, as with v1 boxes.
Zero thickness is allowed, but width, gap and dielectric dimensions must be
positive. Invalid or overlapping geometry raises before meshing. Names are
`signal`, or the ordered pair `positive`, `negative`; coplanar reference traces
are `ground_left`, `ground_right`. Layers are `substrate`, `air`, or `dielectric`.

These templates additionally accept `top_width`; `sipi.templates.coated_microstrip`
adds a planar coating. See [manufacturing geometry and JSON v2](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/manufacturing_sections.md)
for the exact geometry, clearance and schema changes. In v2 every trace adds required
`top_width`; the table below lists the unchanged v1 fields.

See [polygons, local masks and JSON v3](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/polygon_sections.md) for additional sections:
`offset_stripline`, `coupled_stripline`, `broadside_stripline` and `with_surface_mask`
are available from `sipi.templates`.

See [coupled coplanar geometry and validation](coupled_coplanar.md) for the fifth
table entry's dimensions, default box, independent reference and convergence limits.

[Two-dielectric striplines](layered_stripline.md) add `layered_stripline` and
`coupled_layered_stripline`, with independent lower/upper material properties.
Their interface-to-plane heights include the copper in the upper layer.

## Input document

```python
from sipi import CrossSectionDocument, microstrip

doc = CrossSectionDocument(microstrip(
    width=1e-3, substrate_height=1e-3, eps_r=4.3, thickness=35e-6),
    mesh={"edge_size": 3.5e-6, "far_size": 0.5e-3, "grade": 0.15})
text = doc.dumps()
restored = CrossSectionDocument.loads(text)
line = restored.analyze()
```

The JSON root has exactly these required fields:

| Field | Contract |
|---|---|
| `schema` | `"sipi.cross-section/1"` or `"sipi.cross-section/2"`; [v3](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/polygon_sections.md) |
| `length_unit` | `"m"`; no implicit conversion |
| `layers` | Nonempty ordered array of `{name, thickness, eps_r, tan_delta}` |
| `traces` | Nonempty ordered array of `{name, x, width, y, thickness, ground}` |
| `box` | `{width, bottom, top, sides}`; boundaries are `"open"` or `"ground"` |
| `mesh` | Object with optional `edge_size`, `far_size`, `grade`, `min_angle` |

Names are nonblank strings and unique within each array. Numbers must be finite
real values, never booleans or numeric strings; `ground` must be a boolean.
Unknown or missing fields, unknown versions, duplicate JSON keys and nonfinite
numbers are rejected. Geometry follows the `CrossSection` contract. Mesh lengths
are positive with resolved `edge_size <= far_size`, `grade >= 0` and
`0 < min_angle < 34` degrees (default 28). Null mesh options are rejected; omit
an option to use its default. `section.mesh_settings(**options)` resolves and
validates all mesh defaults without generating a mesh.

`from_dict` and `to_dict` operate on plain objects. The document snapshots inputs;
`section`, `mesh_options` and `to_dict()` return fresh values. `dumps()` returns
deterministic JSON and never writes a file. Results are not saved in this input
schema. Omitted mesh settings use the installed engine's defaults; to archive
explicit settings, construct with `mesh=section.mesh_settings()` and record the
engine version alongside the document. Defaults and numerical implementations
can change between versions.

## Target impedance

### Save a design request

`ImpedanceDesignDocument` saves the goal and search settings, separately from the
resulting cross-section input. It accepts named templates only, never code or a
serialized Python callable. Loading validates parameters and endpoint geometry
but does not mesh or solve.

```python
from sipi import ImpedanceDesignDocument

plan = ImpedanceDesignDocument('stripline',
    dict(width=.5e-3, plane_spacing=1e-3, eps_r=4),
    variable='width', bounds=[.3e-3, .8e-3], target=50,
    tolerance=.2, max_evaluations=20,
    mesh=dict(edge_size=.5e-6, far_size=.125e-3, grade=.075))
saved_goal = plan.dumps()
result = ImpedanceDesignDocument.loads(saved_goal).solve()
saved_section = result.document.dumps()
```

Strict `sipi.impedance-design/1` has exactly `schema`, `template`, `parameters`,
`variable`, `bounds`, `target_ohm`, `quantity`, `tolerance_ohm`, `max_evaluations`,
`mesh`, `fixed_pitch_m`, `fixed_plane_spacing_m`. The last two fields are explicit
nulls when unused. Bounds are two positive increasing numbers in the chosen
template parameter's units; target and tolerance are positive ohms. The default
budget is 40, with accepted integer range 3–10000. Constructor arguments `target`
and `tolerance` map to the explicit `_ohm` JSON fields. All template defaults and
the resolved nominal mesh settings are saved. Record the engine version with
the JSON when archiving a calculation.

`from_dict`, `loads`, `to_dict`, `dumps` snapshot/copy inputs and reject unknown
versions/fields, missing fields, duplicate keys, nonfinite numbers and booleans
in numeric fields. This is a single-variable request; geometry and quantity
follow the [study template contracts](study.md). A width search may use fixed
pitch, and a layered-height search may use fixed plane spacing. Constraints
requiring another independent variable are rejected; dimensions that are not
being searched already remain fixed at their saved values.

`solve()` returns the existing `ImpedanceDesign`, including its saved candidate
section and evaluation history. It calls the same bounded search and separate
mesh confirmation described below. `GoalSeekError` and its completed history
propagate; a failed search is never represented as a successful saved design.
Save `plan.dumps()` alongside `result.document.dumps()` to retain both the goal
and the result input. Neither document format writes files automatically.

### Direct factory interface

```python
from sipi import seek_impedance, stripline

result = seek_impedance(
    lambda w: stripline(width=w, plane_spacing=1e-3, eps_r=4),
    (0.3e-3, 0.8e-3), 50.0,
    mesh={"edge_size": 0.5e-6, "far_size": 0.125e-3, "grade": 0.075},
    tolerance=0.1, max_evaluations=20)
print(result.parameter, result.impedance, result.refined_impedance)
```

`factory(parameter)` returns a valid `CrossSection`. Bounds must be positive,
finite and increasing, in the parameter's units. `quantity="z0"` selects a
single signal; `"z_diff"` selects a symmetric pair through `even_odd()`, including
its symmetry checks. Explicit [`z_diff_forward`](asymmetric_pair.md) selects
the real forward-current pair launch without assuming exchange symmetry.
Target and tolerance must be positive finite ohms.

The search evaluates both endpoints and accepts an endpoint within tolerance;
otherwise opposite endpoint residual signs are required. Bisection stops only
when the actual impedance residual is within tolerance. One solve is reserved
for a refinement with `edge_size`, `far_size` and `grade` halved. Both requested
and refined impedances must meet the target tolerance. `max_evaluations` counts
all solves, including the final refinement, and must be an integer of at least 3.


For a narrower search stopping residual, pass `search_tolerance` in ohms.
For example, `tolerance=0.5, search_tolerance=0.25` requires the requested-mesh
search to reach 0.25 Ω, then checks the separately refined result against
0.5 Ω. The threshold must be positive, finite and no larger than `tolerance`.
Omitting it, passing `None`, or setting it equal to `tolerance` preserves the
original behavior. Endpoint acceptance uses the narrower threshold too;
otherwise a genuine endpoint sign change is still required. This leaves room
for discretization drift, but does not guarantee success or increase the
evaluation or mesh budget. A failed refinement still raises an error.

Pass `search_tolerance` to `ImpedanceDesignDocument` to save this setting as
`sipi.impedance-design/4`, using the required `search_tolerance_ohm` field.
Version 4 retains the same geometry, fixed-pitch/plane constraints, and optional
material evaluation/binding fields as versions 1–3. `material_variables` requires
`material_evaluation`. Its positive search threshold must not exceed
`tolerance_ohm`; null, unknown fields and missing thresholds reject. Loading
never solves. Common saved execution retains the same refined acceptance and
failure history. Omitting the constructor option keeps the original version
and canonical JSON; versions 1–3 still reject extra threshold fields.

`ImpedanceDesign` contains the parameter, target, quantity, requested and refined
impedances, input document and evaluation history. `residual`,
`refined_residual` and `mesh_change` keep the target error and mesh change
distinct. The document is the requested-mesh input. `GoalSeekError.history`
records completed evaluations when a bracket, evaluation budget, parameter
resolution or refinement check fails. A field extraction that exceeds the
mesher's point budget raises `GoalMeshSizeLimitError`, catchable as both
`GoalSeekError` and `meshine.MeshSizeLimitError`. Its `__cause__` is the original
mesher exception. It retains completed `history`, failed `parameter` (in the
factory's units), `stage` (`search` or `refinement`), `attempts` (completed
solves plus the failed attempt), and `cause_type`. `input_json` holds the failed
geometry with all resolved mesh settings; `material_evaluation_json` retains
the selected frequency/models when present. No failed solve becomes a completed
history row, and no retry or automatic mesh relaxation occurs.

Invalid input, factory/material-factory errors and other solver exceptions
propagate unchanged; a failure is never returned as a successful design. On a refinement
failure, tighten mesh settings and rerun. This is a numerical target check, not
a manufacturing-tolerance guarantee or a proof of monotonicity for arbitrary
factories. Box/material uncertainty needs separate analysis.

## Validation

For matrix postprocessing, use `result, line = seek_impedance(..., return_line=True)`.
`line` is a `LineParameters` snapshot from the selected **requested mesh**, including
the selected frequency/material evaluation when supplied. Its C, C0, L and C_loss
arrays are independent read-only copies. No extra field solve is performed and no
field vectors or cross-request cache are retained. The separate refinement must
still pass; a failure returns neither a design nor a line. `return_line` must be a
boolean. The default `False` returns the original `ImpedanceDesign` with unchanged
fields; saved design/execution JSON does not gain a new option or matrix payload.
The snapshot is a real quasi-static line, not a complex lossy characteristic impedance.

`tests/sipi/test_design_documents.py` checks all four templates against explicit
geometry and checks that JSON round trips preserve C, C0, L and dielectric-loss
matrices. Invalid fields, mutation isolation and search failure paths are covered.
The real-FEM 50-ohm stripline search is compared with an independently rooted
Cohn conformal-map formula: width must agree within 1%, and both mesh residuals
must be at most 0.1 ohm. These thresholds were set before running the test.
The 47 tests passed on Linux, Python 3.12.14, NumPy 2.5.4 and SciPy 1.18.1;
platform and installed-package acceptance is handled separately by required CI.
Existing physical reference thresholds are unchanged. No new external dependency
or independent validation of coplanar physics is claimed by template equivalence.

`tests/sipi/test_impedance_design_document.py` adds a saved/reloaded 50-ohm Cohn
width comparison (1% width, both mesh residuals at most 0.2 ohm), no-solve parsing,
snapshot isolation, strict malformed-input checks, constraint/mesh/budget
forwarding and retained failures. This verifies the request path; it does not
expand the underlying models' physical validity.

[Correlated tolerance studies and fixed-pitch sampling](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/study.md).

[Fixed-frequency material studies and goals](material_impedance.md) preserve scalar/principal-axis overrides alongside geometry.

[Single material parameter goals (design v3)](material_goals.md) preserve the selected model and refined-mesh acceptance.

[Two-parameter differential/common impedance targets](pair_design.md) use bounded local search and a frozen-input mesh check.
