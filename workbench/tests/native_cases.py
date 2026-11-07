"""Fixed native inputs/outputs for browser parity; acceptance is relative 1e-6."""

import json
from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from engine import execute

cases = []
for template, extra in [('microstrip', {}), ('stripline', {}),
                        ('coupled_microstrip', {'gap': .2e-3}),
                        ('grounded_coplanar', {'gap': .2e-3, 'ground_width': 1e-3})]:
    parameters = {'width': .5e-3, 'eps_r': 4, 'thickness': 0,
                  'plane_spacing' if template == 'stripline' else 'substrate_height': 1e-3, **extra}
    request = {'action': 'analyze', 'template': template, 'parameters': parameters,
               'mesh': {'edge_size': 5e-6, 'far_size': .5e-3, 'grade': .2}}
    cases.append({'input': request, 'result': execute(request)})
for template in ('stripline', 'coupled_microstrip'):
    request = next(row['input'] for row in cases if row['input']['template'] == template)
    request = {**request, 'action':'network', 'network':dict(start_hz=1e6, stop_hz=1e9,
               points=9, length=.1, resistance=2.0, z_ref=50)}
    cases.append({'input':request, 'result':execute(request)})
for template, extra in [('stripline', {}), ('coated_microstrip',
        dict(coating_height=.2e-3, coating_eps_r=3.5, coating_tan_delta=.01))]:
    request = {'action': 'analyze', 'template': template, 'parameters': {
        'width': .5e-3, 'top_width': .4e-3, 'thickness': .1e-3, 'eps_r': 4,
        'tan_delta': .02,
        'plane_spacing' if template == 'stripline' else 'substrate_height': 1e-3, **extra},
        'mesh': {'edge_size': 5e-6, 'far_size': .5e-3, 'grade': .2}}
    cases.append({'input': request, 'result': execute(request)})
for mode in ('sweep', 'monte_carlo'):
    request = dict(next(row['input'] for row in cases if row['input']['template'] == 'stripline'))
    request.update(action='study', study=dict(mode=mode, points=3, seed=42,
        variables=[dict(parameter='eps_r', lower=3.6, upper=4.4)]))
    cases.append({'input': request, 'result': execute(request)})
asymmetric = deepcopy(next(row['result']['document'] for row in cases
                           if row['input']['template'] == 'coupled_microstrip'))
asymmetric['traces'][1]['width'] *= .5
for action in ('analyze', 'network'):
    request = dict(action=action, template='imported_asymmetric', document=asymmetric,
                   network=dict(start_hz=1e6, stop_hz=1e9, points=9, length=.1, resistance=2., z_ref=50))
    cases.append({'input':request, 'result':execute(request)})
print(json.dumps(cases, allow_nan=False))
