# Installed runtime file snapshots

`sipi._workbench.artifacts.capture_installed_artifacts()` inventories the actual
installed files of SIPI, galerkin, meshine, NumPy, SciPy, Shapely and
array-api-compat. It returns canonical `manifest_text` and record-compatible
`artifacts` declarations with `kind=runtime`. It does not change the calculation
UI, attach results, or write files. Browser and frozen-executable provenance
require separate host paths; this helper requires inspectable installations.

Each `sipi.installed-component/1` manifest contains the component/version,
`policy=distribution-files/1`, relative import path, and sorted file rows
(`path`, byte count, actual SHA-256). Its canonical compact, sorted-key,
non-ASCII-escaped UTF-8 JSON SHA-256 is the declaration digest. The enclosing
`sipi.installed-runtime/1` includes informational Python version, OS and machine.
Those runtime labels are not binary fingerprints and are not component digests.

The selection policy uses distribution file inventories, excluding bytecode,
`__pycache__`, installer bookkeeping (`RECORD`, `INSTALLER`, `REQUESTED`,
`direct_url.json` inside dist-info) and scripts with paths outside the distribution
root. Included metadata, licenses, Python files, listed data and bundled native
libraries are hashed from their actual bytes. Absolute/invalid/duplicate paths,
missing files, source-shadowed imports and unlisted package modules are refused.
The package scan checks `.py`, `.so`, `.pyd`, `.dll` and `.dylib`; it does not
claim to find every unlisted data file or externally loaded library.

Default limits are 20000 inventory entries (including excluded entries), 20000
scanned paths per imported package, and 512 MiB of included files in total.
Both limits must be positive integers. Hashing streams files and checks size and
file identity/timestamps before/after each read. This detects observed concurrent
changes, but is not an atomic filesystem snapshot or loaded-memory attestation.

These are actual file fingerprints, **not original wheel hashes**, signatures,
independent provenance audits, physical-accuracy evidence or complete Python/OS
library inventories. Record metadata remains `host-declared`. Preserve the raw
manifest alongside any future records so the digest's scope is reviewable.

Run from a built wheel outside the source checkout:

```python
import json
from sipi._workbench.artifacts import capture_installed_artifacts

snapshot = capture_installed_artifacts()
manifest = json.loads(snapshot['manifest_text'])
assert len(manifest['components']) == len(snapshot['artifacts']) == 7
assert {row['kind'] for row in snapshot['artifacts']} == {'runtime'}
```

[Project records](PROJECTS.md) · [한국어](ARTIFACTS.ko.md)
