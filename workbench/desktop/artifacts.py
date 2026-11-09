"""Snapshot installed distribution files; never claim an original wheel hash."""
import hashlib
import importlib
from importlib import metadata
import json
from pathlib import Path, PurePosixPath
import platform
import re

COMPONENTS = (('sipi', 'sipi'), ('galerkin', 'galerkin'), ('meshine', 'meshine'),
              ('numpy', 'numpy'), ('scipy', 'scipy'), ('shapely', 'shapely'),
              ('array-api-compat', 'array_api_compat'))
_BOOKKEEPING = {'RECORD', 'INSTALLER', 'REQUESTED', 'direct_url.json'}
_MODULE_SUFFIXES = {'.py', '.so', '.pyd', '.dll', '.dylib'}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False)


def _digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _excluded(path):
    return ('..' in path.parts or '__pycache__' in path.parts
            or path.suffix in {'.pyc', '.pyo'}
            or (any(p.endswith('.dist-info') for p in path.parts)
                and path.name in _BOOKKEEPING))


def _file_snapshot(path, budget):
    before = path.stat()
    if not path.is_file() or before.st_size > budget[0]:
        raise ValueError('Installed artifact file is missing, not regular, or exceeds the byte limit.')
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(1024*1024):
            size += len(chunk)
            if size > budget[0]:
                raise ValueError('Installed artifact files exceed the byte limit.')
            digest.update(chunk)
    after = path.stat()
    identity = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    if size != before.st_size or identity(before) != identity(after):
        raise ValueError('Installed artifact file changed during capture.')
    budget[0] -= size
    return dict(bytes=size, sha256=digest.hexdigest())


def capture_installed_artifacts(*, max_files=20000, max_bytes=512*1024*1024):
    """Return deterministic payload manifests and host-declared runtime digests.

    Only the fixed installed distributions are inventoried. Source shadowing,
    missing payloads and unlisted package modules fail instead of manufacturing
    provenance. Cache files, installer bookkeeping and scripts outside the
    distribution root are excluded by the versioned selection policy.

    This is a file snapshot, not a wheel hash, signature, memory attestation or
    complete Python/OS native-library inventory. No files are written. Frozen
    executables and browser runtimes require their own host provenance path.
    """
    for name, value in (('max_files', max_files), ('max_bytes', max_bytes)):
        if type(value) is not int or value < 1:
            raise ValueError(name + ' must be a positive integer.')
    remaining = [max_bytes]
    count = 0
    components = []
    for name, module_name in COMPONENTS:
        dist = metadata.distribution(name)
        version = dist.version
        if not isinstance(version, str) or re.fullmatch(r'[A-Za-z0-9+._-]{1,128}', version) is None:
            raise ValueError('Installed artifact version cannot be represented in a record.')
        entries = dist.files
        if not entries:
            raise ValueError('Installed artifact has no distribution file inventory: ' + name)
        module = importlib.import_module(module_name)
        origin = getattr(module, '__file__', None)
        if not origin:
            raise ValueError('Installed artifact has no inspectable module origin: ' + name)
        origin = Path(origin).resolve()
        files = []
        listed = set()
        seen = set()
        origin_path = None
        for entry in entries:
            count += 1
            if count > max_files:
                raise ValueError('Installed artifact inventory exceeds the file limit.')
            raw = str(entry)
            path = PurePosixPath(raw)
            if (not raw or path.is_absolute() or ':' in raw or '\\' in raw
                    or str(path) != raw or raw in seen):
                raise ValueError('Installed artifact inventory has invalid or duplicate paths.')
            seen.add(raw)
            if _excluded(path):
                continue
            local = Path(dist.locate_file(entry))
            resolved = local.resolve()
            listed.add(resolved)
            if resolved == origin:
                origin_path = raw
            files.append(dict(path=raw, **_file_snapshot(local, remaining)))
        if origin_path != module_name + '/__init__.py':
            raise ValueError('Imported module is not in its installed artifact inventory: ' + name)
        scanned = 0
        for path in origin.parent.rglob('*'):
            scanned += 1
            if scanned > max_files:
                raise ValueError('Installed package scan exceeds the file limit.')
            if ('__pycache__' not in path.parts and path.suffix in _MODULE_SUFFIXES
                    and path.is_file() and path.resolve() not in listed):
                raise ValueError('Installed package contains an unlisted module: ' + name)
        components.append(dict(schema='sipi.installed-component/1', policy='distribution-files/1',
            component=name, version=version, import_path=origin_path,
            files=sorted(files, key=lambda row: row['path'])))
    components.sort(key=lambda item: item['component'])
    manifest = dict(schema='sipi.installed-runtime/1', scope='installed-distribution-files',
                    python_version=platform.python_version(), platform=platform.system(),
                    machine=platform.machine(), components=components)
    declarations = [dict(component=item['component'], version=item['version'], kind='runtime',
                         sha256=_digest(_canonical(item))) for item in components]
    return dict(manifest_text=_canonical(manifest), artifacts=declarations)
