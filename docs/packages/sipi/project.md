# Saved A/B projects

[한국어](../../locales/ko/pages/packages/sipi/project.md) · [Execution records](execution_record.md) · [Requests](execution_request.md) · [Local files](project_io.md) · [Editable templates](template_document.md)

`SavedProject` keeps multiple current designs and their execution histories in
one immutable JSON snapshot. It supplies the data contract for local A/B work
and reopening. Loading, editing and preparing never execute a calculation.
This API does not read or write files or start a user interface.

```python
import hashlib
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject

def make_request(resistance):
    return SavedExecutionRequest(
        LumpedNetworkDocument([0, 1e9], resistance=resistance).dumps())

# Synthetic example metadata; the application must check actual build artifacts.
artifacts = [dict(component='sipi', version='example-only', kind='wheel',
                  sha256=hashlib.sha256(b'demonstration artifact').hexdigest())]
a = make_request(10)
result_a = SavedExecutionRecord(a, a.run(), run_id='demo:a', artifacts=artifacts)
project = SavedProject(a, project_id='demo:project', design_id='a',
                       title='Series resistor comparison', label='Baseline')
project = project.attach_record('a', result_a, select=True)
project = project.duplicate_design('a', 'b', 'Alternative')
assert project.design('b')['records'] == []
b = make_request(20)
project = project.update_design('b', b)
result_b = SavedExecutionRecord(b, b.run(), run_id='demo:b', artifacts=artifacts)
project = project.attach_record('b', result_b, select=True)
saved_text = project.dumps()  # application chooses how/where to persist this
restored = SavedProject.loads(saved_text)
assert restored.current_record('a').receipt == result_a.receipt
assert restored.current_record('b').receipt == result_b.receipt
assert restored.prepare('b').to_dict() == b.to_dict()
```

The application displays `current_record(design_id)` as the explicitly selected
result. `None` means no result is selected for the current request. It must not
display the last history item as if it were a new result. The selected record's
complete canonical request, including execution controls, must match the design.
Completion, fit acceptance and study completeness remain separate values in the
original receipt; selection does not relabel them or certify numerical accuracy.

```python
edited = restored.update_design('b', make_request(25))
assert edited.current_record('b') is None
assert edited.design('b')['records'] == [result_b.to_dict()]
assert restored.current_record('b').run_id == 'demo:b'  # old snapshot unchanged
reopened = SavedProject.loads(edited.dumps())
assert reopened.current_record('b') is None
assert reopened.prepare('b').to_dict() == make_request(25).to_dict()
```

## Explicit selection and history

- `add_design(id, label, request)` adds a current request without results.
- `duplicate_design(source_id, id, label)` copies its current request and
  controls, with empty history and selection. Existing snapshots stay unchanged.
- `update_design(id, request, label=...)` replaces its current original input
  and controls. A semantic change clears selection and retains all historical
  records. Formatting-only changes with equal canonical request keep selection.
- `attach_record(id, record)` appends history without selecting it. A late
  response for an older request can be retained this way.
- `attach_record(..., select=True)` and `select_record(id, run_id)` select only
  a record in that design that matches the current request. Mismatches reject.
  `select_record(id, None)` clears selection without deleting history.
- `remove_record(id, run_id)` explicitly removes one history item and clears
  selection if needed. `remove_design(id)` removes a design; at least one must
  remain. These operations return new snapshots and do not erase existing files.
- `design(id)` and `to_dict()` return detached data. `design_ids` preserves the
  design order; `prepare(id)` reconstructs the original request without running.

Hosts still own **active run admission**. Two invocations of the same semantic
request can both match a design; before selecting an arriving response, the host
must also compare its current invocation token. Project loading/selection does
not implement cancellation, process lifetime, concurrent editing or job queues.
No result is selected automatically from timestamps or history order.

## Strict file content contract

`sipi.project/1` has exactly `schema`, `project_id`, `title`, `designs` and
`content_sha256`. Each ordered design contains exactly `design_id`, `label`,
`source_text`, `controls`, `records` and `selected_run_id`. Controls retain the
existing canonical `max_input_bytes`, `max_evaluations` and `diagnostics` fields.
Records use the unchanged [execution record contract](execution_record.md).
This envelope is not a registered engine calculation input.

There are 1–64 designs and at most 128 records across the project. Design IDs
and record run IDs must be unique across their respective project collections.
Project/design IDs use 1–128 ASCII letters/digits/dot/underscore/colon/hyphen.
Title and label are nonblank text within 512 and 256 UTF-8 bytes respectively,
without C0 or DEL control characters. Original request text and its original
byte cap are preserved even when canonical input would be larger.

The default `max_project_bytes` is 16 MiB, configurable from 1 byte through
64 MiB. The limit covers both raw loaded UTF-8 text and canonical stored JSON;
embedded records are revalidated within this same cap. Functional edits preserve
the snapshot's configured cap. Unknown or duplicate keys, unsupported versions,
nonfinite values, invalid selections and damaged nested records reject.

The checksum hashes every project field except `content_sha256` using sorted
keys, compact separators and unescaped Unicode UTF-8. It detects changes and is
never silently repaired on load. A recomputed checksum does not authenticate a
file. Artifact identities inside records remain **host-declared**; saving them
does not verify installed binaries, dependency completeness or execution truth.

The application is responsible for atomic file writes, backups, recovery and
preserving an unsupported original file for a compatible reader. This envelope
does not silently migrate, discard unknown fields, restore a running job or
promise browser/Windows support. UI state and project merging are not included.

```sh
python -m pytest -q tests/sipi/test_project.py tests/sipi/test_execution_record.py tests/sipi/test_execution_request.py
```

Checks cover actual A/B network calculations, immutable input edits and history,
late responses, same-request run selection, copy/remove/reopen, exact UTF-8 and
count limits, strict structure/integrity and all registered input formats without
implicit field solves. They add no new physical accuracy claim.
