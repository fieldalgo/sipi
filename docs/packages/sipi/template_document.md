# Editable template section inputs

[한국어](../../locales/ko/pages/packages/sipi/template_document.md) · [Cross-section JSON](design.md) · [Projects](project.md) · [Shared execution](execution.md)

`TemplateSectionDocument` preserves a supported template's name and numeric
parameters alongside its exact geometric cross-section and resolved mesh
controls. An application can restore a parameter form without guessing the
original dimensions from polygons. This is an engine input contract; a template
form or project user interface is not implemented by this class.

```python
from sipi.template_document import TemplateSectionDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject

section = TemplateSectionDocument('stripline',
    dict(width=.5e-3, plane_spacing=1e-3, eps_r=4),
    mesh=dict(edge_size=40e-6, far_size=.25e-3, grade=.3))
request = SavedExecutionRequest(section.dumps())
receipt = request.run()
assert receipt['execution']['status'] == 'complete'
assert receipt['execution']['result']['z0_ohm'] > 0
# Synthetic demonstration metadata, not actual runtime provenance.
record = SavedExecutionRecord(request, receipt, run_id='demo:template-1',
    artifacts=[dict(component='sipi', version='example-only', kind='wheel', sha256='1'*64)])
project = SavedProject(request, project_id='demo:project', design_id='a',
                       title='Stripline comparison', label='Baseline')
project = project.attach_record('a', record, select=True)
restored = SavedProject.loads(project.dumps())
reopened = TemplateSectionDocument.loads(restored.prepare('a').source_text)
assert reopened.parameters == section.parameters
assert reopened.cross_section.dumps() == section.cross_section.dumps()
```

All 42 existing manufacturing template factories registered for impedance
studies are available. Existing geometric and material validity rules still
apply. Lengths use meters; relative permittivity and loss tangent are
dimensionless. This class adds no factory, solver, material model or new physical
accuracy. `analyze()` delegates to its ordinary `CrossSectionDocument` and shared
execution uses the existing cross-section result fields.

## Edit, then choose a calculation

```python
from sipi.design_document import ImpedanceDesignDocument
from sipi.study import ImpedanceStudyDocument

edited = TemplateSectionDocument(reopened.template,
    dict(reopened.parameters, width=.6e-3), mesh=reopened.mesh_options)
updated = restored.update_design('a', SavedExecutionRequest(edited.dumps()))
assert updated.current_record('a') is None
assert updated.design('a')['records'] == [record.to_dict()]

# Prepare existing goal/study inputs from the saved template without solving.
goal = ImpedanceDesignDocument(edited.template, edited.parameters,
    variable='width', bounds=[.4e-3, .8e-3], target=50,
    max_evaluations=32, mesh=edited.mesh_options)
study = ImpedanceStudyDocument(edited.template, edited.parameters,
    quantity='z0', mesh=edited.mesh_options,
    sampling=dict(kind='corners', variables=[dict(name='width', lower=.55e-3, upper=.65e-3)]))
assert goal.to_dict()['parameters'] == edited.parameters
assert study.to_dict()['parameters'] == edited.parameters
```

Edits create a new document. The example explicitly preserves mesh controls;
omitting `mesh` deliberately resolves defaults for the changed section instead.
Neither choice is a convergence certificate. Goal/study quantity, bounds,
sampling, fixed pitch and material overrides keep their own existing contracts.
Preparing those inputs does not demonstrate that a target is feasible or that
the selected mesh meets its refinement tolerance.

## Exact geometry binding

`sipi.template-section/1` has exactly `schema`, `template`, `parameters` and
`cross_section`. Parameter binding rejects unknown/missing names, booleans and
nonfinite numeric values. Default argument values are included explicitly;
`None` is permitted only for optional parameters whose existing default is
`None`. Such a default may remain `None` in the parameter list while its actual
physical geometry is fully recorded in `cross_section`.

The nested cross-section uses its existing versioned geometry schema. Its mesh
contains all four resolved controls: `edge_size`, `far_size`, `grade` and
`min_angle`. On loading, the current factory rebuilds geometry from the saved
parameters with those mesh controls. The canonical nested geometry must match
exactly. A mismatched width, material, boundary, geometry version or unresolved
mesh is rejected. A later engine that changes factory semantics must explicitly
handle migration; this class does not silently replace the stored section.

`template`, `parameters`, `cross_section`, `section` and `mesh_options` provide
detached/reconstructed values. The snapshot is immutable. `loads`/`from_dict`
reject unknown fields, duplicate keys and nonfinite JSON; preparation performs
geometry validation without field solves. The original geometric JSON formats
remain supported without inferring a template from arbitrary geometry. Shared
input byte limits and saved request/project identity remain in force.

```sh
python -m pytest -q tests/sipi/test_template_document.py tests/sipi/test_execution_request.py tests/sipi/test_execution_record.py tests/sipi/test_project.py
```

The frozen 42-case fixture records the preceding factories' exact defaults,
geometry and mesh, including tapered, layered, coated and finite-ground cases.
It is an **existing-geometry regression reference**, not independent physical
truth. Separate checks compare actual direct and saved matrices, exercise an
independent Cohn stripline with mesh/outer-domain refinement, and verify project
reopening and edit invalidation. Existing numerical methods and tolerances are
unchanged. Additional UI forms, browser runtime parity and Windows acceptance
remain separate work.
