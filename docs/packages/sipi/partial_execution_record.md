# Versioned records for partial resolution failures

`SavedExecutionRecord(..., schema='sipi.execution-record/2')` preserves the
existing partial failure outputs of `sipi.line-resolution/1`,
`sipi.line-resolution/2`, `sipi.panel-resolution/1` and
`sipi.adaptive-panel-resolution/1`. Those execution results retain a non-null
partial assessment and an error described by `stage`, `input`, `kind` and
`message`. Previously the version-1 record envelope rejected this combination.

The default constructor still creates `sipi.execution-record/1` and retains all
its original admission rules. Execution outputs are unchanged. Opt into version
2 when capturing these partial results; loading does not silently upgrade old
records. Version 2 also retains the ordinary complete, incomplete and typed-error
states supported by version 1.

A partial failure is admitted only for those four resolution input schemas.
The result must have the appropriate static or adaptive keys, false `completed`
and `accepted` flags, original tolerances, and object-row evaluation/comparison
histories. Its field-failure record must match the original error. Adaptive
field failures retain `stop_reason: field-failed` and no selected evaluation.
An adaptive budget stop instead retains null field failure,
`stop_reason: budget-exhausted`, `ResolutionBudgetExceeded`, the budget stage and
the original request input. It is not relabelled as convergence or a field error.

All existing source/request binding, content digest, byte limits, run identity
and host-declared artifact checks remain. The failed matrices and histories are
preserved evidence, not independently certified numerical results. Structural
validation does not authenticate a manually assembled receipt, prove the declared
artifacts ran or certify physical accuracy. A checksum is not a signature.

Loading and `prepare()` perform no fields or optimization. `SavedProject` can
retain and explicitly select a version-2 record through its existing record
loader. Selection does not turn a failed calculation into a qualified result.
A version-2 record remains an output document, not an engine request.

This small complete-network example demonstrates the same explicit record API.
Use real host-verified artifact declarations in a real run; the placeholders below
are deliberately marked as examples.

```python
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord

request = SavedExecutionRequest(LumpedNetworkDocument(
    [0., 1e9], resistance=10., port_names=('input', 'output')).dumps())
receipt = request.run()
# Example-only declarations, not the hashes of any executed artifacts.
artifacts = [dict(component='sipi', version='example-only', kind='wheel',
                  sha256='0' * 64)]
saved = SavedExecutionRecord(request, receipt, run_id='example:1',
    artifacts=artifacts, schema='sipi.execution-record/2')
restored = SavedExecutionRecord.loads(saved.dumps())
assert restored.receipt == receipt
assert restored.prepare().to_dict() == request.to_dict()
assert restored.to_dict()['schema'] == 'sipi.execution-record/2'
```

[한국어](../../locales/ko/pages/packages/sipi/partial_execution_record.md)
