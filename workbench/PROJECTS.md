# Project transport contract

[한국어](PROJECTS.ko.md)

The private desktop/Worker adapter transforms the existing
[SavedProject](../docs/packages/sipi/project.md) format without calculations or
file writes. A/B controls and result-history screens are not connected yet.
An accepted engine input does not imply an editable form exists for it.

| Action | Required keys besides `action` | Optional keys |
|---|---|---|
| `project-create` | `text`, `project_id`, `design_id`, `title`, `label` | `controls` |
| `project-open` | `project_text` | none |
| `project-duplicate` | `project_text`, `source_id`, `design_id`, `label` | none |
| `project-update` | `project_text`, `design_id`, `text` | `controls`, `label` |

`text` is raw engine-input JSON; `project_text` is raw project JSON. Missing or
unknown options, duplicate keys in those texts, unsupported versions, invalid
values and mismatched project digests are rejected. Replies contain `engine`
(existing version/build information) and canonical `project_text`. This adds
neither artifact attestation nor fabricated result records.

The encoded UTF-8 request is limited to 256 KiB. New input text, incoming project
text and canonical output projects are each limited to 200 KiB. The adapter uses
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
original text. Open preserves validated records and explicit selection. These
actions neither attach records nor choose a latest result. Invocation IDs,
stale-response handling, execution, artifact declarations and file publication
remain host work.

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
```

Native source/installed adapter and spawned HTTP checks do not establish new
Worker or Windows acceptance. The UI assets are unchanged in this unit.
