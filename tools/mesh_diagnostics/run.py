# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Unshipped, single-process diagnostics for an isolated meshine candidate."""
import argparse
import ast
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SCRIPT_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
ACTIVE = False


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def manifest():
    data = json.loads((HERE / 'manifest.json').read_text(encoding='utf-8'))
    for name in ('patch', 'inputs', 'reference'):
        file = HERE / ('candidate.patch' if name == 'patch' else name+'.json')
        if sha256(file.read_bytes()) != data[name+'_sha256']:
            raise ValueError('diagnostic '+name+' checksum mismatch')
    return data


def checked_payload(root, expected):
    """Read exact tracked bytes before writing anything to the candidate copy."""
    root = Path(root).resolve()
    result = {}
    for name, digest in expected.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError('source path escapes checkout')
        raw = path.read_bytes()
        if sha256(raw) != digest:
            raise ValueError('source checksum mismatch: '+name)
        result[name] = raw
    return result


def candidate_source(original, data):
    """Reproduce the reviewed four-call change; reject every other source base."""
    if sha256(original) != data['original_refine_sha256']:
        raise ValueError('wrong refine source base')
    text = original.decode('utf-8')
    lines = text.splitlines(keepends=True)
    count = 0
    for node in reversed(ast.parse(text).body):
        if isinstance(node, ast.FunctionDef) and node.name in ('_treated_apices', '_lattice_point'):
            old = ''.join(lines[node.lineno-1:node.end_lineno])
            count += old.count('np.linalg.norm(')
            lines[node.lineno-1:node.end_lineno] = [old.replace('np.linalg.norm(', '_length2(')]
    helper = ('def _length2(delta: np.ndarray) -> float:\n'
              '    """Scalar 2D length without a platform-dependent BLAS dot reduction."""\n'
              '    return math.hypot(float(delta[0]), float(delta[1]))\n\n\n')
    result = ''.join(lines).replace('def _treated_apices(', helper+'def _treated_apices(', 1).encode()
    if count != data['replacements'] or sha256(result) != data['candidate_refine_sha256']:
        raise ValueError('candidate differs from reviewed source')
    return result


def prepare(engine, destination, variant):
    data = manifest()
    revision = subprocess.check_output(['git', '-C', str(engine), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != data['base']:
        raise ValueError('wrong shared checkout commit')
    payload = checked_payload(engine, data['package_and_tests'])
    if variant not in ('original', 'candidate'):
        raise ValueError('unknown variant')
    if variant == 'candidate':
        key = 'packages/meshine/src/meshine/refine.py'
        payload[key] = candidate_source(payload[key], data)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in payload.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    write_json(destination / 'provenance.json', dict(
        variant=variant, shared_commit=revision,
        files={k: sha256(v) for k, v in payload.items()},
        patch_sha256=data['patch_sha256'], inputs_sha256=data['inputs_sha256'],
        reference_sha256=data['reference_sha256']))


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def array_record(value):
    import numpy as np
    a = np.asarray(value)
    a = np.asarray(a, dtype='<i8' if a.dtype.kind in 'biu' else '<f8')
    return dict(shape=list(a.shape), sha256=sha256(a.tobytes()))


@contextmanager
def trace_refinement(record):
    """Observe actual calls; do not substitute their inputs or return values.

    Not thread-safe. Use a fresh, single-threaded Python process per probe.
    Restoration also runs after a failed mesh or failed observer.
    """
    global ACTIVE
    import meshine.refine as refine
    from meshine import Domain
    if ACTIVE:
        raise RuntimeError('a refinement trace is already active')
    build, delaunay, triangle, apices = Domain.build, refine.Delaunay, refine._triangle_data, refine._treated_apices
    record.update(domains=[], rounds=[], triangle_calls=[], apex_calls=[])

    def observed_build(self, *args, **kwargs):
        points, segments, regions = result = build(self, *args, **kwargs)
        record['domains'].append(dict(points=points.tolist(), segments=[dict(
            a=int(s.a), b=int(s.b), owners=list(map(int, s.owners)), name=s.name,
            curve=None if s.curve is None else type(s.curve).__name__) for s in segments],
            regions=[dict(name=r.name, loops=[list(map(int, loop)) for loop in r.loops],
                          size=r.size) for r in regions]))
        return result

    def observed_delaunay(points, *args, **kwargs):
        tri = delaunay(points, *args, **kwargs)
        row = dict(points=array_record(points), simplices=array_record(tri.simplices))
        if not record['rounds']:
            row.update(first_points=points.tolist(), first_simplices=tri.simplices.tolist())
        record['rounds'].append(row)
        return tri

    def observed_triangle(points, triangles):
        result = triangle(points, triangles)
        row = dict(points=array_record(points), triangles=array_record(triangles),
                   outputs=[array_record(a) for a in result],
                   delaunay_round=len(record['rounds'])-1)
        if not record['triangle_calls']:
            row.update(first_points=points.tolist(), first_triangles=triangles.tolist(),
                       first_outputs=[a.tolist() for a in result])
        record['triangle_calls'].append(row)
        return result

    def observed_apices(*args, **kwargs):
        result = apices(*args, **kwargs)
        record['apex_calls'].append(dict(units={str(k): float(v) for k, v in result[1].items()}))
        return result

    ACTIVE = True
    Domain.build, refine.Delaunay = observed_build, observed_delaunay
    refine._triangle_data, refine._treated_apices = observed_triangle, observed_apices
    try:
        yield
    finally:
        Domain.build, refine.Delaunay = build, delaunay
        refine._triangle_data, refine._treated_apices = triangle, apices
        ACTIVE = False


def observe(section, mesh, *, quantity, snapshot=None, record=None):
    import numpy as np
    record = {} if record is None else record
    record.update(mesh=mesh, quantity=quantity)
    with trace_refinement(record):
        field = section.mesh(**mesh)
    line = field.line_parameters()
    record.update(nodes=array_record(field.mesh.nodes), triangles=array_record(field.mesh.triangles),
                  value=float(line.even_odd()['z_diff'] if quantity == 'z_diff' else getattr(line, quantity)),
                  matrices={k: getattr(line, k).tolist() for k in ('C', 'C0', 'C_loss', 'L')})
    if snapshot is not None:
        from sipi.conductor import surface_current_factors
        factors = surface_current_factors(field.mesh, field.signals, field.ground)
        record['conductor'] = dict(parts=factors.parts.tolist(), C0=factors.C0.tolist(),
                                   current_integrals=factors.current_integrals.tolist(),
                                   current_error=float(factors.current_error))
        arrays = dict(nodes=field.mesh.nodes, triangles=field.mesh.triangles, ground=field.ground,
                      signal_names=np.asarray(list(field.signals)))
        arrays.update({f'signal_{i}': v for i, v in enumerate(field.signals.values())})
        with Path(snapshot).open('xb') as stream:
            np.savez_compressed(stream, **arrays)
        record['snapshot_sha256'] = sha256(Path(snapshot).read_bytes())
    return record


def compare_impedances(values, reference):
    """Retain the existing 1e-9 runtime criterion; this is not an accuracy test."""
    import math
    expected = reference['values']
    if set(values) != set(expected):
        raise ValueError('runtime comparison is missing or adds cases')
    errors = {name: abs(values[name]/expected[name]-1) for name in expected}
    limit = reference['relative_impedance_limit']
    if limit != 1e-9:
        raise ValueError('unexpected runtime comparison limit')
    return dict(relative_limit=limit, relative_errors=errors,
                failed=[name for name, error in errors.items() if not math.isfinite(error) or error > limit])


def probe(variant, destination):
    import platform
    from importlib import metadata
    import meshine.refine as refine
    from sipi import coupled_microstrip
    from sipi.study import ImpedanceStudyDocument, _TEMPLATES
    data = manifest()
    key = {'original': 'original_refine_sha256', 'candidate': 'candidate_refine_sha256'}[variant]
    digest = sha256(Path(refine.__file__).read_bytes())
    if digest != data[key]:
        raise ValueError('installed refine bytes do not match requested variant')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    environment = dict(variant=variant, shared_commit=data['base'], refine_sha256=digest,
                       inputs_sha256=data['inputs_sha256'], reference_sha256=data['reference_sha256'],
                       probe_script_sha256=SCRIPT_SHA256, python=sys.version, platform=platform.platform(),
                       versions={n: metadata.version(n) for n in ('sipi', 'meshine', 'galerkin', 'numpy', 'scipy', 'shapely')})
    write_json(destination / 'environment.json', environment)
    completed = []
    values = {}
    current = None
    try:
        inputs = json.loads((HERE / 'inputs.json').read_text(encoding='utf-8'))
        for request in inputs:
            doc = ImpedanceStudyDocument.from_dict(request)
            for index, parameters in enumerate(doc.sample_parameters()):
                name = request['template']+'-'+str(index)
                current = dict(case=name, template=request['template'], index=index, parameters=parameters)
                result = observe(_TEMPLATES[request['template']](**parameters), request['mesh'],
                                 quantity=request['quantity'], record=current)
                result.update(template=request['template'], index=index, parameters=parameters)
                write_json(destination / (name+'.json'), result)
                values[name] = result['value']
                completed.append(name)
        for label, factor in [('coarse', 1.), ('fine', .5)]:
            section = coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=1e-3,
                                         thickness=.05e-3, eps_r=4.)
            mesh = {k: v*factor for k, v in dict(edge_size=5e-6, far_size=.2e-3, grade=.1).items()}
            name = 'conductor-'+label
            current = dict(case=name)
            result = observe(section, mesh, quantity='z_diff_forward', snapshot=destination / (name+'.npz'), record=current)
            write_json(destination / (name+'.json'), result)
            completed.append(name)
        current = dict(phase='runtime-impedance-comparison')
        reference = json.loads((HERE / 'reference.json').read_text(encoding='utf-8'))
        if reference['inputs_sha256'] != data['inputs_sha256']:
            raise ValueError('runtime reference uses different inputs')
        comparison = compare_impedances(values, reference)
        write_json(destination / 'comparison.json', comparison)
        if comparison['failed']:
            raise ValueError('runtime impedance comparison failed: '+', '.join(comparison['failed']))
    except Exception as exc:
        write_json(destination / 'failure.json', dict(completed=completed, active_case=current,
                   error_type=type(exc).__name__, error=str(exc)))
        raise
    write_json(destination / 'completed.json', completed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('engine', type=Path)
    prep.add_argument('destination', type=Path)
    prep.add_argument('variant', choices=('original', 'candidate'))
    run = sub.add_parser('probe')
    run.add_argument('variant', choices=('original', 'candidate'))
    run.add_argument('destination', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.engine, args.destination, args.variant)
    else:
        probe(args.variant, args.destination)


if __name__ == '__main__':
    main()
