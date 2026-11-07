"""Stage an unmodified, hash-pinned Pyodide preview without changing deployment routes."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from urllib.request import urlopen
import zipfile

from notice_inventory import supplemental_notices

ROOT = Path(__file__).resolve().parents[2]
VERSION = '0.29.5'
ARCHIVE = 'https://registry.npmjs.org/pyodide/-/pyodide-0.29.5.tgz'
ARCHIVE_HASH = '6749b10ee515a1458ecea36d860c8ce2a48366e85b3f92d749ad1840e4aff181'
CDN = 'https://cdn.jsdelivr.net/pyodide/v0.29.5/full/'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fetch(url, expected=None):
    with urlopen(url, timeout=90) as response:
        data = response.read()
    if expected is not None and digest(data) != expected:
        raise ValueError('Downloaded asset hash mismatch: ' + url)
    return data


def notices_from_zip(data, name):
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as wheel:
        for item in wheel.namelist():
            if not item.endswith('/') and any(word in Path(item).name.lower() for word in ('license', 'copying', 'notice')):
                try:
                    text = wheel.read(item).decode('utf-8')
                except UnicodeError:
                    continue
                out.append(f'\n--- {name}: {item} ---\n{text}\n')
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--shared', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / '.validation/sipi-web')
    args = parser.parse_args()
    engine = args.engine.resolve()
    expected = (ROOT / 'workbench/packaging/engine-ref.txt').read_text().strip()
    actual = subprocess.check_output(['git', '-C', str(engine), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != expected or subprocess.check_output(['git', '-C', str(engine), 'status', '--porcelain'], text=True).strip():
        raise SystemExit('Use a clean engine checkout at the exact engine-ref.txt commit.')
    shared = args.shared.resolve()
    shared_ref = json.loads((engine / 'dependencies.json').read_text())['development_source']['commit']
    if (subprocess.check_output(['git', '-C', str(shared), 'rev-parse', 'HEAD'], text=True).strip() != shared_ref
            or subprocess.check_output(['git', '-C', str(shared), 'status', '--porcelain'], text=True).strip()):
        raise SystemExit('Use a clean shared-package checkout at dependencies.json development_source.commit.')
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit('Use a new or empty output directory to avoid mixing runtime versions.')
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'workbench/ui', output, dirs_exist_ok=True)
    for page in output.glob('*.html'):
        page.write_text(page.read_text().replace('data-runtime="local"', 'data-runtime="browser"'), encoding='utf-8')
    manifest = {'pyodide': VERSION, 'engine_commit': expected, 'files': {}, 'wheels': [], 'packages': {},
                'source': 'https://github.com/pyodide/pyodide/tree/0.29.5',
                'runtime_archive_sha256': ARCHIVE_HASH, 'status': 'local validation candidate'}
    manifest['shared_commit'] = shared_ref
    def put(relative, data, source):
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        manifest['files'][relative] = {'sha256': digest(data), 'bytes': len(data), 'source': source}
    archive = tarfile.open(fileobj=io.BytesIO(fetch(ARCHIVE, ARCHIVE_HASH)))
    runtime_files = ['pyodide.js', 'pyodide.asm.js', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json']
    for name in runtime_files:
        put('runtime/' + name, archive.extractfile('package/' + name).read(), ARCHIVE)
    lock = json.loads((output / 'runtime/pyodide-lock.json').read_text())
    manifest['python_abi'] = lock['info']
    package_names = set()
    def include(name):
        if name in package_names:
            return
        package_names.add(name)
        for dependency in lock['packages'][name]['depends']:
            include(dependency)
    include('numpy'); include('scipy'); include('shapely')
    notices = [f'SIPI browser preview\nPyodide {VERSION}, MPL-2.0, unmodified separate files.\nSource: {manifest["source"]}\n']
    license_url = 'https://raw.githubusercontent.com/pyodide/pyodide/0.29.5/LICENSE'
    license_data = fetch(license_url)
    put('runtime/LICENSE-PYODIDE.txt', license_data, license_url)
    notices.append(license_data.decode())
    python_source = 'https://raw.githubusercontent.com/python/cpython/v3.13.2/LICENSE'
    python_license = fetch(python_source)
    put('runtime/LICENSE-PYTHON.txt', python_license, python_source)
    notices.append('\n--- CPython 3.13.2 and included notices ---\n' + python_license.decode())
    for name in sorted(package_names):
        item = lock['packages'][name]
        data = fetch(CDN + item['file_name'], item['sha256'])
        put('runtime/' + item['file_name'], data, CDN + item['file_name'])
        manifest['packages'][name] = {'version': item['version'], 'sha256': item['sha256'], 'file_name': item['file_name']}
        notices.extend(notices_from_zip(data, name))
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            manifest['packages'][name]['native_files'] = [path for path in package.namelist() if path.endswith(('.so', '.wasm', '.a'))]
    # Pure Python dependency, pinned independently of the browser's numerical ABI.
    info = json.loads(fetch('https://pypi.org/pypi/array-api-compat/1.16.0/json'))
    item = next(row for row in info['urls'] if row['filename'].endswith('py3-none-any.whl'))
    compat = fetch(item['url'], item['digests']['sha256'])
    put('wheels/' + item['filename'], compat, item['url'])
    manifest['wheels'].append('wheels/' + item['filename'])
    notices.extend(notices_from_zip(compat, 'array-api-compat 1.16.0'))
    # Invoke the already installed, reviewed build backend; no implicit installation.
    wheel_dir = output / 'wheels'
    for name in ('galerkin', 'meshine', 'sipi'):
        code = 'import setuptools.build_meta as b; b.build_wheel(' + repr(str(wheel_dir)) + ')'
        source_root = engine if name == 'sipi' else shared / 'packages' / name
        subprocess.run([sys.executable, '-c', code], cwd=source_root, check=True, stdout=subprocess.DEVNULL)
        matches = list(wheel_dir.glob(name + '-*.whl'))
        if len(matches) != 1:
            raise ValueError('Expected one built wheel for ' + name)
        path = matches[0]
        data = path.read_bytes()
        with zipfile.ZipFile(path) as wheel:
            descriptor = next(p for p in wheel.namelist() if p.endswith('.dist-info/WHEEL'))
            if b'Root-Is-Purelib: true' not in wheel.read(descriptor) or any('.data/' in p for p in wheel.namelist()):
                raise ValueError('Browser loader requires a pure root-layout wheel: ' + name)
        relative = 'wheels/' + path.name
        source_url = ('https://github.com/fieldalgo/sipi/tree/' + expected if name == 'sipi'
                      else 'https://github.com/fieldalgo/openphysics/tree/' + shared_ref + '/packages/' + name)
        put(relative, data, source_url)
        manifest['wheels'].append(relative)
        notices.extend(notices_from_zip(data, name))
    extra_notices, components = supplemental_notices('browser')
    notices.extend(extra_notices)
    manifest['supplemental_components'] = components
    manifest['redistribution_review'] = 'incomplete; internal validation only'
    put('engine.py', (ROOT / 'workbench/desktop/engine.py').read_bytes(), 'first-party adapter')
    put('notices.txt', '\n'.join(notices).encode('utf-8'), 'collected upstream notices')
    manifest['staged_bytes'] = sum(path.stat().st_size for path in output.rglob('*') if path.is_file())
    (output / 'runtime-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(output), 'bytes': manifest['staged_bytes'],
        'packages': {name: item['version'] for name, item in manifest['packages'].items()}, 'abi': manifest['python_abi']}))


if __name__ == '__main__':
    main()
