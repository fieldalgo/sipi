"""Records tied to browser source artifacts checked by the loading host."""
from dataclasses import dataclass, field
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import re

if __package__:
    from .recording import _admit, _record_result
else:
    from recording import _admit, _record_result

_HELPERS = ('engine.py', 'artifacts.py', 'recording.py', 'browser_recording.py')
_RUNTIME = ('pyodide.js', 'pyodide.asm.js', 'pyodide.asm.wasm', 'python_stdlib.zip',
            'pyodide-lock.json', 'LICENSE-PYODIDE.txt', 'LICENSE-PYTHON.txt')
_PURE = {'sipi', 'galerkin', 'meshine', 'array-api-compat'}
_NUMERICAL = {'numpy', 'scipy', 'shapely'}
_VERSIONS = dict(sipi='0.1.0', galerkin='0.0.2', meshine='0.0.2',
                 numpy='2.2.5', scipy='1.14.1', shapely='2.0.7', **{'array-api-compat': '1.16.0'})
_PATH = re.compile(r'(?:runtime|wheels)/[A-Za-z0-9_+.-]+|[a-z_]+\.py|notices\.txt')


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate browser manifest key.')
        result[key] = value
    return result


def _reject(value):
    raise ValueError('Nonfinite browser manifest number.')


def _helpers(files):
    for name in _HELPERS:
        payload = (Path(__file__).resolve().parent/name).read_bytes()
        if (len(payload) != files[name]['bytes']
                or hashlib.sha256(payload).hexdigest() != files[name]['sha256']):
            raise ValueError('Browser helper differs from its source manifest: ' + name)


def _declarations(data, text):
    required = {'pyodide', 'engine_commit', 'shared_commit', 'python_abi', 'files', 'wheels', 'packages'}
    if not isinstance(data, dict) or not required <= data.keys():
        raise ValueError('Browser source manifest is incomplete.')
    if data['pyodide'] != '0.29.5':
        raise ValueError('Use the reviewed browser runtime version.')
    for name in ('engine_commit', 'shared_commit'):
        if not isinstance(data[name], str) or re.fullmatch(r'[0-9a-f]{40}', data[name]) is None:
            raise ValueError('Browser source commits must be full hashes.')
    abi = data['python_abi']
    if (not isinstance(abi, dict) or set(abi) != {'abi_version', 'arch', 'platform', 'python'}
            or abi != dict(abi_version='2025_0', arch='wasm32', platform='emscripten_4_0_9', python='3.13.2')
            or platform.python_version() != abi['python']):
        raise ValueError('Browser Python runtime does not match the reviewed ABI.')
    files = data['files']
    if not isinstance(files, dict) or not 1 <= len(files) <= 128:
        raise ValueError('Browser manifest needs 1..128 source files.')
    total = 0
    for path, row in files.items():
        if (not isinstance(path, str) or _PATH.fullmatch(path) is None
                or any(part in {'.', '..'} for part in path.split('/'))
                or not isinstance(row, dict) or set(row) != {'bytes', 'sha256', 'source'}
                or type(row['bytes']) is not int or not 0 <= row['bytes'] <= 64*1024*1024
                or not isinstance(row['sha256'], str) or re.fullmatch(r'[0-9a-f]{64}', row['sha256']) is None
                or not isinstance(row['source'], str)):
            raise ValueError('Browser manifest contains an invalid source file.')
        total += row['bytes']
    if total > 128*1024*1024:
        raise ValueError('Browser source files exceed 128 MiB.')
    required_files = {*_HELPERS, *('runtime/'+name for name in _RUNTIME), 'notices.txt'}
    if not required_files <= files.keys():
        raise ValueError('Browser manifest omits required runtime or helper files.')
    wheels = data['wheels']
    if not isinstance(wheels, list) or len(wheels) != 4 or any(not isinstance(p, str) for p in wheels):
        raise ValueError('Browser manifest needs four pure source wheels.')
    rows = []
    seen = set()
    for path in wheels:
        match = re.fullmatch(r'wheels/([a-z0-9_]+)-([A-Za-z0-9+._]+)-py3-none-any\.whl', path)
        if match is None or path not in files:
            raise ValueError('Browser pure wheel path is invalid.')
        name, version = match.groups()
        name = name.replace('_', '-')
        if name not in _PURE or name in seen or _VERSIONS[name] != version or metadata.version(name) != version:
            raise ValueError('Browser pure wheel does not match the loaded distribution.')
        seen.add(name)
        rows.append(dict(component=name, version=version, kind='wheel', sha256=files[path]['sha256']))
    packages = data['packages']
    if not isinstance(packages, dict) or set(packages) != _NUMERICAL:
        raise ValueError('Browser numerical package set differs from the reviewed runtime.')
    for name, row in packages.items():
        if not isinstance(row, dict) or set(row) != {'version', 'sha256', 'file_name', 'native_files'}:
            raise ValueError('Browser numerical package descriptor is incomplete.')
        version, filename = row['version'], row['file_name']
        if (not isinstance(version, str) or re.fullmatch(r'[A-Za-z0-9+._-]{1,128}', version) is None
                or not isinstance(filename, str) or filename != name+'-'+version+'-cp313-cp313-pyemscripten_2025_0_wasm32.whl'
                or _VERSIONS[name] != version or metadata.version(name) != version or 'runtime/'+filename not in files
                or files['runtime/'+filename]['sha256'] != row['sha256']
                or not isinstance(row['native_files'], list)
                or any(not isinstance(path, str) for path in row['native_files'])):
            raise ValueError('Browser numerical wheel differs from the loaded distribution or source hash.')
        rows.append(dict(component=name, version=version, kind='wheel', sha256=row['sha256']))
    rows.append(dict(component='sipi-browser-runtime', version=data['pyodide'], kind='runtime',
                     sha256=hashlib.sha256(text.encode('utf-8')).hexdigest()))
    return sorted(rows, key=lambda item: (item['component'], item['kind']))


@dataclass(frozen=True, init=False)
class BrowserSourceRecorder:
    """Use a host-checked source manifest; never accept provenance from job JSON.

    The loading host must check every declared download against its hash before
    constructing this provider. This class checks structure, loaded versions and
    helper bytes, not signatures, original wheel authenticity or loaded memory.
    """
    _manifest_text: str = field(repr=False)
    _artifacts_json: str = field(repr=False)

    def __init__(self, manifest_text):
        if not isinstance(manifest_text, str) or len(manifest_text.encode('utf-8')) > 1024*1024:
            raise ValueError('Browser manifest must be UTF-8 text up to 1 MiB.')
        data = json.loads(manifest_text, object_pairs_hook=_unique, parse_constant=_reject)
        json.dumps(data, allow_nan=False)
        rows = _declarations(data, manifest_text)
        _helpers(data['files'])
        object.__setattr__(self, '_manifest_text', manifest_text)
        object.__setattr__(self, '_artifacts_json', json.dumps(rows, sort_keys=True, separators=(',', ':')))

    def __call__(self, request):
        _admit(request)
        files = json.loads(self._manifest_text)['files']
        _helpers(files)
        receipt = request.run()
        _helpers(files)
        return _record_result(request, receipt, json.loads(self._artifacts_json), self._manifest_text)
