# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Verify exact wheels, then run regression and integration outside the checkout."""
import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheels', required=True, type=Path, help='the exact wheels installed for this run')
    parser.add_argument('--shard-index', type=int, default=None)
    parser.add_argument('--shard-count', type=int, default=None)
    args = parser.parse_args()
    if (args.shard_index is not None or args.shard_count is not None) and not (
            args.shard_index is not None and args.shard_count is not None
            and 0 <= args.shard_index < args.shard_count <= 64):
        parser.error('provide 0 <= shard-index < shard-count <= 64')
    root = Path(__file__).resolve().parents[1]
    report = root / '.validation'
    report.mkdir(exist_ok=True)
    xml = report / 'installed.xml'
    xml.unlink(missing_ok=True)  # an early failure must not retain a previous success
    outcome = dict(status='running', phase='setup', python=sys.version, platform=platform.platform())
    def save():
        (report / 'installed.json').write_text(json.dumps(outcome, indent=2) + '\n', encoding='utf-8')
    save()
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
               OPENPHYSICS_REQUIRE_CROSSCHECK='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    env.pop('PYTHONPATH', None)
    try:
        with tempfile.TemporaryDirectory(prefix='sipi-installed-') as tmp:
            outside = Path(tmp)
            # A fresh process outside the checkout also tests normal import resolution.
            shutil.copy2(root / 'tools' / 'verify_install.py', outside / 'verify_install.py')
            outcome['phase'] = 'artifact-audit'
            code = 'import json,sys; from verify_install import audit; print(json.dumps(audit(sys.argv[1])))'
            checked = subprocess.run([sys.executable, '-c', code, str(args.wheels.resolve())],
                                     cwd=outside, env=env, check=True, text=True, capture_output=True)
            outcome['artifacts'] = json.loads(checked.stdout)
            outcome['phase'] = 'reference-audit'
            outcome['dependencies'] = {name: metadata.version(name) for name in
                                       ('numpy', 'scipy', 'shapely', 'scikit-rf', 'scikit-fem')}
            for name in ('tests', 'integration'):
                shutil.copytree(root / name, outside / name)
            shutil.copy2(root / 'pyproject.toml', outside / 'pyproject.toml')
            partition_args = []
            if args.shard_index is not None:
                (outside / 'tools').mkdir()
                shutil.copy2(root / 'tools' / 'pytest_shard.py', outside / 'tools' / 'pytest_shard.py')
                outcome['partition'] = dict(index=args.shard_index, count=args.shard_count)
                partition_args = ['-p', 'tools.pytest_shard',
                                  '--sipi-shard-index=' + str(args.shard_index),
                                  '--sipi-shard-count=' + str(args.shard_count),
                                  '--sipi-shard-report=' + str(report / 'installed-shard.json')]
            outcome['phase'] = 'regression'
            subprocess.run([sys.executable, '-m', 'pytest', '-q', 'tests', 'integration',
                            '--junitxml=' + str(xml), *partition_args], cwd=outside, env=env, check=True)
        outcome.update(status='passed', phase='complete')
    except Exception as exc:
        outcome.update(status='failed', error=str(exc))
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            outcome['stderr'] = exc.stderr
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
