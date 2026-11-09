# Execution receipt transport

The shared Python adapter accepts `saved-receipt` with raw saved-input `text`
and optional `controls`. It returns `engine` and the existing
`sipi.execution-receipt/1` envelope. This is a host integration contract;
the input-project UI does not yet attach new calculation results.

Supplied controls must contain exactly `max_input_bytes`, `max_evaluations`
and `diagnostics`. Defaults are 204800, 128 and `[]`. Raw input is limited to
200 KiB and the compact UTF-8 JSON request to 256 KiB. A larger declared input
limit is retained in semantic identity, while the separate transport limit
still applies. Evaluation limits above 128 are rejected, never clamped.
Core model admission checks and line-only diagnostic restrictions remain.
Preparation does not promise a successful solve.

Receipts bind canonical input and all controls to execution output. Formatting
alone keeps the request identity; changed controls do not. Failed goals and
incomplete studies retain their status/history. Other exceptions follow the
existing host error path. `saved-analyze` is unchanged.

Repeated identical requests have the same semantic ID. Hosts must still assign
unique run IDs, reject stale responses and supply actual artifact provenance
before constructing project records. Receipts and `engine` version strings
do not identify wheels or attest physical accuracy. This action writes no files
and attaches no records. Preserve serialized project/record text across JavaScript:
reserializing parsed numbers can change digests, for example `0.0` becoming `0`.

This core example uses the same default receipt contract; the adapter adds the
transport limits above.

```python
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest

text = LumpedNetworkDocument([0, 1e9], resistance=10).dumps()
request = SavedExecutionRequest(text, max_input_bytes=204800,
                               max_evaluations=128, diagnostics=[])
receipt = request.run()
assert receipt['request']['request_id'] == request.request_id
assert receipt['execution']['status'] == 'complete'
```

[Project transport](PROJECTS.md) · [한국어](RECEIPTS.ko.md)
