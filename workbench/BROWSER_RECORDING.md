# Browser source-artifact records

The Worker supports the same `saved-record` request and raw record/project
transport as [native recording](RECORDING.md). Its provenance describes checked
source artifacts loaded into Pyodide, rather than an installed filesystem snapshot.
Automatic result-history UI remains separate from this transport contract.

Initialization validates relative source paths, declared sizes and SHA-256 for
every staged manifest file before loading the calculation runtime. Limits are
128 files, 64 MiB per file and 128 MiB total; the manifest is at most 1 MiB.
Wheels and Python helpers are unpacked/written from the checked bytes. Runtime
assets are checked before the ordinary Pyodide loader reads their staged URLs.
This is not an atomic network-load or loaded-memory attestation, signature, or
proof of the source server's identity. A matching manifest is a host declaration.

The reviewed runtime remains unmodified Pyodide 0.29.5/Python 3.13.2, ABI
2025_0/wasm32/emscripten_4_0_9, NumPy 2.2.5, SciPy 1.14.1, Shapely 2.0.7 and
array-api-compat 1.16.0. SIPI 0.1.0 and galerkin/meshine 0.0.2 source wheels are
identified by their hashes and full engine/shared commits; development version
strings alone are insufficient. Existing licenses, notices and redistribution
review limitations remain in force. No browser engine is bundled into the native app.

`BrowserSourceRecorder` validates the source manifest, loaded distribution
versions and actual helper file bytes. The loading host constructs this frozen
provider; user job JSON cannot inject a provider or artifact declaration.
The record declares seven source-wheel hashes plus the SHA-256 of the exact
raw manifest as `sipi-browser-runtime`/`runtime`. The manifest links runtime,
helper, wheel and notice hashes. Keep its original text with exported records.
Its `host-declared` metadata is not promoted to independent provenance or accuracy.

Each call runs the existing immutable request once, checks helper bytes before
and after, and returns raw `record_text` and `runtime_manifest_text`. A fresh run
ID distinguishes repeated identical requests. Input/record limits, failed and
incomplete receipts, cancellation, and stale project-selection rules are unchanged.
JavaScript must preserve record text rather than reserialize parsed numbers.
Worker errors do not fall back to server computation. Frozen-executable recording
still needs its own provenance path.

The existing staging command now includes the four canonical Python helpers.
Use a fresh stage and preserve exact engine/shared pins and notice inventories.
Run the existing browser/saved-analysis acceptance plus the new recording transport:

```sh
node workbench/tests/record-browser.mjs .validation/record-native
node workbench/tests/record-browser.mjs .validation/record-worker .validation/web
```

For the first command, `SIPI_PYTHON` must select the current built-wheel installation;
the host starts outside the checkout. Integrity-negative acceptance can add
`--expect-integrity-error` with a separately copied stage whose helper/runtime
bytes or source path was deliberately corrupted. Preserve the good stage.
These checks exercise actual browser transport; they do not claim that a new
result-history screen exists.

[한국어](BROWSER_RECORDING.ko.md)
