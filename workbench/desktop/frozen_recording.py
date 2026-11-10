"""Host-declared snapshots of the reviewed Windows onefile execution payload."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys

if __package__:
    from .recording import _admit, _record_result
else:
    from recording import _admit, _record_result


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate frozen build-info key.')
        result[key] = value
    return result


def _reject(value):
    raise ValueError('Nonfinite frozen build-info number.')


def _context():
    compiled = globals().get('__compiled__')
    if (compiled is None or sys.platform != 'win32'
            or platform.python_version() != '3.13.17'
            or platform.machine().lower() not in {'amd64', 'x86_64'}
            or tuple(getattr(compiled, key, None) for key in ('major', 'minor', 'micro')) != (2, 8, 10)
            or getattr(compiled, 'standalone', False) is not True
            or getattr(compiled, 'onefile', False) is not True):
        raise ValueError('Frozen recording requires the reviewed Windows x64 onefile runtime.')
    executable = Path(sys.executable)
    # Nuitka's standalone sys.executable identifies the unpacked binary. Its
    # containing_dir/argv[0] may identify the outer launcher and are not used.
    root = Path(__file__).parent
    if (not executable.is_absolute() or not root.is_absolute()
            or executable.suffix.lower() != '.exe'
            or executable.parent != root or executable.resolve().parent != root.resolve()):
        raise ValueError('Frozen helper and executing payload must share the bundle root.')
    return root, executable.name


def _regular(path):
    result = path.lstat()
    if stat.S_ISLNK(result.st_mode) or getattr(result, 'st_file_attributes', 0) & 0x400:
        raise ValueError('Frozen bundle links and reparse points are not supported.')
    return result


def _files(root, max_entries):
    _regular(root)
    pending = [root]
    result = []
    count = 0
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                count += 1
                if count > max_entries:
                    raise ValueError('Frozen bundle exceeds the entry limit.')
                path = Path(entry.path)
                relative = path.relative_to(root)
                if len(relative.parts) > 64 or len(relative.as_posix()) > 1024:
                    raise ValueError('Frozen bundle path exceeds the limit.')
                info = _regular(path)
                if stat.S_ISDIR(info.st_mode):
                    pending.append(path)
                elif stat.S_ISREG(info.st_mode):
                    result.append(relative.as_posix())
                else:
                    raise ValueError('Frozen bundle contains a nonregular entry.')
    return sorted(result)


def _snapshot(path, remaining):
    before = _regular(path)
    if not stat.S_ISREG(before.st_mode) or before.st_size > remaining[0]:
        raise ValueError('Frozen bundle exceeds the byte limit or contains a nonregular file.')
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(1024*1024):
            size += len(chunk)
            if size > remaining[0]:
                raise ValueError('Frozen bundle exceeds the byte limit.')
            digest.update(chunk)
    after = _regular(path)
    identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    if size != before.st_size or identity(before) != identity(after):
        raise ValueError('Frozen bundle file changed during capture.')
    remaining[0] -= size
    return dict(bytes=size, sha256=digest.hexdigest())


def _build(text):
    data = json.loads(text, object_pairs_hook=_unique, parse_constant=_reject)
    if not isinstance(data, dict) or set(data) != {'engine_commit', 'workbench_commit', 'shared_commit', 'source_wheels'}:
        raise ValueError('Frozen build-info is incomplete.')
    for key in ('engine_commit', 'workbench_commit', 'shared_commit'):
        if not isinstance(data[key], str) or re.fullmatch(r'[0-9a-f]{40}', data[key]) is None:
            raise ValueError('Frozen source commits must be full hashes.')
    rows = data['source_wheels']
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError('Frozen build-info needs three first-party source wheels.')
    names = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'name', 'version', 'wheel', 'sha256', 'files_checked'}
                or not isinstance(row['name'], str) or row['name'] not in {'sipi', 'galerkin', 'meshine'}
                or row['name'] in names or not isinstance(row['version'], str)
                or re.fullmatch(r'[A-Za-z0-9+._-]{1,128}', row['version']) is None
                or row['wheel'] != row['name']+'-'+row['version']+'-py3-none-any.whl'
                or not isinstance(row['sha256'], str) or re.fullmatch(r'[0-9a-f]{64}', row['sha256']) is None
                or type(row['files_checked']) is not int or row['files_checked'] < 1):
            raise ValueError('Frozen source-wheel descriptor is invalid.')
        names.add(row['name'])
    import sipi
    if next(row['version'] for row in rows if row['name'] == 'sipi') != sipi.__version__:
        raise ValueError('Frozen SIPI version differs from its build-info.')
    return data


def capture_frozen_artifacts(*, max_entries=20000, max_bytes=512*1024*1024):
    """Hash the unpacked payload, not the compressed launcher or source wheels.

    Bounds include every directory entry and regular file, including UI and
    notices. System DLLs outside this directory and loaded memory are outside
    this host-declared file snapshot. No caller-provided paths are accepted.
    """
    for value in (max_entries, max_bytes):
        if type(value) is not int or value < 1:
            raise ValueError('Frozen snapshot limits must be positive integers.')
    root, executable = _context()
    paths = _files(root, max_entries)
    if not {executable, 'ui/build-info.json', 'ui/notices.txt'} <= set(paths):
        raise ValueError('Frozen bundle omits its executing payload, build-info or notices.')
    remaining = [max_bytes]
    files = [dict(path=name, **_snapshot(root/name, remaining)) for name in paths]
    build_row = next(row for row in files if row['path'] == 'ui/build-info.json')
    if build_row['bytes'] > 1024*1024:
        raise ValueError('Frozen build-info exceeds 1 MiB.')
    with (root/'ui/build-info.json').open('rb') as stream:
        raw = stream.read(1024*1024+1)
    if len(raw) != build_row['bytes'] or hashlib.sha256(raw).hexdigest() != build_row['sha256']:
        raise ValueError('Frozen build-info changed during capture.')
    build = _build(raw.decode('utf-8'))
    if _files(root, max_entries) != paths:
        raise ValueError('Frozen bundle entries changed during capture.')
    manifest = dict(schema='sipi.frozen-runtime/1', policy='unpacked-bundle-files/1',
                    scope='host-declared-unpacked-payload', python_version=platform.python_version(),
                    nuitka_version='2.8.10', platform='Windows', machine='x86_64',
                    executable=executable, build=build, files=files)
    text = _canonical(manifest)
    if len(text.encode('utf-8')) > 8*1024*1024:
        raise ValueError('Frozen runtime manifest exceeds 8 MiB.')
    payload = next(row for row in files if row['path'] == executable)
    version = next(row['version'] for row in build['source_wheels'] if row['name'] == 'sipi')
    return dict(manifest_text=text, artifacts=[
        dict(component='sipi', version=version, kind='executable', sha256=payload['sha256']),
        dict(component='sipi-frozen-runtime', version='1', kind='runtime',
             sha256=hashlib.sha256(text.encode('utf-8')).hexdigest())])


def run_recorded_frozen(request):
    _admit(request)
    before = capture_frozen_artifacts()
    receipt = request.run()
    after = capture_frozen_artifacts()
    if before != after:
        raise RuntimeError('Frozen bundle snapshot changed during execution; no record was created.')
    return _record_result(request, receipt, before['artifacts'], before['manifest_text'])
