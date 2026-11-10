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
                        ('coupled_stripline', {'gap': .2e-3}),
                        ('grounded_coplanar', {'gap': .2e-3, 'ground_width': 1e-3}),
                        ('coupled_grounded_coplanar', {'gap':.3e-3, 'ground_gap':.2e-3, 'ground_width':1e-3})]:
    parameters = {'width': .5e-3, 'eps_r': 4, 'thickness': 0,
                  'plane_spacing' if template in ('stripline', 'coupled_stripline') else 'substrate_height': 1e-3, **extra}
    request = {'action': 'analyze', 'template': template, 'parameters': parameters,
               'mesh': {'edge_size': 5e-6, 'far_size': .5e-3, 'grade': .2}}
    cases.append({'input': request, 'result': execute(request)})
for template in ('stripline', 'coupled_microstrip', 'coupled_stripline', 'coupled_grounded_coplanar'):
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
# Explicit buried-pair placement: field, four-port response and height study.
placement = dict(action='analyze', template='coupled_stripline', parameters=dict(
    width=.3e-3, gap=.3e-3, plane_spacing=1e-3, trace_height=.3e-3,
    thickness=35e-6, top_width=.2e-3, eps_r=4., tan_delta=.02, box_width=6e-3),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.15))
for action in ('analyze', 'network', 'study'):
    request = {**placement, 'action': action}
    if action == 'network': request['network'] = dict(start_hz=1e6, stop_hz=1e9,
        points=3, length=.1, resistance=2., z_ref=50)
    if action == 'study': request['study'] = dict(mode='sweep', points=2, seed=42,
        variables=[dict(parameter='trace_height', lower=.28e-3, upper=.32e-3)])
    cases.append({'input': request, 'result': execute(request)})
# Explicit offset single placement: field, two-port response and height study.
placement = dict(action='analyze', template='offset_stripline', parameters=dict(
    width=.3e-3, plane_spacing=1e-3, trace_height=.3e-3,
    thickness=35e-6, top_width=.2e-3, eps_r=4., tan_delta=.02, box_width=6e-3),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.15))
for action in ('analyze', 'network', 'study'):
    request = {**placement, 'action': action}
    if action == 'network': request['network'] = dict(start_hz=1e6, stop_hz=1e9,
        points=3, length=.1, resistance=2., z_ref=50)
    if action == 'study': request['study'] = dict(mode='sweep', points=2, seed=42,
        variables=[dict(parameter='trace_height', lower=.28e-3, upper=.32e-3)])
    cases.append({'input': request, 'result': execute(request)})
# Finite tapered planar coating: field, four-port response and coating study.
coated = dict(action='analyze', template='coupled_coated_microstrip', parameters=dict(
    width=.5e-3, gap=.3e-3, substrate_height=.5e-3, thickness=35e-6,
    top_width=.4e-3, eps_r=4., tan_delta=.01, coating_height=.1e-3,
    coating_eps_r=3.5, coating_tan_delta=.02, box_width=12e-3, air_height=6e-3),
    mesh=dict(edge_size=4e-6, far_size=.25e-3, grade=.2))
for action in ('analyze', 'network', 'study'):
    request = {**coated, 'action': action}
    if action == 'network': request['network'] = dict(start_hz=1e6, stop_hz=1e9,
        points=3, length=.1, resistance=2., z_ref=50)
    if action == 'study': request['study'] = dict(mode='sweep', points=2, seed=42,
        variables=[dict(parameter='coating_height', lower=.09e-3, upper=.11e-3)])
    cases.append({'input': request, 'result': execute(request)})
# Same exact qualified coated-coplanar inputs in native and Worker runtimes.
coated_coplanar = dict(width=.5e-3, gap=.2e-3, ground_width=1e-3,
    substrate_height=.5e-3, eps_r=4., tan_delta=.01, thickness=.035e-3, top_width=.4e-3,
    coating_height=.1e-3, coating_eps_r=3.5, coating_tan_delta=.02, air_height=6e-3, box_width=12e-3)
request = dict(action='analyze', template='coated_grounded_coplanar', parameters=coated_coplanar,
    mesh=dict(edge_size=4e-6, far_size=.25e-3, grade=.2))
cases.append(dict(input=request, result=execute(request)))
request = {**request, 'action':'network', 'network':dict(start_hz=1e6,stop_hz=1e9,points=3,length=.1,resistance=2.,z_ref=50.)}
cases.append(dict(input=request, result=execute(request)))
request = {k:v for k,v in request.items() if k!='network'}
request.update(action='study', study=dict(mode='sweep',variables=[dict(parameter='ground_width',lower=.8e-3,upper=1.2e-3)],points=2,seed=42))
cases.append(dict(input=request, result=execute(request)))

# Finite coated coplanar pair: distinct signal/ground gaps and four-port response.
paired_coating={**coated_coplanar, 'gap':.3e-3, 'ground_gap':.2e-3}
for action in ('analyze','network','study'):
    request=dict(action=action,template='coupled_coated_grounded_coplanar',parameters=paired_coating,
        mesh=dict(edge_size=4e-6,far_size=.25e-3,grade=.2))
    if action=='network':request['network']=dict(start_hz=1e6,stop_hz=1e9,points=3,length=.1,resistance=2.,z_ref=50.)
    if action=='study':request['study']=dict(mode='sweep',variables=[dict(parameter='ground_gap',lower=.15e-3,upper=.25e-3)],points=2,seed=42)
    cases.append(dict(input=request,result=execute(request)))

print(json.dumps(cases, allow_nan=False))
