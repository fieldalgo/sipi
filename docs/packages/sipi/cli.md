# Saved-input commands

[한국어](../../locales/ko/pages/packages/sipi/cli.md)

The development wheel installs `sipi run` and `sipi validate`; `python -m sipi`
provides the same commands. Use an exactly validated wheel and matching
dependencies from [development](../../development.md). This is not a PyPI
release announcement. Commands do not start a browser or server. Bundled UI
assets and the default UI launcher remain separate work: `sipi` without a
subcommand currently prints usage and exits with code 2.

Prepare an input using the existing API:

```python
from pathlib import Path
from sipi import LumpedNetworkDocument

doc = LumpedNetworkDocument([0, 1e9], resistance=10, inductance=2e-9,
                            port_names=("input", "output"))
Path("input.json").write_text(doc.dumps(), encoding="utf-8")
```

```sh
sipi validate input.json --output canonical.json
sipi run input.json --output result.json
```

`validate` writes canonical input without a field solve. `run` uses
[SavedExecutionRequest](execution_request.md) and writes its
`sipi.execution-receipt/1`: canonical input, controls, semantic request identity
and the existing `sipi.execution/1` output. This is not a unique invocation ID,
artifact declaration or runtime attestation. Retain exact engine/dependency
wheel hashes alongside inputs/results; a development version alone is ambiguous.

```python
import json
from pathlib import Path

receipt = json.loads(Path("result.json").read_text(encoding="utf-8"))
assert receipt["schema"] == "sipi.execution-receipt/1"
assert receipt["execution"]["status"] == "complete"
assert receipt["execution"]["input"]["schema"] == "sipi.lumped-network/1"
```

[Registered calculation inputs](execution.md) are supported; project files,
receipts and result records are not calculation inputs. Unsupported versions,
duplicate keys and nonfinite values retain the engine's rejection behavior.
No template inference or automatic mesh refinement is added.

Omitted `--output` writes UTF-8 JSON to stdout. A literal `-` selects stdin or
stdout; errors go to stderr. `--max-input-bytes` defaults to 262144, with host
range 1..67108864, and bounds raw UTF-8 bytes before parsing.
`run --max-evaluations` defaults to 128, preserving the existing 2..10000 generic
range and per-model admission. Saved budgets are never silently clamped.
`--diagnostic characteristic` and/or `--diagnostic modes` apply only to supported
top-level line inputs; duplicate selections are invalid. These controls do not
limit elapsed time or memory.

| Exit | Meaning |
|---|---|
| 0 | Validation or execution completed. Fit `accepted` and optional diagnostic failures remain separate result decisions. |
| 1 | Failed/incomplete execution, or calculation/model-admission exception. Failed/incomplete receipts keep original rows/history; exceptions do not fabricate receipts. |
| 2 | Usage, input reading or request preparation failed. |
| 3 | Output error, including existing destinations and closed output pipes. |
| 130 | Ctrl+C interruption; inspect any output path before retrying. |

Named outputs must be new paths with existing parent directories. The command
serializes complete finite JSON, writes/fsyncs a sibling temporary file and
publishes with an exclusive hard link. Concurrent publishers cannot overwrite
each other. Only its own temporary file is removed; an error after publication
reports that the complete result already exists. Choose a new path to retry.
This provides no automatic replacement, backup, stale-file recovery or power-loss
durability guarantee. Hard-link support is required. Filesystem checks were run
on Linux; Windows/macOS acceptance is separate. Input files remain untouched.
