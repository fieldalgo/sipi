"""Create raw calculation records backed by inspectable installed payloads."""
import hashlib
import json
from pathlib import Path
import uuid

from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord

if __package__:
    from .artifacts import capture_installed_artifacts
else:
    from artifacts import capture_installed_artifacts


def run_recorded(request):
    """Execute once between two matching installed-file snapshots.

    Unique run IDs do not replace host cancellation or stale-response checks.
    File snapshots do not attest loaded memory or make the execution atomic.
    Return raw record/manifest text so JavaScript need not reserialize numbers.
    """
    if not isinstance(request, SavedExecutionRequest):
        raise ValueError('Recorded execution needs a prepared saved request.')
    if len(request.source_text.encode('utf-8')) > 200*1024 or request.max_evaluations > 128:
        raise ValueError('Recorded workbench execution accepts at most 200 KiB and 128 evaluations.')
    before = capture_installed_artifacts()
    components = json.loads(before['manifest_text'])['components']
    own_files = next(item['files'] for item in components if item['component'] == 'sipi')
    own_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if not any(row['path'] == 'sipi/_workbench/recording.py' and row['sha256'] == own_digest
               for row in own_files):
        raise ValueError('Recorded execution requires this helper in the installed SIPI wheel.')
    receipt = request.run()
    after = capture_installed_artifacts()
    if before != after:
        raise RuntimeError('Installed artifact snapshot changed during execution; no record was created.')
    record = SavedExecutionRecord(request, receipt, run_id='run:'+uuid.uuid4().hex,
                                  artifacts=before['artifacts'], max_record_bytes=200*1024)
    return dict(record_text=record.dumps(), runtime_manifest_text=before['manifest_text'])
