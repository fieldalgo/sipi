# Saved FEM geometry-energy transmission lines

`FEMShapeTransmissionLineDocument` explicitly selects the checked vacuum FEM
geometry-energy current method and whole-boundary surface metals. Its schema is
`sipi.fem-shape-transmission-line/1`. The existing saved-line methods are unchanged.

The nine root keys are `schema`, `cross_section`, `frequency_hz`, `materials`,
`conductors`, `reference`, `ground_thickness_m`, `length_m` and `reference_ohms`.
Lengths are metres and frequency is Hz. `cross_section` retains its existing
versioned geometry and optional mesh controls. Each signal and the one common
reference metal use the existing bulk/rough or explicit outside-in coating
records from transmission-line/7. Face-specific and separate ground materials
are not admitted by this schema. There are 1–4 signals; the name `ground` is
reserved by the shared capacitance API.

```python
from sipi import CrossSectionDocument, FEMShapeTransmissionLineDocument
from sipi.templates import coupled_stripline

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness={'kind': 'smooth'})

section = coupled_stripline(width=.0004, gap=.0003, plane_spacing=.002,
                            thickness=.00005, eps_r=4., box_width=.008)
document = FEMShapeTransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=2.5e-6,
        far_size=.0001, grade=.05)),
    [2e9, 5e9], materials={},
    conductors={'positive': metal(58e6), 'negative': metal(35e6)},
    reference=metal(58e6), ground_thickness=35e-6, length=.02)
assert FEMShapeTransmissionLineDocument.loads(document.dumps()).dumps() == document.dumps()
```

Call `document.analyze()` to solve. Normalization validates material/core/skin
admission without meshing or fields. Analysis generates one mesh and shares it
between the vacuum current basis and frequency-dependent dielectric C/G. The
same C0 supplies external L; the boundary metal laws supply R and internal L.
The existing RLGC network then supplies the finite-length S matrix. Original
flux, shape derivative, extension, symmetry and energy checks remain mandatory.
Frequency budgets are checked before analysis in common execution.

The result inherits R/L/G/C, network and propagation diagnostics from the existing
line result. `current_record()` retains original gradient energies/fluxes, both
geometric extensions, both finite-difference steps and every completed vacuum
capacitance sample. The mesh descriptor records counts and SHA-256 hashes of
nodes, triangles and ordered signal/ground indices, using explicit little-endian
float64/int64 arrays. It identifies the actual mesh; hashes alone do not contain
its coordinates or certify reproducibility on another platform.

Common `normalize_saved`, `execute_saved`, `SavedExecutionRequest`, execution
records, projects and CLI execution accept the new document. Requested
characteristic/mode diagnostics retain the existing rejection rules and do not
erase a successfully extracted line. Existing record version defaults and
host-declared artifact semantics are unchanged.

`FEMShapeLineError` records the failed stage and exact normalized input. Later
failures retain completed current evidence; a typed current failure retains its
original gradient result when available, completed capacitances, failed request
address and partial energy observations. Nonfinite values in failed observations
are explicitly encoded as the strings `nan`, `+inf` or `-inf`; these are never
accepted numerical results. A failed execution has a null result and its error
record can be retained in either supported execution-record version. Interrupts
propagate.

Completion means extraction and its numerical consistency checks completed.
It does not certify mesh/outer convergence, small mutual-entry or measured
accuracy. Coarse meshes can be rejected for nonphysical energy eigenvalues;
refinement and independent references remain necessary. This document does not
claim a browser Worker or Windows executable has been validated for this method.

[한국어](../../locales/ko/pages/packages/sipi/fem_shape_line.md)
