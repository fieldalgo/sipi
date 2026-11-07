"""A Windows-style Git checkout must preserve hash-pinned upstream notices."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize('preserve', [False, True])
def test_original_notice_bytes_survive_autocrlf_checkout(tmp_path, preserve):
    root = Path(__file__).resolve().parents[2]
    source = tmp_path / 'source'
    source.mkdir()
    notices = Path('workbench/packaging/notices')
    shutil.copytree(root / notices, source / notices)
    if preserve:
        shutil.copy2(root / '.gitattributes', source / '.gitattributes')

    def git(*args, cwd=source):
        return subprocess.run(['git', *args], cwd=cwd, check=True,
                              capture_output=True, text=True)

    git('init')
    git('-c', 'core.autocrlf=false', 'add', '.')
    git('-c', 'user.name=Codex', '-c', 'user.email=noreply@openai.com',
        '-c', 'commit.gpgsign=false', 'commit', '-m',
        'Notice checkout test fixture\n\nCo-authored-by: Codex <noreply@openai.com>')
    checkout = tmp_path / 'windows-checkout'
    git('-c', 'core.autocrlf=true', 'clone', '--no-hardlinks', str(source), str(checkout))
    inventory = json.loads((checkout / notices / 'manifest.json').read_text(encoding='utf-8'))
    matches = [hashlib.sha256((checkout / notices / item['file']).read_bytes()).hexdigest() == item['sha256']
               for item in inventory['components']]
    # The control must reproduce the platform failure, rather than passing
    # because Git happened to skip newline conversion in this test environment.
    assert all(matches) is preserve
