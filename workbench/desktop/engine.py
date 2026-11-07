"""Small JSON adapter shared by the desktop and browser Python runtimes."""

import math
import json
from pathlib import Path
from itertools import product
from numbers import Real

import numpy as np
import sipi
from sipi.templates import coated_microstrip

TEMPLATES = {name: getattr(sipi, name) for name in (
    'microstrip', 'stripline', 'coupled_microstrip', 'grounded_coplanar')}
TEMPLATES['coated_microstrip'] = coated_microstrip


def engine_info():
    out = {'sipi': sipi.__version__}
    for directory in (Path(__file__).resolve().parent / 'ui', Path(__file__).resolve().parent.parent / 'ui'):
        path = directory / 'build-info.json'
        if path.is_file():
            out['build'] = json.loads(path.read_text(encoding='utf-8'))
            break
    return out


def document(request):
    if 'document_text' in request:
        return sipi.CrossSectionDocument.loads(request['document_text'])
    if 'document' in request:
        return sipi.CrossSectionDocument.from_dict(request['document'])
    name = request.get('template')
    if name not in TEMPLATES:
        raise ValueError('Choose a supported cross-section template.')
    parameters = request.get('parameters')
    if not isinstance(parameters, dict):
        raise ValueError('Template parameters must be an object.')
    section = TEMPLATES[name](**parameters)
    # Persist the actual settings, including defaults, in every saved design.
    mesh = section.mesh_settings(**request.get('mesh', {}))
    return sipi.CrossSectionDocument(section, mesh=mesh)


def serialize_line(line):
    out = {name: getattr(line, name).tolist() for name in ('C', 'C0', 'L', 'C_loss')}
    out.update(names=list(line.names), G_1GHz=line.G(1e9).tolist())
    if len(line.names) == 1:
        out.update(z0=line.z0, eps_eff=line.eps_eff, delay=line.delay)
    elif len(line.names) == 2:
        try:
            out.update(line.even_odd())
        except ValueError as error:
            # A valid asymmetric pair still has C/L/G and a full network.
            # Do not manufacture symmetric modal impedances for that geometry.
            out['scalar_summary_unavailable'] = str(error)
    else:
        out['scalar_summary_unavailable'] = 'Scalar summaries require one signal or a symmetric pair.'
    return out



def network_settings(value):
    if not isinstance(value, dict) or set(value) != {'start_hz', 'stop_hz', 'points', 'length', 'resistance', 'z_ref'}:
        raise ValueError('Network settings need frequency bounds, points, length, resistance and z_ref.')
    for key in ('start_hz', 'stop_hz', 'length', 'resistance', 'z_ref'):
        v = value[key]
        if isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v):
            raise ValueError(f'{key} must be finite and real.')
    if not 0 <= value['start_hz'] < value['stop_hz'] <= 1e12:
        raise ValueError('Use increasing frequencies between 0 and 1 THz; check quasi-TEM validity separately.')
    if type(value['points']) is not int or not 2 <= value['points'] <= 201:
        raise ValueError('Use 2 to 201 frequency points.')
    if not 0 <= value['length'] <= 100 or value['resistance'] < 0 or value['z_ref'] <= 0:
        raise ValueError('Use length 0 to 100 m, resistance >= 0 and reference impedance > 0.')
    return dict(value)


def serialize_network(line, settings):
    count = len(line.names)
    f = np.linspace(settings['start_hz'], settings['stop_hz'], settings['points'])
    net = sipi.quasistatic_network(line, f, length=settings['length'],
        R=np.eye(count)*settings['resistance'], z_ref=settings['z_ref'])
    out = dict(settings=settings, frequency=net.frequency.tolist(),
               ports=list(net.port_names), z_ref=net.z_ref.tolist(),
               real=net.s.real.tolist(), imag=net.s.imag.tolist(),
               touchstone=net.touchstone(), extension=f's{2*count}p',
               model='constant diagonal series R; extracted C/L and constant-tangent G(f)')
    plotted = net
    if count == 2:
        plotted = net.mixed_mode()
        out['mixed'] = dict(ports=list(plotted.port_names), z_ref=plotted.z_ref.tolist(),
                            real=plotted.s.real.tolist(), imag=plotted.s.imag.tolist())
        out['crosstalk'] = dict(
            excitation='near conductor 1; every other port terminated in z_ref',
            next_ports=[2, 1], fext_ports=[4, 1],
            next_db=(20*np.log10(np.maximum(np.abs(net.s[:, 1, 0]), 1e-15))).tolist(),
            fext_db=(20*np.log10(np.maximum(np.abs(net.s[:, 3, 0]), 1e-15))).tolist())
    # Positive loss in dB; display floor is explicit, exported S is never clipped.
    out['transmission'] = 'Sdd21' if count == 2 else 'S21'
    out['insertion_loss_db'] = (-20*np.log10(np.maximum(np.abs(plotted.s[:, 1, 0]), 1e-15))).tolist()
    out['return_loss_db'] = (-20*np.log10(np.maximum(np.abs(plotted.s[:, 0, 0]), 1e-15))).tolist()
    out['phase_deg'] = np.angle(plotted.s[:, 1, 0], deg=True).tolist()
    return out


def study_documents(request, nominal):
    """Validate all sampled inputs before any solve; independent bounded inputs."""
    if 'document' in request or 'document_text' in request:
        raise ValueError('Choose a template before running a parameter study.')
    settings = request.get('study')
    if not isinstance(settings, dict) or set(settings) != {'mode', 'variables', 'points', 'seed'}:
        raise ValueError('Study needs mode, variables, points and seed.')
    mode, variables = settings['mode'], settings['variables']
    if mode not in ('sweep', 'corners', 'monte_carlo'):
        raise ValueError('Choose sweep, corners or monte_carlo.')
    if not isinstance(variables, list) or not 1 <= len(variables) <= (1 if mode == 'sweep' else 2):
        raise ValueError('Use one sweep variable or one/two tolerance variables.')
    if type(settings['points']) is not int or not 2 <= settings['points'] <= 32:
        raise ValueError('Use 2 to 32 study samples.')
    if type(settings['seed']) is not int or not 0 <= settings['seed'] < 2**32:
        raise ValueError('Seed must be an integer from 0 through 4294967295.')
    parameters = request['parameters']
    allowed = {'width', 'top_width', 'substrate_height', 'plane_spacing', 'thickness',
               'gap', 'eps_r', 'coating_height', 'coating_eps_r'}
    names, low, high = [], [], []
    for variable in variables:
        if not isinstance(variable, dict) or set(variable) != {'parameter', 'lower', 'upper'}:
            raise ValueError('Each variable needs parameter, lower and upper.')
        name = variable['parameter']
        if not isinstance(name, str) or name not in allowed or name not in parameters or name in names:
            raise ValueError('Study variables must be distinct, supported template inputs.')
        lower, upper = variable['lower'], variable['upper']
        if any(isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) for v in (lower, upper)) or lower >= upper:
            raise ValueError('Study bounds must be finite and strictly increasing.')
        names.append(name); low.append(lower); high.append(upper)
    if mode == 'sweep':
        samples = np.linspace(low, high, settings['points'])
    elif mode == 'corners':
        samples = np.asarray(list(product(*zip(low, high))), dtype=float)
    else:
        rng = np.random.Generator(np.random.PCG64(settings['seed']))
        samples = rng.uniform(low, high, size=(settings['points'], len(names)))
    # Validate the entire bounds box as well as sampled inputs. No resampling
    # around physically invalid inputs or silently discarding failed samples.
    factory = TEMPLATES[request['template']]
    for corner in product(*zip(low, high)):
        factory(**{**parameters, **dict(zip(names, corner))})
    documents = []
    for sample in samples:
        values = dict(zip(names, map(float, sample)))
        section = factory(**{**parameters, **values})
        documents.append((values, sipi.CrossSectionDocument(section, mesh=nominal.mesh_options)))
    cleaned = dict(mode=mode, variables=[dict(v) for v in variables], points=len(samples),
                   seed=settings['seed'], generator='PCG64' if mode == 'monte_carlo' else None,
                   distribution='independent uniform' if mode == 'monte_carlo' else None)
    return cleaned, documents


def execute_study(request, nominal):
    settings, documents = study_documents(request, nominal)
    quantity = 'z_diff' if request['template'] == 'coupled_microstrip' else 'z0'
    rows = []
    for values, doc in documents:
        row = dict(parameters=values, document=doc.to_dict())
        try:
            line = serialize_line(doc.analyze())
            value = line[quantity]
            if not math.isfinite(value) or value <= 0:
                raise ValueError('Solver returned an invalid study impedance.')
            row.update(status='complete', impedance=value, line=line)
        except Exception as error:
            row.update(status='error', error=str(error), error_type=type(error).__name__)
        rows.append(row)
    failed = sum(row['status'] != 'complete' for row in rows)
    summary = None
    if not failed:
        z = np.array([row['impedance'] for row in rows])
        summary = dict(minimum=float(z.min()), maximum=float(z.max()), mean=float(z.mean()),
                       sample_std=float(z.std(ddof=1)))
    return dict(schema='sipi.parameter-study/1', status='incomplete' if failed else 'complete',
                engine=dict(sipi=sipi.__version__, numpy=np.__version__), template=request['template'],
                nominal_parameters=dict(request['parameters']), nominal_document=nominal.to_dict(),
                settings=settings, quantity=quantity, rows=rows, failed=failed, summary=summary,
                mesh_policy='fixed resolved nominal mesh; no per-sample refinement check')


def execute(request):
    if not isinstance(request, dict):
        raise ValueError('Request must be a JSON object.')
    action = request.get('action')
    if action in ('saved-normalize', 'saved-analyze'):
        from sipi.execution import normalize_saved, execute_saved
        required = {'action', 'text'}
        allowed = required | ({'diagnostics'} if action == 'saved-analyze' else set())
        if not required <= request.keys() or not request.keys() <= allowed:
            raise ValueError('Saved analysis needs text and only the selected action options.')
        out = {'engine': engine_info()}
        if action == 'saved-normalize':
            out['document_text'] = normalize_saved(request['text'], max_input_bytes=200*1024)
        else:
            out['execution'] = execute_saved(request['text'], max_input_bytes=200*1024,
                max_evaluations=128, diagnostics=request.get('diagnostics', ()))
        return out
    if action not in ('document', 'analyze', 'design', 'network', 'study'):
        raise ValueError('Unknown calculation action.')
    settings = network_settings(request.get('network')) if action == 'network' else None
    doc = document(request)
    if action == 'network' and sum(not t.ground for t in doc.section.traces) not in (1, 2):
        raise ValueError('The network workbench supports one or two signal conductors.')
    out = {'engine': engine_info(), 'document': doc.to_dict()}
    if action == 'study':
        out['study'] = execute_study(request, doc)
    elif action == 'analyze':
        out['line'] = serialize_line(doc.analyze())
    elif action == 'network':
        line = doc.analyze()
        out['line'] = serialize_line(line)
        out['network'] = serialize_network(line, settings)
    elif action == 'design':
        if 'document' in request or 'document_text' in request:
            raise ValueError('Choose a template before searching for a width.')
        settings = request.get('design', {})
        params = dict(request['parameters'])
        factory = TEMPLATES[request['template']]
        mesh = request.get('mesh')
        if mesh is None:
            mesh = doc.section.mesh_settings()
            mesh['edge_size'] /= 4
            mesh['far_size'] /= 4
            mesh['grade'] /= 2
        result = sipi.seek_impedance(
            lambda width: factory(**{**params, 'width': width}),
            settings.get('bounds'), settings.get('target'),
            tolerance=settings.get('tolerance', 0.1),
            quantity='z_diff' if request['template'] == 'coupled_microstrip' else 'z0',
            mesh=mesh, max_evaluations=32)
        # Matrix output must correspond to the returned design, not the initial width.
        out['document'] = sipi.CrossSectionDocument(
            result.document.section,
            mesh=result.document.section.mesh_settings(**result.document.mesh_options)).to_dict()
        out['line'] = serialize_line(result.document.analyze())
        out['design'] = {
            'width': result.parameter, 'target': result.target,
            'impedance': result.impedance, 'refined_impedance': result.refined_impedance,
            'residual': result.residual, 'refined_residual': result.refined_residual,
            'mesh_change': result.mesh_change,
            'history': [vars(row) for row in result.history]}
    return out


def worker(request, connection):
    try:
        connection.send({'status': 'complete', 'result': execute(request)})
    except Exception as exc:
        error = {'status': 'error', 'message': str(exc), 'type': type(exc).__name__}
        if isinstance(exc, sipi.GoalSeekError):
            error['history'] = [vars(row) for row in exc.history]
        connection.send(error)
    finally:
        connection.close()
