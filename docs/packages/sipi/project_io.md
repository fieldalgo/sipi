# Explicit local project files

[한국어](../../locales/ko/pages/packages/sipi/project_io.md) · [Project content](project.md) · [Execution records](execution_record.md)

`sipi.project_io` provides explicit file reads and saves for a local host. The
project and calculation modules remain free of automatic file access. Reading
or saving does not run a calculation, start a server or upload a design.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.project import SavedProject
from sipi.project_io import read_project, save_project

request = SavedExecutionRequest(LumpedNetworkDocument([0, 1e9], resistance=10).dumps())
project = SavedProject(request, project_id='demo:project', design_id='a',
                       title='Resistor comparison', label='Baseline')
with TemporaryDirectory() as directory:
    path = Path(directory) / 'comparison.json'
    created = save_project(path, project)  # create only; never overwrite an existing file
    loaded = read_project(path)
    assert loaded.file_sha256 == created.file_sha256
    assert loaded.project.dumps() == project.dumps()
    changed = loaded.project.duplicate_design('a', 'b', 'Alternative')
    replaced = save_project(path, changed, expected_sha256=loaded.file_sha256)
    reopened = read_project(path)
    assert reopened.project.design_ids == ('a', 'b')
    assert reopened.file_sha256 == replaced.file_sha256
```

`read_project` returns an immutable `LoadedProject` with `project` and
`file_sha256`. This digest identifies the **raw file bytes**, including whitespace,
and is separate from the internal project content checksum. Replacing a file
requires this exact previously observed digest. With `expected_sha256=None`, the
default, `save_project` only creates a new file and rejects an existing target.
It returns a `ProjectSaveReceipt(file_sha256, directory_synced)`.

```python
from sipi.project_io import ProjectConflictError

with TemporaryDirectory() as directory:
    path = Path(directory) / 'comparison.json'
    save_project(path, project)
    old = read_project(path)
    newer = old.project.duplicate_design('a', 'b', 'Alternative')
    save_project(path, newer, expected_sha256=old.file_sha256)
    conflict_detected = False
    try:
        save_project(path, project, expected_sha256=old.file_sha256)
    except ProjectConflictError:
        conflict_detected = True  # reload/compare; never blindly retry as an overwrite
    assert conflict_detected
    assert read_project(path).project.dumps() == newer.dumps()
```

## Publication and conflict boundaries

The parent directory must already exist. Its resolved path and the normalized
filename identify a sibling exclusive lock. An existing lock raises
`ProjectBusyError`; its `lock_path` identifies the lock for the host. The save
never waits, steals a lock or deletes another writer's lock. The final target
must be a regular file, not a symlink, directory or special file. Reads are
bounded before UTF-8 decoding and project validation.

The candidate is validated before writing. A unique sibling temporary file gets
the complete canonical UTF-8 content, is flushed and file-synced, and is then
published. Creation uses a hard link that cannot replace an existing target;
replacement checks the old raw digest under the cooperative lock and uses
`os.replace`. The call removes its own temporary file and lock. It never falls
back to truncating the old file or writing in place if the filesystem cannot
support these operations.

This serializes cooperating writers using the same resolved path. It is **not**
atomic compare-and-swap against programs that ignore the lock. Filesystem aliases,
hostile directory mutation and external writes during read/replace are outside
this guarantee. A matching content hash is not a monotonically increasing edit
revision and is not a signature. The host must still manage open-file ownership,
active runs and user conflict decisions.

On POSIX, the parent directory is synced after publication and cleanup and the
receipt reports `directory_synced=True`. On other systems the receipt reports
`False`; this is not a failed file sync or a claim of directory durability.
Created/replaced files use the temporary file's private mode, **0600 on POSIX**.
Old permissions, ACLs and extended attributes are not copied. The original raw
formatting is not preserved on save; the new file is canonical project JSON.

## Failure and recovery

- `FileExistsError`: create-only mode found an existing file, including a racing
  external creator. It was not overwritten.
- `FileNotFoundError`: a required parent or replacement target is missing.
- `ProjectConflictError`: replacement bytes changed since the supplied version.
  Keep both in-memory and on-disk versions; reload and compare before choosing.
- `ProjectBusyError`: another cooperative lock exists. Do not delete an active
  lock. After a crash, recovery must first establish that no writer is running.
- `ProjectSaveError`: inspect `published`. `False` means this call did not publish
  the candidate. `True` means the complete candidate was published before a later
  sync/cleanup failure; **reopen the target** and compare `file_sha256`. Do not
  assume the old content remains or automatically roll it back. `cleanup_errors`
  retains cleanup failures and the exception cause retains the I/O error.

A process kill or machine crash can leave temporary files or a stale lock. This
API does not promote temporary files, remove stale locks, rotate backups or
recover automatically. A host must preserve candidate/original data and reconcile
it explicitly. Successful sync calls are not proof of survival against hardware
failure, power loss or remote-filesystem behavior.

The default read cap is 16 MiB; `max_project_bytes` accepts 1 byte through 64 MiB.
Replacement comparison also bounds the old raw file to 64 MiB. Unknown project
versions, damaged checksums, non-UTF-8 files and unsupported structures reject
without rewriting their bytes. Candidate admission keeps the project's own cap.

```sh
python -m pytest -q tests/sipi/test_project_io.py tests/sipi/test_project.py tests/sipi/test_execution_record.py
```

Validation currently covers a **Linux local filesystem**: Unicode paths, exact
roundtrips, competing processes, raw-byte conflicts, no-clobber creation,
pre-publication failures, post-publication sync/cleanup failures and complete
reopening. Windows/macOS, browser downloads, network filesystems and interactive
crash recovery have not been accepted by these checks. No new third-party runtime
dependency is introduced.
