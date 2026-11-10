"""Exercise the built executable from a Unicode/space path and record startup/cleanup."""

import argparse
from contextlib import contextmanager
import hashlib
import http.client
import json
import os
from pathlib import Path
import queue
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

STARTUP_URL = re.compile(r'(http://127\.0\.0\.1:\d+)/#token=([\w-]+)')


@contextmanager
def candidate_directory(report):
    """Keep a secondary cleanup error from replacing the actual smoke failure."""
    folder = tempfile.TemporaryDirectory(prefix='SIPI 한글 path ')
    try:
        yield folder.name
    except BaseException:
        try:
            folder.cleanup()
        except Exception as exc:
            report['directory_cleanup_error'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    else:
        # A cleanup error after an otherwise successful smoke must still fail.
        folder.cleanup()


def stop_candidate(process, request, report):
    """Stop the owned candidate gracefully before terminating its process tree."""
    if process.poll() is not None:
        return
    if request is not None:
        try:
            request('/api/shutdown', {})
            process.wait(timeout=20)
            report['failure_shutdown'] = 'graceful'
            return
        except Exception as exc:
            report['shutdown_error'] = {'type': type(exc).__name__, 'message': str(exc)}
    if process.poll() is None:
        if sys.platform == 'win32':
            # Killing just the outer onefile process can leave its child holding
            # extracted DLLs open. Target only this Popen-owned process tree.
            result = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                    capture_output=True, timeout=20)
            report['failure_tree_stop_returncode'] = result.returncode
        else:
            process.kill()
        process.wait(timeout=10)


def verify_recording(result, bundle, build, execution):
    """Check a real reply against independently read extracted files."""
    from sipi.execution_record import SavedExecutionRecord
    record = SavedExecutionRecord.loads(result['record_text'])
    assert record.receipt['execution'] == execution
    manifest = json.loads(result['runtime_manifest_text'])
    assert manifest['schema'] == 'sipi.frozen-runtime/1'
    assert manifest['build'] == build
    assert manifest['python_version'] == '3.13.17' and manifest['nuitka_version'] == '2.8.10'
    actual = [dict(path=path.relative_to(bundle).as_posix(), bytes=path.stat().st_size,
                   sha256=hashlib.sha256(path.read_bytes()).hexdigest())
              for path in bundle.rglob('*') if path.is_file()]
    assert manifest['files'] == sorted(actual, key=lambda row: row['path'])
    inner = next(row for row in actual if row['path'] == manifest['executable'])
    assert record.artifacts['verification'] == 'host-declared'
    assert record.artifacts['items'] == [
        dict(component='sipi', version='0.1.0', kind='executable', sha256=inner['sha256']),
        dict(component='sipi-frozen-runtime', version='1', kind='runtime',
             sha256=hashlib.sha256(result['runtime_manifest_text'].encode('utf-8')).hexdigest())]
    return dict(independently_checked_files=len(actual), unpacked_executable=manifest['executable'])


def capture_output(stream, ready, report):
    """Retain a bounded diagnostic transcript even when startup exits early."""
    report['process_output'] = ''
    report['process_output_truncated'] = False
    for line in stream:
        if STARTUP_URL.search(line):
            ready.put(line)
        safe = re.sub(r'#token=[\w-]+', '#token=[redacted]', line)
        remaining = 65536-len(report['process_output'])
        report['process_output'] += safe[:remaining]
        if len(safe) > remaining:
            report['process_output_truncated'] = True


def check_rejected_request(url, token):
    """The frozen HTTP host must deliver an early error despite send backpressure."""
    address = urlsplit(url)
    body = json.dumps({'x': 'x' * 270000})
    statuses = []
    for _ in range(3):
        conn = http.client.HTTPConnection(address.hostname, address.port, timeout=10)
        try:
            conn.connect()
            conn.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
            conn.request('POST', '/api/job', body, {'Authorization': 'Bearer ' + token,
                         'Content-Type': 'application/json'})
            response = conn.getresponse()
            value = json.loads(response.read())
            assert response.status == 413 and '256 KiB' in value['message']
            statuses.append(response.status)
        finally:
            conn.close()
    return dict(body_bytes=len(body.encode('utf-8')), requested_send_buffer=4096,
                statuses=statuses)


def check_width_goal(request):
    """Exercise the installed adapter's selected-matrix result through its API."""
    parameters = dict(width=.5e-3, plane_spacing=1e-3, eps_r=4)
    mesh = dict(edge_size=5e-6, far_size=.5e-3, grade=.2)
    def run(payload):
        request('/api/job', payload)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            value = json.loads(request('/api/job'))
            if value['status'] != 'running':
                break
            time.sleep(.2)
        assert value['status'] == 'complete', value
        return value['result']
    nominal = run(dict(action='analyze', template='stripline', parameters=parameters, mesh=mesh))
    result = run(dict(action='design', template='stripline', parameters=parameters, mesh=mesh,
        design=dict(bounds=[.25e-3,.75e-3],target=nominal['line']['z0'],tolerance=1.)))
    assert result['design']['width'] == parameters['width']
    assert result['line'] == nominal['line']
    assert result['document'] == nominal['document']
    assert abs(result['design']['residual']) <= 1.
    assert abs(result['design']['refined_residual']) <= 1.
    assert result['design']['history'][-1]['stage'] == 'refinement'
    return result


def exercise(source, report):
    report['phase'] = 'prepare temporary directory'
    with candidate_directory(report) as folder:
        directory = Path(folder)
        exe = directory / source.name
        shutil.copy2(source, exe)
        temp = directory / 'temporary'
        temp.mkdir()
        env = {**os.environ, 'TEMP': str(temp), 'TMP': str(temp), 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'}
        # Remove Python environment hooks: the candidate must carry its runtime.
        env.pop('PYTHONPATH', None); env.pop('PYTHONHOME', None)
        report['phase'] = 'startup'
        started = time.monotonic()
        process = subprocess.Popen([str(exe), '--no-browser'], cwd=directory,
            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        lines = queue.Queue()
        collector = threading.Thread(target=capture_output, args=(process.stdout, lines, report), daemon=True)
        collector.start()
        request = None
        try:
            deadline = started + 120
            url = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Executable stopped before serving the UI.')
                try:
                    line = lines.get(timeout=1)
                except queue.Empty:
                    continue
                match = STARTUP_URL.search(line)
                if match:
                    url, token = match.groups()
                    break
            if url is None:
                raise RuntimeError('Executable startup exceeded 120 seconds.')
            report['startup_seconds'] = time.monotonic() - started
            def request(path, data=None):
                payload = None if data is None else json.dumps(data).encode()
                req = Request(url + path, data=payload, headers={'Authorization': 'Bearer '+token,
                    'Content-Type': 'application/json'})
                with urlopen(req, timeout=30) as response:
                    return response.read()
            report['phase'] = 'assets and notices'
            assert b'TRANSMISSION LINE DESIGN' in request('/')
            assert b'CPython' in request('/notices.txt')
            assert b'GEOS' in request('/notices.txt')
            assert b'Input JSON' in request('/saved.html')
            report['build'] = json.loads(request('/build-info.json'))
            report['phase'] = 'oversized request response'
            report['rejected_request'] = check_rejected_request(url, token)
            assert json.loads(request('/api/job'))['status'] == 'idle'
            for template, extra in [('microstrip', {}), ('stripline', {}), ('offset_stripline', {'trace_height':.3e-3}), ('coupled_microstrip', {'gap': .2e-3}), ('coupled_stripline', {'gap': .2e-3}), ('grounded_coplanar', {'gap': .2e-3, 'ground_width': 1e-3}), ('coupled_grounded_coplanar', {'gap':.3e-3, 'ground_gap':.2e-3, 'ground_width':1e-3}), ('coupled_coated_microstrip', {'gap':.3e-3, 'coating_height':.1e-3, 'coating_eps_r':3.5}), ('coated_grounded_coplanar', {'gap':.2e-3, 'ground_width':1e-3, 'coating_height':.1e-3, 'coating_eps_r':3.5}), ('coupled_coated_grounded_coplanar', {'gap':.3e-3, 'ground_gap':.2e-3, 'ground_width':1e-3, 'coating_height':.1e-3, 'coating_eps_r':3.5})]:
                report['phase'] = 'analyze ' + template
                parameters = {'width': .5e-3, 'eps_r': 4,
                    'plane_spacing' if template in ('stripline', 'coupled_stripline', 'offset_stripline') else 'substrate_height': 1e-3, **extra}
                request('/api/job', {'action': 'analyze', 'template': template, 'parameters': parameters,
                    'mesh': {'edge_size': 5e-6, 'far_size': .5e-3, 'grade': .2}})
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    result = json.loads(request('/api/job'))
                    if result['status'] != 'running':
                        break
                    time.sleep(.2)
                assert result['status'] == 'complete', result
                line = result['result']['line']
                assert all(line['C'][i][i] > 0 for i in range(len(line['names'])))
                if template == 'stripline':
                    assert abs(line['z0'] - 50.216) < .6
                report['cases'].append({'template': template, 'line': line})
            report['phase'] = 'width target with selected matrices'
            report['width_goal'] = check_width_goal(request)
            report['phase'] = 'saved analysis'
            saved = dict(schema='sipi.lumped-network/1', frequency_hz=[0, 1e9],
                branch=dict(resistance_ohms=10., inductance_h=2e-9, capacitance_f=None),
                placement='series', reference_ohms=[50., 50.], port_names=['near', 'far'])
            request('/api/job', dict(action='saved-analyze', text=json.dumps(saved)))
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                result = json.loads(request('/api/job'))
                if result['status'] != 'running':
                    break
                time.sleep(.2)
            assert result['status'] == 'complete', result
            execution = result['result']['execution']
            assert execution['status'] == 'complete'
            assert abs(execution['result']['network']['s']['real'][0][1][0]-100/110) < 1e-12
            assert result['result']['engine']['build'] == report['build']
            report['saved_analysis'] = execution
            report['phase'] = 'saved bounded 3D capacitance'
            from galerkin.mesh3d import box_mesh
            from sipi.capacitance3d_document import Capacitance3DDocument
            mesh = box_mesh(.004, .003, .002, 2, 2, 2)
            doc = Capacitance3DDocument(mesh, eps_r=3.8,
                conductors={'top': mesh.boundary['z1']}, ground=mesh.boundary['z0'])
            request('/api/job', dict(action='saved-analyze', text=doc.dumps()))
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                result = json.loads(request('/api/job'))
                if result['status'] != 'running':
                    break
                time.sleep(.2)
            assert result['status'] == 'complete', result
            execution = result['result']['execution']
            assert execution['status'] == 'complete' and execution['input'] == doc.to_dict()
            assert execution['result']['model'] == 'bounded-static-3d'
            exact = 8.8541878188e-12*3.8*.004*.003/.002
            assert abs(execution['result']['capacitance_f'][0][0]/exact-1) < 1e-11
            report['saved_capacitance3d'] = execution
            report['phase'] = 'recorded execution and project history'
            from sipi.execution_record import SavedExecutionRecord
            from sipi.project import SavedProject
            def job(data):
                request('/api/job', data)
                until = time.monotonic() + 120
                while time.monotonic() < until:
                    reply = json.loads(request('/api/job'))
                    if reply['status'] != 'running':
                        assert reply['status'] == 'complete', reply
                        return reply['result']
                    time.sleep(.2)
                raise RuntimeError('Recorded execution exceeded the smoke deadline.')
            raw = json.dumps(saved)
            first = job(dict(action='saved-record', text=raw))
            second = job(dict(action='saved-record', text=raw))
            a = SavedExecutionRecord.loads(first['record_text'])
            b = SavedExecutionRecord.loads(second['record_text'])
            assert a.run_id != b.run_id and a.receipt == b.receipt
            assert a.prepare().source_text == raw
            assert first['runtime_manifest_text'] == second['runtime_manifest_text']
            # Independently inspect the live extracted files from the external
            # test process. Do not infer them from the provider's declarations.
            build_files = list(temp.rglob('ui/build-info.json'))
            assert len(build_files) == 1, build_files
            bundle = build_files[0].parent.parent
            checked = verify_recording(first, bundle, report['build'], report['saved_analysis'])
            project = job(dict(action='project-create', text=raw, project_id='smoke',
                               design_id='a', title='Recorded smoke', label='A'))
            attached = job(dict(action='project-attach', project_text=project['project_text'],
                                design_id='a', record_text=first['record_text'], select=True))
            assert SavedProject.loads(attached['project_text']).current_record('a').dumps() == a.dumps()
            looked = job(dict(action='project-record', project_text=attached['project_text'],
                              design_id='a', run_id=a.run_id))
            assert looked['selected'] is True and looked['matches_current'] is True
            assert looked['record_text'] == first['record_text']
            report['recorded_execution'] = dict(record_text=first['record_text'],
                runtime_manifest_text=first['runtime_manifest_text'], second_run_id=b.run_id,
                **checked, project_roundtrip=True)
            report['phase'] = 'recorded goal mesh-budget failure'
            from sipi import ImpedanceDesignDocument
            goal = ImpedanceDesignDocument('stripline',
                dict(width=.3e-3, plane_spacing=1e-3, eps_r=4, box_width=6e-3),
                variable='width', bounds=[.2e-3, .4e-3], target=50., tolerance=.1,
                mesh=dict(edge_size=1e-12, far_size=.2e-3, grade=.2))
            failed = job(dict(action='saved-record', text=goal.dumps()))
            record = SavedExecutionRecord.loads(failed['record_text'])
            result = record.receipt['execution']; error = result['error']
            assert result['status'] == 'failed' and result['result'] is None
            assert error['type'] == 'GoalMeshSizeLimitError' and error['cause_type'] == 'MeshSizeLimitError'
            assert error['stage'] == 'search' and error['attempts'] == 1 and error['history'] == []
            assert error['parameter'] == .0002 and error['input']['traces'][0]['width'] == .0002
            assert error['input']['mesh'] == dict(edge_size=1e-12, far_size=.0002, grade=.2, min_angle=28.)
            assert error['material_evaluation'] is None and '300000 points' in error['message']
            verify_recording(failed, bundle, report['build'], result)
            project = job(dict(action='project-create', text=goal.dumps(), project_id='failed-goal',
                               design_id='a', title='Failed goal', label='A'))
            attached = job(dict(action='project-attach', project_text=project['project_text'],
                                design_id='a', record_text=failed['record_text'], select=True))
            assert SavedProject.loads(attached['project_text']).current_record('a').dumps() == record.dumps()
            report['goal_mesh_failure'] = dict(record_text=failed['record_text'], project_roundtrip=True)
            # The failed result must not poison the next valid calculation.
            assert job(dict(action='saved-analyze', text=raw))['execution'] == report['saved_analysis']
            report['phase'] = 'shutdown'
            request('/api/shutdown', {})
            process.wait(timeout=20)
            assert process.returncode == 0, process.returncode
            report['phase'] = 'temporary file cleanup'
            report['temporary_entries_after_exit'] = [str(path.relative_to(temp)) for path in temp.rglob('*')]
            assert not report['temporary_entries_after_exit'], report['temporary_entries_after_exit']
        finally:
            unwinding = sys.exc_info()[0] is not None
            try:
                stop_candidate(process, request, report)
            except Exception as exc:
                report['process_cleanup_error'] = {'type': type(exc).__name__, 'message': str(exc)}
                if not unwinding:
                    raise
            report['process_returncode'] = process.returncode
            collector.join(timeout=5)
            report['process_output_complete'] = not collector.is_alive()
            if not collector.is_alive():
                process.stdout.close()

    report['phase'] = 'complete'
    report['status'] = 'passed'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('executable', type=Path)
    args = parser.parse_args()
    source = args.executable.resolve()
    report = {'status': 'failed', 'phase': 'inspect executable', 'cases': [],
              'scope': 'Windows runner process/API smoke; isolated-network and interactive-desktop acceptance remain separate'}
    try:
        report['executable_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        report['bytes'] = source.stat().st_size
        exercise(source, report)
    except Exception as exc:
        report['status'] = 'failed'
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        source.with_name('smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        if report['status'] == 'failed' and report.get('process_output'):
            print(report['process_output'], file=sys.stderr)
    print(json.dumps({key: report[key] for key in ('status', 'bytes', 'startup_seconds')}))


if __name__ == '__main__':
    main()
