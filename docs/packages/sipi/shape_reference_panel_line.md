# Saved line with separate ground metals

`ShapeReferencePanelTransmissionLineDocument` saves the
[whole-boundary reference-metal model](shape_reference_conductor.md) with
matched dielectric fields and an RLGC network. The explicit schema is
`sipi.shape-reference-panel-transmission-line/1`. Existing saved schemas and
current methods retain their behavior.

The strict root keys are `schema`, `cross_section`, `frequency_hz`, `materials`,
`conductors`, `reference`, `ground_thickness_m`, `length_m`, `reference_ohms`,
`panel` and `step_fraction`. All lengths are metres, frequency Hz, conductivity
S/m and impedance ohms. `cross_section` is a saved cross-section/1, /2 or /3;
`materials` uses the existing explicit dielectric records. `conductors` maps
exactly the signal names to bulk/rough or layered surface-metal records.
`reference` explicitly has `kind: surfaces`, a bottom metal, null top/sides
and exactly the named ground traces in `conductors`. Each ground trace has
one whole-perimeter metal; face-specific laws are rejected. There is no
conflicting common-reference default. Finite-thickness convex geometry,
bottom ground and open top/sides remain required.

A layered metal has conductivity, relative permeability and an outside-in
`coatings` array (at most 32), with each layer's thickness_m, conductivity
and relative_permeability. Bulk/rough records have conductivity,
relative_permeability and explicit roughness. The existing model conventions,
good-conductor, individual skin-depth and remaining-core checks apply before
fields. The saved panel controls and both shape-offset levels are admitted
without solving fields during normalization. Shared quadrature, geometry and
conditioning checks still run during actual extraction.

The current solve supplies C0 and external L. One saved volume mesh supplies
C/G using the same C0; local metal laws supply R/internal L. The result retains
the exact input, mesh/current controls and all current samples. Common execution
supports characteristic/mode diagnostics and saves `current_solver` plus
`conductor_boundaries`: ordered labels, skin depth, roughness, complex surface
impedance, separate resistance contributions and ungrouped shape energy matrices.
Boundary order is signals, bottom plane, then ground traces in geometry order.
Grouped current integrals remain in `current_solver`; separate face or
plane/trace return-current integrals are not inferred from energy matrices.

A staged runtime failure produces `ShapePanelLineError`, retaining the original
cause, exact input and complete currents or partial current requests. Common
execution returns failed with null result and that error. KeyboardInterrupt
propagates. Existing requests, execution records /1 and /2, projects and CLI
can transport this input. The frequency budget is checked before fields; it
does not bound field-solver memory or wall time.

This field-free example constructs and normalizes a coated guard input:

```python
from sipi import CrossSection, Layer, Trace, CrossSectionDocument
from sipi import ShapeReferencePanelTransmissionLineDocument
from sipi.execution import normalize_saved

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness={'kind': 'smooth'})

section = CrossSection([Layer('uniform', .01105, 4.)], [
    Trace('a', -.0005, .0003, .001, 50e-6),
    Trace('guard', 0., .0002, .001, 50e-6, ground=True),
    Trace('b', .0005, .0004, .001, 60e-6),
], .02)
coated_guard = dict(kind='layered', conductivity=58e6,
    relative_permeability=1., coatings=[
        dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
        dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])
doc = ShapeReferencePanelTransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=10e-6, far_size=.0005, grade=.1)),
    [1e9, 4e9, 16e9], materials={},
    conductors={'a': metal(58e6), 'b': metal(35e6)},
    reference=dict(kind='surfaces', bottom=metal(45e6), top=None, sides=None,
                   conductors={'guard': coated_guard}),
    ground_thickness=35e-6, length=.02, panels_per_edge=32,
    ground_modes=1024, interpolation_degree=16, step_fraction=.001)
text = doc.dumps()
assert text == normalize_saved(text)
# result = doc.analyze()  # Runs actual current and dielectric field solves.
# from sipi import SavedExecutionRequest
# receipt = SavedExecutionRequest(text, diagnostics=['characteristic', 'modes']).run()
```

Checks include independent uniform-dielectric/LC identities, bulk/coating
transfer equations, passive reciprocal four-port networks, selected panel and
volume refinements, and exact preservation of direct-API currents. Finite
outer changes are observations, not an accepted outer-domain gate. These checks
do not establish arbitrary-geometry or small mutual-entry accuracy, measured
foil behavior, browser execution or platform release support. The local planar
coating law does not resolve coating corners or metal interior diffusion.
