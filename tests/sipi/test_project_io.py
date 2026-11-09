# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual local saves, competing processes and pre/post-publication failures."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest
from sipi import CrossSection, LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from sipi.project_io import (read_project, save_project, ProjectBusyError,
                             ProjectConflictError, ProjectSaveError)
import sipi.project_io as io


def project(resistance=10):
    request = SavedExecutionRequest(LumpedNetworkDocument([0, 1e9], resistance=resistance).dumps())
    return SavedProject(request, project_id='project:1', design_id='a', title='선로', label='설계')


def lock_path(target):
    name_hash = hashlib.sha256(os.path.normcase(target.name).encode('utf-8')).hexdigest()
    return target.parent / ('.sipi-project-'+name_hash+'.lock')


def test_real_create_load_replace_unicode_path_and_history(tmp_path):
    target = tmp_path / '선로 설계.json'
    p = project()
    req = p.prepare('a')
    # Synthetic fixture declaration; no assertion about actual build identity.
    result = SavedExecutionRecord(req, req.run(), run_id='run:1', artifacts=[
        dict(component='sipi', version='example-only', kind='wheel', sha256='1'*64)])
    p = p.attach_record('a', result, select=True)
    receipt = save_project(target, p)
    raw = target.read_bytes()
    assert raw == p.dumps().encode() and receipt.file_sha256 == hashlib.sha256(raw).hexdigest()
    assert receipt.directory_synced is (os.name == 'posix')
    loaded = read_project(target)
    assert loaded.project.dumps() == p.dumps() and loaded.file_sha256 == receipt.file_sha256
    changed = loaded.project.update_design('a', project(20).prepare('a'))
    second = save_project(target, changed, expected_sha256=loaded.file_sha256)
    reopened = read_project(target)
    assert reopened.file_sha256 == second.file_sha256 != receipt.file_sha256
    assert reopened.project.current_record('a') is None
    assert reopened.project.design('a')['records'] == [result.to_dict()]
    assert sorted(tmp_path.iterdir()) == [target]


def test_create_does_not_overwrite_existing_unrelated_or_valid_bytes(tmp_path):
    target = tmp_path / 'project'
    for original in [b'user file, not a project', project().dumps().encode()]:
        target.write_bytes(original)
        with pytest.raises(FileExistsError):
            save_project(target, project(20))
        assert target.read_bytes() == original and sorted(tmp_path.iterdir()) == [target]


def test_raw_whitespace_hash_is_separate_and_stale_saves_reject(tmp_path):
    target = tmp_path / 'project'
    original = project().dumps().encode()
    target.write_bytes(b' '+original+b'\n')
    loaded = read_project(target)
    assert loaded.project.dumps().encode() == original
    assert loaded.file_sha256 == hashlib.sha256(b' '+original+b'\n').hexdigest()
    assert loaded.file_sha256 != hashlib.sha256(original).hexdigest()
    target.write_bytes(original)
    with pytest.raises(ProjectConflictError):
        save_project(target, project(20), expected_sha256=loaded.file_sha256)
    assert target.read_bytes() == original and sorted(tmp_path.iterdir()) == [target]


def test_missing_replacement_never_creates_or_leaves_files(tmp_path):
    with pytest.raises(FileNotFoundError):
        save_project(tmp_path/'absent', project(), expected_sha256='0'*64)
    assert list(tmp_path.iterdir()) == []


def test_busy_lock_is_not_removed_or_stolen(tmp_path):
    target = tmp_path / 'project'
    lock = lock_path(target)
    lock.write_bytes(b'owned by another writer')
    with pytest.raises(ProjectBusyError) as exc:
        save_project(target, project())
    assert exc.value.lock_path == lock
    assert lock.read_bytes() == b'owned by another writer'
    assert sorted(tmp_path.iterdir()) == [lock]


@pytest.mark.parametrize('replacing', [False, True])
@pytest.mark.parametrize('stage', ['temp', 'file_sync', 'publish'])
def test_prepublication_io_failures_preserve_old_or_absent_target(tmp_path, monkeypatch, replacing, stage):
    target = tmp_path / 'project'
    old = project().dumps().encode()
    expected = None
    if replacing:
        target.write_bytes(old)
        expected = hashlib.sha256(old).hexdigest()
    def fail(*args, **kwargs):
        raise OSError('injected storage failure')
    if stage == 'temp':
        monkeypatch.setattr(io.tempfile, 'mkstemp', fail)
    elif stage == 'file_sync':
        monkeypatch.setattr(io.os, 'fsync', fail)
    else:
        monkeypatch.setattr(io.os, 'replace' if replacing else 'link', fail)
    candidate = project(20)
    with pytest.raises(ProjectSaveError) as exc:
        save_project(target, candidate, expected_sha256=expected)
    assert exc.value.published is False
    assert exc.value.file_sha256 == hashlib.sha256(candidate.dumps().encode()).hexdigest()
    assert not exc.value.cleanup_errors
    assert (target.read_bytes() == old) if replacing else not target.exists()
    assert sorted(tmp_path.iterdir()) == ([target] if replacing else [])


@pytest.mark.parametrize('replacing', [False, True])
def test_postpublication_directory_sync_failure_reports_new_complete_target(tmp_path, monkeypatch, replacing):
    target = tmp_path / 'project'
    expected = None
    if replacing:
        target.write_text(project().dumps(), encoding='utf-8')
        expected = read_project(target).file_sha256
    def fail(parent):
        raise OSError('injected directory sync failure')
    monkeypatch.setattr(io, '_sync_directory', fail)
    candidate = project(20)
    with pytest.raises(ProjectSaveError) as exc:
        save_project(target, candidate, expected_sha256=expected)
    assert exc.value.published is True
    loaded = read_project(target)
    assert loaded.project.dumps() == candidate.dumps()
    assert loaded.file_sha256 == exc.value.file_sha256
    assert sorted(tmp_path.iterdir()) == [target]


def test_cleanup_failure_keeps_evidence_and_reports_publication(tmp_path, monkeypatch):
    target = tmp_path / 'project'
    lock = lock_path(target)
    original_unlink = Path.unlink
    def fail_lock(self, *args, **kwargs):
        if self == lock:
            raise OSError('injected owned lock cleanup failure')
        return original_unlink(self, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', fail_lock)
    candidate = project()
    with pytest.raises(ProjectSaveError) as exc:
        save_project(target, candidate)
    assert exc.value.published is True and len(exc.value.cleanup_errors) == 1
    assert read_project(target).project.dumps() == candidate.dumps()
    assert lock.exists()
    original_unlink(lock)
    assert sorted(tmp_path.iterdir()) == [target]


def test_external_create_race_cannot_be_overwritten(tmp_path, monkeypatch):
    target = tmp_path / 'project'
    original_link = os.link
    def create_then_link(source, dest):
        Path(dest).write_bytes(b'external creator')
        return original_link(source, dest)
    monkeypatch.setattr(io.os, 'link', create_then_link)
    with pytest.raises(FileExistsError):
        save_project(target, project())
    assert target.read_bytes() == b'external creator'
    assert sorted(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize('replacing', [False, True])
def test_two_processes_cannot_both_publish_from_same_version(tmp_path, replacing):
    target = tmp_path / 'project'
    expected = None
    if replacing:
        save_project(target, project())
        expected = read_project(target).file_sha256
    code = '''import sys
from sipi.project import SavedProject
from sipi.project_io import save_project, ProjectBusyError, ProjectConflictError
try:
    save_project(sys.argv[1], SavedProject.loads(sys.argv[2]), expected_sha256=None if sys.argv[3]=='NONE' else sys.argv[3])
except ProjectBusyError:
    sys.exit(3)
except (ProjectConflictError, FileExistsError):
    sys.exit(4)
'''
    candidates = [project(20).dumps(), project(30).dumps()]
    processes = [subprocess.Popen([sys.executable, '-c', code, str(target), text, expected or 'NONE'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for text in candidates]
    outputs = [p.communicate(timeout=60) for p in processes]
    codes = [p.returncode for p in processes]
    assert codes.count(0) == 1 and all(c in (0, 3, 4) for c in codes), (codes, outputs)
    assert read_project(target).project.dumps() == candidates[codes.index(0)]
    assert sorted(tmp_path.iterdir()) == [target]


def test_bounded_read_checks_raw_bytes_utf8_and_integrity(tmp_path):
    target = tmp_path / 'project'
    data = project().dumps().encode()
    target.write_bytes(data)
    assert read_project(target, max_project_bytes=len(data)).project.dumps().encode() == data
    with pytest.raises(ValueError, match='max_project_bytes'):
        read_project(target, max_project_bytes=len(data)-1)
    target.write_bytes(b' '+data)
    with pytest.raises(ValueError, match='max_project_bytes'):
        read_project(target, max_project_bytes=len(data))
    target.write_bytes(b'\xff')
    with pytest.raises(UnicodeDecodeError):
        read_project(target)
    invalid = json.loads(data)
    invalid['title'] = 'not rehashed'
    target.write_text(json.dumps(invalid), encoding='utf-8')
    with pytest.raises(ValueError, match='digest mismatch'):
        read_project(target)
    assert json.loads(target.read_text(encoding='utf-8')) == invalid


def test_invalid_candidate_is_checked_before_any_file_creation(tmp_path):
    with pytest.raises(ValueError):
        save_project(tmp_path/'project', {})
    p = project()
    object.__setattr__(p, '_data_json', '{}')
    with pytest.raises(ValueError):
        save_project(tmp_path/'project', p)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('bad', ['', 'A'*64, 'a'*63, 'z'*64, 1, True])
def test_invalid_expected_digest_rejects_before_writing(tmp_path, bad):
    with pytest.raises(ValueError):
        save_project(tmp_path/'project', project(), expected_sha256=bad)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('bad', [0, -1, True, 1.0, 64*1024*1024+1])
def test_invalid_read_cap_rejects(tmp_path, bad):
    with pytest.raises(ValueError):
        read_project(tmp_path/'absent', max_project_bytes=bad)


def test_final_symlink_directory_and_special_file_are_not_followed(tmp_path):
    target = tmp_path / 'project'
    save_project(target, project())
    alias = tmp_path / 'alias'
    try:
        alias.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip('this test requires filesystem symlink support')
    with pytest.raises(ValueError, match='regular file'):
        read_project(alias)
    with pytest.raises(ProjectSaveError) as exc:
        save_project(alias, project(20), expected_sha256=read_project(target).file_sha256)
    assert exc.value.published is False and alias.is_symlink()
    assert read_project(target).project.dumps() == project().dumps()
    directory = tmp_path/'directory'
    directory.mkdir()
    with pytest.raises(ValueError, match='regular file'):
        read_project(directory)
    if hasattr(os, 'mkfifo'):
        fifo = tmp_path/'fifo'
        os.mkfifo(fifo)
        with pytest.raises(ValueError, match='regular file'):
            read_project(fifo)


def test_missing_parent_is_not_created_and_invalid_paths_do_not_write(tmp_path):
    with pytest.raises(FileNotFoundError):
        save_project(tmp_path/'absent'/'project', project())
    for path in ['', b'bytes', tmp_path/'..']:
        with pytest.raises(ValueError):
            save_project(path, project())
    assert list(tmp_path.iterdir()) == []


def test_private_candidate_permissions_on_posix(tmp_path):
    if os.name != 'posix':
        pytest.skip('POSIX mode semantics only')
    target = tmp_path/'project'
    save_project(target, project())
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    target.chmod(0o644)
    save_project(target, project(20), expected_sha256=read_project(target).file_sha256)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_read_save_never_run_calculations(tmp_path, monkeypatch):
    p = project()
    def forbidden(*args, **kwargs):
        pytest.fail('explicit project I/O executed a calculation')
    monkeypatch.setattr(SavedExecutionRequest, 'run', forbidden)
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    target = tmp_path/'project'
    save_project(target, p)
    loaded = read_project(target)
    assert loaded.project.dumps() == p.dumps()
    assert loaded.project.prepare('a').to_dict() == p.prepare('a').to_dict()
