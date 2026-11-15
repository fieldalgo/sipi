# Explicit corner resolution for FEM shape lines

`CornerFEMShapeTransmissionLineDocument` retains an original FEM shape line
and a separate corner target in metres. Its strict JSON schema is
`sipi.corner-fem-shape-transmission-line/1`, with exactly `schema`, `line` and
`corner_size`. The target must be finite, positive and no greater than the
resolved edge size. Loading and normalization validate without a field solve.

```python
from sipi.templates import coupled_stripline
from sipi import (CrossSectionDocument,
                  FEMShapeTransmissionLineDocument,
                  CornerFEMShapeTransmissionLineDocument)
from sipi.execution import normalize_saved

section = coupled_stripline(width=.0004, gap=.0003, plane_spacing=.002,
                            eps_r=4., thickness=.00005, box_width=.008)
cross = CrossSectionDocument(section,
    mesh=dict(edge_size=5e-6, far_size=.0002, grade=.1))
metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness=dict(kind='smooth'))
line = FEMShapeTransmissionLineDocument(cross, [2e9, 5e9], materials={},
    conductors=dict(positive=metal, negative=metal), reference=metal,
    ground_thickness=35e-6, length=.02)
saved = CornerFEMShapeTransmissionLineDocument(line, corner_size=2.5e-6)
assert normalize_saved(saved.dumps()) == saved.dumps()
# result = saved.analyze()
```

The [original FEM shape line](fem_shape_line.md) still supplies geometry,
frequency samples, dispersive materials, whole-boundary metals, reference
metal, thickness, length and port references. Its derivative, extension,
positive-energy, flux and skin-depth checks remain mandatory. The explicit
corner target changes mesh sizing; it does not select a different current
solver. Setting it equal to the edge target reproduces the original mesh.
Both vacuum and material fields use the same actual mesh.

The common executor and saved request support characteristic/mode diagnostics
and check the nested frequency count against the host budget before solving.
Results retain full input, resolved corner controls, actual mesh hashes and
current observations. Staged failures retain the wrapper input and any complete
or partial current evidence. A mesh-size limit is retained as a failure;
interruption propagates. Reopening an execution record or project does not solve
again. Editing the corner target invalidates the current result link while
preserving history. Declare the actual numerical artifacts when saving records.

The original FEM line schema still rejects a corner key in its nested mesh.
Use the explicit wrapper. Existing FEM study, goal and resolution documents
continue to require their original line type; this wrapper is not implicitly
accepted by them.

Validation checks original behavior, an actual paired line at equal/halved
corner targets, all 24 capacitance offsets, two extension fields, independent
metal-transfer composition and four-port propagation. A finite-mesh current
consistency check does not establish mesh or outer-domain convergence. In
particular, weak mutual resistance needs its own entrywise convergence check;
this mesh-control API does not certify conductor-loss accuracy or new platforms.

[한국어](../../locales/ko/pages/packages/sipi/corner_fem_line.md)
