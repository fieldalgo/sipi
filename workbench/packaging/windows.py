"""Build a Windows x64 one-file candidate and preserve its component inventory."""

import hashlib
import importlib
from importlib import metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

from notice_inventory import supplemental_notices

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / '.validation' / 'sipi-windows'


def wheel_inventory(directory):
    """Audit the exact installed first-party inputs before freezing anything."""
    sys.path.insert(0, str(ROOT / 'tools'))
    from verify_install import compare_payload
    result = []
    for name in ('sipi', 'galerkin', 'meshine'):
        paths = list(Path(directory).glob(name + '-*.whl'))
        if len(paths) != 1:
            raise ValueError(f'Expected exactly one {name} wheel in {directory}')
        dist = metadata.distribution(name)
        installation = Path(dist.locate_file('')).resolve()
        origin = Path(importlib.import_module(name).__file__).resolve()
        if not installation.is_relative_to(Path(sys.prefix).resolve()) or not origin.is_relative_to(installation / name):
            raise ValueError(f'{name}: installed import is shadowed or outside this environment')
        checked = compare_payload(paths[0], installation, name=name, version=dist.version)
        result.append(dict(name=name, version=dist.version, wheel=paths[0].name,
            sha256=hashlib.sha256(paths[0].read_bytes()).hexdigest(), files_checked=checked))
    return result


def main():
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise SystemExit('Build with CPython 3.12 on Windows x64; cross-compilation is not claimed.')
    if sys.version_info[:3] != (3, 12, 14):
        raise SystemExit('Use the reviewed CPython 3.12.14 build environment.')
    for line in (ROOT / 'workbench/packaging/requirements-windows.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        name, expected = line.split('==')
        if metadata.version(name) != expected:
            raise SystemExit(f'Use the reviewed build pin: {name}=={expected}')
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise SystemExit('Preserve the previous build evidence and use a fresh checkout/output directory.')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    runtime = ['sipi', 'galerkin', 'meshine', 'numpy', 'scipy', 'shapely', 'array-api-compat']
    build = ['Nuitka', 'ordered-set', 'zstandard', 'pefile', 'setuptools', 'wheel']
    inventory = {'python': sys.version, 'platform': platform.platform(),
                 'engine_commit': (ROOT / 'workbench/packaging/engine-ref.txt').read_text().strip(),
                 'runtime': {}, 'build_tools': {}, 'release_status': 'internal validation candidate'}
    inventory['source_wheels'] = wheel_inventory(ROOT / '.validation' / 'wheels')
    inventory['shared_commit'] = json.loads((ROOT / 'dependencies.json').read_text())['development_source']['commit']
    inventory['workbench_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    import os
    vswhere = Path(os.environ['ProgramFiles(x86)']) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    installations = json.loads(subprocess.check_output([str(vswhere), '-latest', '-products', '*',
        '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-format', 'json'], text=True))
    if not installations or not installations[0]['installationVersion'].startswith('17.'):
        raise SystemExit('Use the reviewed Visual Studio 2022 toolchain; no compiler download is permitted.')
    inventory['compiler_installation'] = installations[0]
    notices = ['FieldAlgo SIPI offline workbench — third-party notices\n']
    for name in runtime + build:
        dist = metadata.distribution(name)
        inventory['runtime' if name in runtime else 'build_tools'][name] = {
            'version': dist.version, 'license': dist.metadata.get('License-Expression') or dist.metadata.get('License'),
            'files': []}
        for entry in dist.files or []:
            path = Path(dist.locate_file(entry))
            if not path.is_file():
                continue
            if name in runtime and path.suffix.lower() in ('.dll', '.pyd'):
                inventory['runtime'][name]['files'].append({'name': str(entry), 'size': path.stat().st_size,
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            label = path.name.lower()
            if any(word in label for word in ('license', 'copying', 'notice')) and path.suffix.lower() not in ('.py', '.pyc'):
                try:
                    text = path.read_text(encoding='utf-8')
                except UnicodeError:
                    continue
                notices.append(f'\n--- {name} {dist.version}: {entry} ---\n{text}\n')
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.is_file():
        raise SystemExit('Python redistribution license is missing.')
    notices.append('\n--- CPython and included components ---\n' + python_license.read_text(encoding='utf-8'))
    # Nuitka's unmodified onefile runtime uses its bundled zstd; retain that BSD notice.
    import nuitka
    zstd_notice = Path(nuitka.__file__).parent / 'build/inline_copy/zstd/LICENSE.txt'
    if not zstd_notice.is_file():
        raise SystemExit('Nuitka onefile zstd notice is missing.')
    notices.append('\n--- Nuitka bundled zstd ---\n' + zstd_notice.read_text(encoding='utf-8'))
    extra_notices, components = supplemental_notices('windows')
    notices.extend(extra_notices)
    inventory['supplemental_components'] = components
    notice_path = OUTPUT / 'notices.txt'
    notice_path.write_text('\n'.join(notices), encoding='utf-8')
    build_info = OUTPUT / 'build-info.json'
    build_info.write_text(json.dumps({key: inventory[key] for key in
        ('engine_commit', 'workbench_commit', 'shared_commit', 'source_wheels')}, indent=2), encoding='utf-8')
    command = [sys.executable, '-m', 'nuitka', '--mode=onefile', '--msvc=latest',
        '--experimental=force-dependencies-pefile', '--lto=no', '--jobs=2',
        '--windows-console-mode=force', '--output-filename=FieldAlgo-SIPI.exe',
        '--company-name=FieldAlgo', '--product-name=SIPI', '--file-version=0.1.0.0',
        '--product-version=0.1.0.0', '--file-description=SIPI offline cross-section workbench',
        '--include-package=sipi', '--include-package=meshine', '--include-package=galerkin', '--include-package=shapely',
        '--nofollow-import-to=pytest,matplotlib,tkinter,torch,jax,cupy,dask,IPython',
        '--include-data-dir=' + str(ROOT / 'workbench/ui') + '=ui',
        '--include-data-files=' + str(notice_path) + '=ui/notices.txt',
        '--include-data-files=' + str(build_info) + '=ui/build-info.json',
        '--output-dir=' + str(OUTPUT), '--report=' + str(OUTPUT / 'compilation.xml'),
        str(ROOT / 'workbench/desktop/main.py')]
    # No blanket download permission: MSVC and the reviewed pefile scanner are used.
    inventory['status'] = 'building'
    report_path = OUTPUT / 'inventory.json'
    report_path.write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    try:
        subprocess.run(command, check=True, stdin=subprocess.DEVNULL, cwd=ROOT)
    except Exception as exc:
        inventory.update(status='failed', error=str(exc))
        report_path.write_text(json.dumps(inventory, indent=2), encoding='utf-8')
        raise
    executable = OUTPUT / 'FieldAlgo-SIPI.exe'
    if not executable.is_file():
        raise SystemExit('Expected one-file executable was not produced.')
    inventory['executable'] = {'name': executable.name, 'bytes': executable.stat().st_size,
                             'sha256': hashlib.sha256(executable.read_bytes()).hexdigest()}
    inventory['bundled_native_files'] = []
    for path in sorted(OUTPUT.glob('*.dist/**/*')):
        if path.is_file() and path.suffix.lower() in ('.dll', '.pyd', '.exe'):
            inventory['bundled_native_files'].append({'name': str(path.relative_to(OUTPUT)),
                'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    inventory['status'] = 'built; executable smoke still required'
    report_path.write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    print(json.dumps(inventory['executable']))


if __name__ == '__main__':
    main()
