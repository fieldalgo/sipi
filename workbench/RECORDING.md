# Recorded execution in an installed native workbench

`saved-record` accepts raw saved-input `text` and optional complete `controls`,
with the same admission rules as [saved-receipt](RECEIPTS.md): 200 KiB input,
256 KiB compact encoded request, at most 128 evaluations. Caller-supplied run IDs,
artifact declarations and other options are rejected. The existing analysis and
receipt actions keep their responses and numerical behavior.

This action requires the current recording helper in an inspectable installed
SIPI wheel. It captures [actual installed file inventories](ARTIFACTS.md), runs
the immutable request once, and captures them again. Different snapshots refuse
record creation. Missing metadata, source-shadowed imports or an unmatched helper
are refused before solving. An ordinary solver exception remains an error;
failed-goal and incomplete-study receipts retain their original histories.

The reply contains `engine`, raw `record_text` and raw `runtime_manifest_text`.
The record has a fresh UUID-based run ID and is limited to 200 KiB, including
input, receipt and declarations. Excessive output is refused without truncation.
The separate manifest can exceed the request/project limit: it is provenance
evidence, not another project input. Preserve both original strings for export.
Do not parse/reserialize the record's numbers before sending it to `project-attach`.
Project combined-size and explicit-selection rules still apply.

File comparison is not an atomic filesystem snapshot, loaded-memory attestation,
original-wheel identification or physical-accuracy claim. Declarations remain
`host-declared`. Unique run IDs do not replace cancellation or stale-response
checks. No files are written and the action does not select a project result.

The browser uses a separate [source-artifact path](BROWSER_RECORDING.md), while
frozen-executable provenance remains separate work. Existing calculations remain
available; automatic result-history UI is not added by these transport actions.

Run this built-wheel example outside the checkout:

```python
from sipi import LumpedNetworkDocument
from sipi.project import SavedProject
from sipi._workbench.engine import execute

text = LumpedNetworkDocument([0, 1e9], resistance=10).dumps()
project = execute(dict(action='project-create', text=text, project_id='example',
    design_id='a', title='Recorded calculation', label='A'))
result = execute(dict(action='saved-record', text=text))
updated = execute(dict(action='project-attach', project_text=project['project_text'],
    design_id='a', record_text=result['record_text'], select=True))
current = SavedProject.loads(updated['project_text']).current_record('a')
assert current.dumps() == result['record_text']
assert current.receipt['execution']['status'] == 'complete'
```

[한국어](RECORDING.ko.md)
