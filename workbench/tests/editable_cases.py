"""Fixed editable inputs for the real browser save/reopen acceptance."""
import json
from sipi.template_document import TemplateSectionDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject

cases = []
for name in ('microstrip', 'stripline', 'coupled_microstrip', 'coupled_stripline', 'grounded_coplanar', 'coupled_grounded_coplanar', 'coated_microstrip'):
    p = dict(width=.0005000000000123456, thickness=0, eps_r=4.123456789012345,
             tan_delta=.0123456789012345, box_width=.016)
    p['plane_spacing' if name in ('stripline', 'coupled_stripline') else 'substrate_height'] = .0010000000000123
    if name not in ('stripline', 'coupled_stripline'): p['air_height'] = .0067
    if name in ('coupled_microstrip', 'coupled_stripline', 'grounded_coplanar', 'coupled_grounded_coplanar'): p['gap'] = .0002
    if name == 'coupled_stripline': p.update(trace_height=.000300000000012345, thickness=.000035, top_width=.0004)
    if name in ('grounded_coplanar', 'coupled_grounded_coplanar'): p['ground_width'] = .003
    if name == 'coupled_grounded_coplanar': p.update(ground_gap=.0002500000000123456, thickness=.000035, top_width=.0004)
    if name == 'coated_microstrip': p.update(thickness=.000035, top_width=.0004,
        coating_height=.0002, coating_eps_r=3, coating_tan_delta=.02)
    doc = TemplateSectionDocument(name, p, mesh=dict(edge_size=8e-6, far_size=.00025, grade=.3))
    cases.append(doc.to_dict())
unsupported = TemplateSectionDocument('offset_stripline', dict(width=.0005, trace_height=.0003, plane_spacing=.001, eps_r=4))
unsupported_project = SavedProject(SavedExecutionRequest(unsupported.dumps()),
    project_id='unsupported', design_id='a', title='Unsupported form', label='A')
base = TemplateSectionDocument('stripline',dict(width=.0005,plane_spacing=.001,eps_r=4),
    mesh=dict(edge_size=16e-6,far_size=.0005,grade=.3))
request = SavedExecutionRequest(base.dumps())
# Synthetic artifact declaration for a browser fixture, not runtime provenance.
record = SavedExecutionRecord(request, request.run(), run_id='fixture:run', artifacts=[
    dict(component='sipi',version='fixture-only',kind='wheel',sha256='1'*64)])
recorded = SavedProject(request, project_id='recorded',design_id='a',title='Recorded input',label='A')
recorded = recorded.attach_record('a',record,select=True)
print(json.dumps(dict(cases=cases, unsupported=unsupported.to_dict(),
    unsupported_project=unsupported_project.to_dict(), recorded_project=recorded.to_dict(),
    recorded_project_text=recorded.dumps()),allow_nan=False))
