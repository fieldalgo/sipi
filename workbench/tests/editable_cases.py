"""Fixed editable inputs for the real browser save/reopen acceptance."""
import json
from sipi.template_document import TemplateSectionDocument

cases = []
for name in ('microstrip', 'stripline', 'coupled_microstrip', 'grounded_coplanar', 'coated_microstrip'):
    p = dict(width=.0005000000000123456, thickness=0, eps_r=4.123456789012345,
             tan_delta=.0123456789012345, box_width=.016)
    p['plane_spacing' if name == 'stripline' else 'substrate_height'] = .0010000000000123
    if name != 'stripline': p['air_height'] = .0067
    if name in ('coupled_microstrip', 'grounded_coplanar'): p['gap'] = .0002
    if name == 'grounded_coplanar': p['ground_width'] = .003
    if name == 'coated_microstrip': p.update(thickness=.000035, top_width=.0004,
        coating_height=.0002, coating_eps_r=3, coating_tan_delta=.02)
    doc = TemplateSectionDocument(name, p, mesh=dict(edge_size=8e-6, far_size=.00025, grade=.3))
    cases.append(doc.to_dict())
unsupported = TemplateSectionDocument('coupled_stripline', dict(width=.0005, gap=.0002, plane_spacing=.001, eps_r=4))
print(json.dumps(dict(cases=cases, unsupported=unsupported.to_dict()), allow_nan=False))
