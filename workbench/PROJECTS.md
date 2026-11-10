# Project transport contract

[한국어](PROJECTS.ko.md)

The private desktop/Worker adapter transforms the existing
[SavedProject](../docs/packages/sipi/project.md) format without calculations or
file writes. The [input-project UI](README.md#keep-ab-cross-section-inputs-in-a-project)
uses input operations. **Saved analysis** uses the same contract for project inputs,
recorded runs and explicit history selection, as described below.
An accepted engine input does not imply an editable form exists for it.

| Action | Required keys besides `action` | Optional keys |
|---|---|---|
| `project-create` | `text`, `project_id`, `design_id`, `title`, `label` | `controls` |
| `project-open` | `project_text` | none |
| `project-duplicate` | `project_text`, `source_id`, `design_id`, `label` | none |
| `project-update` | `project_text`, `design_id`, `text` | `controls`, `label` |
| `project-attach` | `project_text`, `design_id`, `record_text`, `select` | none |
| `project-select` | `project_text`, `design_id`, `run_id` | none |
| `project-remove-record` | `project_text`, `design_id`, `run_id` | none |
| `project-record` | `project_text`, `design_id`, `run_id` | none |

`text` is raw engine-input JSON; `project_text` and `record_text` are raw project
and execution-record JSON. Missing or
unknown options, duplicate keys in those texts, unsupported versions, invalid
values and mismatched project digests are rejected. Replies contain `engine`
(existing version/build information) and canonical `project_text`. This adds
neither artifact attestation nor fabricated result records. The read-only
`project-record` reply instead contains `engine`, raw `record_text`, `selected`
and `matches_current` booleans; it does not return a replacement project.

The encoded UTF-8 request is limited to 256 KiB. New input text, incoming project
text, incoming record text and canonical output projects are each limited to 200 KiB. The adapter uses
compact, non-ASCII-escaped JSON for its size check; the native HTTP host also
bounds the actual received body, including extra escaping/whitespace. Growth
beyond the bound is rejected without truncation or automatic record removal.
Hosts must retain their previous snapshot on errors. The core API's larger
configurable limits remain separate.

Supplied `controls` must contain exactly `max_input_bytes`, `max_evaluations` and
`diagnostics`, with existing execution-request validation. Creation defaults to
204800 bytes, 128 evaluations and no diagnostics. Update preserves the current
controls when omitted. Preparation does not admit a model-specific calculation
budget or certify convergence.

Duplication copies current input/controls into a new ID with empty history;
other designs are retained. Semantic input/control updates clear selection but
keep all history. Formatting-only updates retain selection and the new exact
original text. Open preserves validated records and explicit selection.

`project-attach` accepts an existing record with a required boolean `select`.
Run IDs must be unique across the project. `select=true` requires the record's
input and controls to match the current design; `false` may retain an older
request as history, without replacing the current selection. `project-select`
selects an existing matching run, or clears selection with `run_id=null`.
`project-remove-record` removes an existing run and clears selection if needed.
Missing designs/runs, stale selections, tampering and excessive combined growth
are errors; the original snapshot is unchanged. No operation chooses the latest
result automatically or certifies that a response belongs to the active invocation.

`project-record` reads a specified existing run without executing, selecting or
changing anything. It validates the whole incoming project first, then returns
the Python-serialized record text with its numeric spellings and digest intact.
Historical inputs/controls may be read: `matches_current=false` marks them as
history, not results for the current design. A formatting-only input change
does not change semantic matching. `selected` reports the existing explicit
selection; matching alone never selects a run. No runtime manifest is invented
or reconstructed from the record's host-declared artifact metadata.

Pass original serialized record text across JavaScript. Parsing and reserializing
numbers can change their content digest. Artifact declarations remain
`host-declared`; attaching a record does not audit or authenticate its provenance.
Invocation IDs, stale-response handling, execution, actual artifact evidence and
file publication remain host work. The seven-form input-project screen does not
attach newly recorded results; use **Saved analysis** for that workflow.

## Keep analysis variants and recorded runs

In **Saved analysis**, load a saved input and choose **Start project from input**.
Name the design, edit its raw JSON or optional diagnostics, and use **Duplicate
current input** to make another variant. Duplication copies current input and
controls with empty history. Switching designs first validates and stores the
current edit, then restores the other input and diagnostics. Invalid input keeps
the current project and design. **Save project** downloads the complete raw
`sipi-analysis-project.json`; **Open project** validates a file before replacing
the current workspace. Neither operation uploads or automatically writes files.

**Run and keep record** in an active project executes the current input and
controls once, then attaches and explicitly selects that run for the design.
Failed targets and incomplete studies remain records with their original status.
If the combined project would exceed a limit, the old project is retained and
the new standalone execution record remains downloadable with a clear error.
Ordinary **Run analysis** does not create history. In a project it uses the same
stored byte/evaluation controls and selected diagnostics as recorded execution.
Imported controls are preserved: a budget above the workbench's 128-evaluation
limit can be opened and saved but execution is refused, not silently clamped.

Choose a run in **Project history**, then **View saved run**. This reads its raw
record without recalculating, selecting or replacing the editable input. The
screen distinguishes selected, matching-but-unselected and historical requests;
unsaved edits are explicitly marked. **Select as current** requires the record
to match the current validated input and controls. **Clear selection** retains
all history; **Remove from project** removes the chosen run and clears selection
when needed. Save the project file to retain any such change.

Input/control edits retain historical records and clear an incompatible
selection on the next validated project update. Formatting alone does not change
semantic matching. Project text and record text are transported and downloaded
without JavaScript reserialization of their digest-bearing numbers. A viewed
record can be exported, but its separate runtime manifest is not inside the
project: **Save environment** is unavailable for a history-only view. Save the
environment file immediately after a newly recorded run if you need it later.
Ordinary result export is disabled while viewing history; export the raw record.

Cancelled operations, late file reads and late attachment replies cannot replace
the current project or append a stale run. UI edits commit only after all required
project transformations succeed. Project limits remain 200 KiB and 256 KiB for
the encoded request; there is no truncation or automatic deletion of old runs.
Individual record-file import, automatic numerical comparison and an environment
manifest archive are not part of this screen.

Actual browser acceptance is `node workbench/tests/project-history-browser.mjs OUTPUT`
with `SIPI_PYTHON` pointing to the built-wheel environment. A staged browser
directory as the second argument exercises the Worker path.

This built development-wheel example creates an A/B snapshot without fields:

```python
import json
from sipi.template_document import TemplateSectionDocument
from sipi._workbench.engine import execute

design = TemplateSectionDocument('stripline',
    dict(width=.0005, plane_spacing=.001, eps_r=4))
created = execute(dict(action='project-create', text=design.dumps(),
    project_id='example', design_id='a', title='Width study', label='A'))
copied = execute(dict(action='project-duplicate', project_text=created['project_text'],
    source_id='a', design_id='b', label='B'))
variant = TemplateSectionDocument('stripline',
    dict(width=.0006, plane_spacing=.001, eps_r=4), mesh=design.cross_section.mesh_options)
updated = execute(dict(action='project-update', project_text=copied['project_text'],
    design_id='b', text=variant.dumps()))
opened = execute(dict(action='project-open', project_text=updated['project_text']))
assert opened['project_text'] == updated['project_text']
assert len(json.loads(opened['project_text'])['designs']) == 2
cleared = execute(dict(action='project-select', project_text=opened['project_text'],
    design_id='a', run_id=None))
assert cleared['project_text'] == opened['project_text']
```

Adapter/HTTP acceptance and actual browser/platform acceptance are separate
checks; see the [workbench guide](README.md) for the current user flow and limits.

Read a real installed record without resending its parsed numeric values:

```python
from sipi import LumpedNetworkDocument
from sipi._workbench.engine import execute

text = LumpedNetworkDocument([0, 1e9], resistance=10).dumps()
created = execute(dict(action='project-create', text=text, project_id='records',
    design_id='a', title='Recorded analysis', label='A'))
recorded = execute(dict(action='saved-record', text=text))
import json
run_id = json.loads(recorded['record_text'])['run_id']
attached = execute(dict(action='project-attach', project_text=created['project_text'],
    design_id='a', record_text=recorded['record_text'], select=True))
read = execute(dict(action='project-record', project_text=attached['project_text'],
    design_id='a', run_id=run_id))
assert read['record_text'] == recorded['record_text']
assert read['selected'] and read['matches_current']
```
