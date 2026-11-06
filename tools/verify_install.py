# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Match imported first-party distributions to the exact supplied wheel payloads."""
from email.parser import BytesParser
import hashlib
import importlib
from importlib import metadata
from pathlib import Path, PurePosixPath
import sys
import zipfile

PACKAGES = ('sipi', 'galerkin', 'meshine', 'simcase')


def compare_payload(wheel, installation, *, name, version):
    """Check bytes, metadata and unexpected Python sources in a pure root-layout wheel."""
    installation = Path(installation).resolve()
    checked = []
    with zipfile.ZipFile(wheel) as archive:
        entries = archive.namelist()
        descriptors = [p for p in entries if p.endswith('.dist-info/METADATA')]
        if len(descriptors) != 1 or len(entries) != len(set(entries)):
            raise ValueError(f'{name}: ambiguous wheel metadata or duplicate members')
        descriptor = BytesParser().parsebytes(archive.read(descriptors[0]))
        if descriptor['Name'] != name or descriptor['Version'] != version:
            raise ValueError(f'{name}: installed name/version differs from wheel')
        for entry in entries:
            if entry.endswith('/') or entry.endswith('.dist-info/RECORD'):
                continue  # installers rewrite RECORD; compare the payload itself
            parts = PurePosixPath(entry).parts
            if not parts or PurePosixPath(entry).is_absolute() or '..' in parts or any(p.endswith('.data') for p in parts):
                raise ValueError(f'{name}: unsupported wheel layout: {entry}')
            target = (installation / entry).resolve()
            if not target.is_relative_to(installation):
                raise ValueError(f'{name}: installed file escapes installation root: {entry}')
            if not target.is_file() or target.read_bytes() != archive.read(entry):
                raise ValueError(f'{name}: installed payload differs: {entry}')
            checked.append(entry)
    package = installation / name
    extra = {p.relative_to(installation).as_posix() for p in package.rglob('*.py')} - set(checked)
    if extra:
        raise ValueError(f'{name}: unexpected installed Python files: {sorted(extra)}')
    return len(checked)


def audit(wheels):
    """Audit installed imports and wheel contents; version equality alone is insufficient."""
    results = []
    for name in PACKAGES:
        choices = sorted(Path(wheels).glob(name + '-*.whl'))
        if len(choices) != 1:
            raise ValueError(f'{name}: expected exactly one wheel, found {len(choices)}')
        dist = metadata.distribution(name)
        root = Path(dist.locate_file('')).resolve()
        if not root.is_relative_to(Path(sys.prefix).resolve()):
            raise ValueError(f'{name}: distribution is outside this Python environment')
        module = importlib.import_module(name)
        origin = Path(module.__file__).resolve()
        if not origin.is_relative_to(root / name):
            raise ValueError(f'{name}: import is shadowed by another source tree')
        checked = compare_payload(choices[0], root, name=name, version=dist.version)
        results.append(dict(name=name, version=dist.version, wheel=choices[0].name,
                            sha256=hashlib.sha256(choices[0].read_bytes()).hexdigest(),
                            files_checked=checked))
    return results
