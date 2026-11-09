# Saved lines with explicit panel currents

[Explicit two-parameter forward goals](panel_pair_goal.md) add independent volume, panel and joint refinement checks.

`PanelTransmissionLineDocument` describes an explicit combination of shared
boundary-panel vacuum currents and the existing dielectric field extraction.
Its `sipi.panel-transmission-line/1` input contains exactly `schema`, `line`
and `panel`. The nested `line` is a canonical `TransmissionLineDocument`;
`panel` stores `panels_per_edge`, `ground_modes` and `interpolation_degree`.
All three controls are saved even when constructor defaults are used.

The nested conductor must be `perfect` or `surface-boundaries`. Other surface
models are not converted implicitly. Existing transmission-line versions 1–6
and their default calculation methods retain their original contracts. A panel
line cannot be loaded as an ordinary transmission-line document and silently
lose its selected current method.

Construction and normalization do not generate a mesh or solve a field. They
validate the existing line inputs, strict keys, frequency/material/metal rules,
bottom-ground/open-top/open-side conditions, positive conductor thickness and
integer panel controls. Duplicate keys and nonfinite JSON numbers are rejected.
The document stores copies; modifying input dictionaries, returned dictionaries,
or the nested line accessor cannot mutate the retained calculation input.

The shared panel kernel still performs its convexity, clearance, aspect-ratio,
conditioning and numerical refinement checks at calculation time. Successful
JSON normalization is not proof that those checks or physical validity will
pass. Exact shared dependency artifacts are required as described in
[panel conductor loss](panel_conductor.md).

## One matched calculation

1. Calculate the vacuum panel current factors. Explicit ground traces remain at
   zero voltage. For `surface-boundaries`, apply the existing per-metal surface
   laws and skin-depth gates. A panel failure propagates before volume meshing.
2. Generate one dielectric mesh using the saved geometry mesh controls.
3. Reuse the existing material sampling and dielectric extraction, supplying the
   panel C0 as its vacuum reference. For a spatially uniform scalar dielectric,
   C and G follow the exact complex-permittivity scaling of that same C0.
   Heterogeneous or tensor dielectric fields use the existing volume solve.
4. Assemble R and internal L from the surface laws, and external L from
   mu_0 epsilon_0 inverse(C0). Compute the existing uniform-line network and
   optional characteristic/modal diagnostics from the resulting RLGC matrices.

The result retains the complete panel-line JSON, resolved volume mesh controls,
panel settings and current diagnostics. R/L/G/C are frequency-indexed SI
matrices. Perfect conductors explicitly give R=0 and internal L=0, while keeping
the panel external inductance. `characteristic()` and the existing line result
operations use these same matrices.

There is no fallback solver, automatic geometry change or unrequested panel
refinement. Panel resolution, volume resolution and finite outer-domain size
are distinct convergence requirements. The finite panel boundary is grounded
at the bottom and has zero normal derivative at the other outer walls; it is
not an exact infinite open domain.

## Validation and limits

Checks cover strict round trips, unchanged earlier saved inputs, input isolation,
field-free normalization, matching C0 and inductance, uniform dielectric scaling,
metal composition, one volume mesh, and independent 2N characteristic solutions
with passive reciprocal networks. The heterogeneous two-line study recomputes
its dielectric fields at the original three volume resolutions and three outer
sizes, with the corresponding explicit panel resolutions. Matrix recombination
can then separate the volume and panel axes without representing those
combinations as additional field solves.

These are fixed-input verification and convergence checks. They do not establish
a successful inverse search, accuracy for arbitrary layouts, a material fit's
validity or agreement with measured hardware. Existing quasi-TEM and first-order
surface-impedance limits remain. Interior current diffusion, independent foil
faces, arbitrary nonconvex panel geometry and distributed 3D transitions are
outside this path.

## Example

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.execution import execute_saved

section = CrossSection(
    [Layer("uniform", .002, 4.2, tan_delta=.02)],
    [Trace("left", -.0003, .0005, .0002, thickness=35e-6),
     Trace("right", .0003, .0005, .0002, thickness=35e-6)],
    .004,
)
metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness={"kind": "smooth"})
line = TransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(
        edge_size=10e-6, far_size=.2e-3, grade=.1)),
    [1e9, 2e9], materials={},
    conductor=dict(kind="surface-boundaries",
        conductors={"left": metal, "right": metal}, reference=metal,
        ground_thickness=35e-6),
    length=.02, schema="sipi.transmission-line/3",
)
document = PanelTransmissionLineDocument(line, panels_per_edge=16)
text = document.dumps()
assert PanelTransmissionLineDocument.loads(text).dumps() == text
output = execute_saved(text, max_evaluations=2,
                       diagnostics=["characteristic"])
assert output["status"] == "complete"
assert output["result"]["current_solver"]["settings"]["panels_per_edge"] == 16
```
