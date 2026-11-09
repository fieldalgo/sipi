# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit local project I/O with cooperative saves and atomic publication."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import tempfile

from .execution import _integer
from .execution_record import _DIGEST, _matches
from .project import SavedProject

__all__ = ['LoadedProject', 'ProjectSaveReceipt', 'ProjectBusyError',
           'ProjectConflictError', 'ProjectSaveError', 'read_project', 'save_project']

_DEFAULT_LIMIT = 16 * 1024 * 1024
_MAX_LIMIT = 64 * 1024 * 1024


@dataclass(frozen=True)
class LoadedProject:
    project: SavedProject
    file_sha256: str


@dataclass(frozen=True)
class ProjectSaveReceipt:
    file_sha256: str
    directory_synced: bool


class ProjectBusyError(RuntimeError):
    """A per-target cooperative lock exists; it is never stolen automatically."""
    def __init__(self, lock_path):
        super().__init__('Project save lock exists; do not remove an active writer lock')
        self.lock_path = Path(lock_path)


class ProjectConflictError(RuntimeError):
    """The target's raw bytes differ from the version the caller loaded."""


class ProjectSaveError(OSError):
    """An I/O failure; published=True means the new target may already exist."""
    def __init__(self, *, published, file_sha256, cleanup_errors=()):
        phase = 'after publication; reopen the target' if published else 'before publication'
        super().__init__('Project save failed '+phase)
        self.published = published
        self.file_sha256 = file_sha256
        self.cleanup_errors = tuple(cleanup_errors)


def _target(path):
    value = os.fspath(path)
    if not isinstance(value, str) or not value:
        raise ValueError('project path must be a nonempty text path')
    target = Path(value)
    if not target.name or target.name in ('.', '..'):
        raise ValueError('project path must name a file')
    parent = target.parent.resolve(strict=True)
    if not parent.is_dir():
        raise ValueError('project parent must be an existing directory')
    return parent / target.name


def _read_raw(target, limit):
    before = os.lstat(target)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('project target must be a regular file, not a symlink or special file')
    if before.st_size > limit:
        raise ValueError('saved project exceeds max_project_bytes')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(target, flags)
    try:
        opened = os.fstat(fd)
        if (not stat.S_ISREG(opened.st_mode)
                or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)):
            raise ValueError('project target changed while opening')
        stream = os.fdopen(fd, 'rb')
        fd = None
        with stream:
            raw = stream.read(limit + 1)
    finally:
        if fd is not None:
            os.close(fd)
    if len(raw) > limit:
        raise ValueError('saved project exceeds max_project_bytes')
    return raw


def read_project(path, *, max_project_bytes=_DEFAULT_LIMIT):
    """Read bounded UTF-8 project bytes without executing their calculations.

    file_sha256 identifies the original raw file, including whitespace. Pass it
    explicitly to save_project when replacing that file. The final path cannot
    be a symlink. No directories, backups or recovery files are created.
    """
    limit = _integer('max_project_bytes', max_project_bytes, 1, _MAX_LIMIT)
    raw = _read_raw(_target(path), limit)
    project = SavedProject.loads(raw.decode('utf-8'), max_project_bytes=limit)
    return LoadedProject(project, hashlib.sha256(raw).hexdigest())


def _sync_directory(parent):
    if os.name != 'posix':
        return False
    fd = os.open(parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return True


def save_project(path, project, *, expected_sha256=None):
    """Atomically create, or cooperatively replace, a project file.

    None means create only: an existing target is never overwritten. Replacement
    requires the exact raw SHA-256 observed by the caller. A sibling exclusive
    lock serializes cooperating writers; it does not provide compare-and-swap
    against unrelated programs that ignore the lock. No automatic retry, stale
    lock removal, in-place-write fallback or crash recovery is performed.

    The complete canonical candidate is fsynced before link/replace publication.
    Created/replaced files use the temporary file's private permissions (0600 on
    POSIX), not the old file's ACLs/metadata. Directory sync is attempted on POSIX;
    other systems return directory_synced=False. Filesystem and platform support
    require actual validation. A post-publication error must be reconciled by
    reopening the target, never by assuming the old file remains.
    """
    if not isinstance(project, SavedProject):
        raise ValueError('project must be a SavedProject')
    if expected_sha256 is not None and not _matches(_DIGEST, expected_sha256):
        raise ValueError('expected_sha256 must be null or 64 lowercase hex characters')
    validated = SavedProject.loads(project.dumps(), max_project_bytes=project._max_project_bytes)
    raw = validated.dumps().encode('utf-8')
    digest = hashlib.sha256(raw).hexdigest()
    target = _target(path)
    name_digest = hashlib.sha256(os.path.normcase(target.name).encode('utf-8')).hexdigest()
    lock = target.parent / ('.sipi-project-'+name_digest+'.lock')
    lock_owned = False
    temporary = None
    published = False
    failure = None
    cleanup_errors = []
    directory_synced = False
    try:
        try:
            lock_fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise ProjectBusyError(lock) from exc
        lock_owned = True
        os.close(lock_fd)
        if expected_sha256 is None:
            try:
                os.lstat(target)
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError('Project target already exists; load it before replacement')
        else:
            current = _read_raw(target, _MAX_LIMIT)
            if hashlib.sha256(current).hexdigest() != expected_sha256:
                raise ProjectConflictError('Project bytes changed since the supplied version was loaded')
        fd, name = tempfile.mkstemp(prefix='.sipi-project-', suffix='.tmp', dir=target.parent)
        temporary = Path(name)
        try:
            stream = os.fdopen(fd, 'wb')
            fd = None
            with stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            if fd is not None:
                os.close(fd)
        if expected_sha256 is None:
            os.link(temporary, target)
        else:
            os.replace(temporary, target)
        published = True
    except Exception as exc:
        failure = exc
    finally:
        for owned in (temporary, lock if lock_owned else None):
            if owned is None:
                continue
            try:
                owned.unlink(missing_ok=True)
            except OSError as exc:
                cleanup_errors.append(str(exc))
                if failure is None:
                    failure = exc
    if failure is None:
        try:
            directory_synced = _sync_directory(target.parent)
        except OSError as exc:
            failure = exc
    if failure is not None:
        if (not published and not cleanup_errors
                and isinstance(failure, (ProjectBusyError, ProjectConflictError,
                                         FileExistsError, FileNotFoundError))):
            raise failure
        raise ProjectSaveError(published=published, file_sha256=digest,
                               cleanup_errors=cleanup_errors) from failure
    return ProjectSaveReceipt(digest, directory_synced)
