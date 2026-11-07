"""Exercise the built executable from a Unicode/space path and record startup/cleanup."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import Request, urlopen

STARTUP_URL = re.compile(r'(http://127\.0\.0\.1:\d+)/#token=([\w-]+)')


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


def exercise(source, report):
    report['phase'] = 'prepare temporary directory'
    with tempfile.TemporaryDirectory(prefix='SIPI 한글 path ') as folder:
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
            for template, extra in [('microstrip', {}), ('stripline', {}), ('coupled_microstrip', {'gap': .2e-3}), ('grounded_coplanar', {'gap': .2e-3, 'ground_width': 1e-3})]:
                report['phase'] = 'analyze ' + template
                parameters = {'width': .5e-3, 'eps_r': 4,
                    'plane_spacing' if template == 'stripline' else 'substrate_height': 1e-3, **extra}
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
            report['phase'] = 'shutdown'
            request('/api/shutdown', {})
            process.wait(timeout=20)
            assert process.returncode == 0, process.returncode
            report['phase'] = 'temporary file cleanup'
            report['temporary_entries_after_exit'] = [str(path.relative_to(temp)) for path in temp.rglob('*')]
            assert not report['temporary_entries_after_exit'], report['temporary_entries_after_exit']
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=10)
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
