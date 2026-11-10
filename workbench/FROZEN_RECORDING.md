# Recorded execution in the Windows onefile candidate

The candidate's compiled host routes `saved-record` to an unpacked-bundle
provider. It shares the input, receipt, record and project contracts with the
[installed and browser hosts](RECORDING.md). Client JSON cannot supply a runtime
path, artifact declaration or provider. Other calculations keep their behavior.

This provider requires Windows x64, CPython 3.13.17, Nuitka 2.8.10 standalone
onefile markers, an explicit `--onefile-no-dll` build, and a helper beside the
executing payload. Windows temporary onefile builds otherwise default to a DLL
payload while the process executable remains the outer launcher; that mode does
not meet this recording contract. With the reviewed executable payload mode, `sys.executable` identifies the extracted executable; `argv[0]` and
`__compiled__.containing_dir` can identify the outer launcher and are not used.
The helper is compiled into the payload, so an inspectable Python source file
or installed wheel inventory is not required.

Before and after exactly one saved execution, the provider hashes every regular
file in that extracted directory, including the executable, native libraries,
UI, build information and notices. It rejects links/reparse points, nonregular
files, missing required files and changed snapshots. Limits are 20,000 directory
entries, 512 MiB of file bytes, 64 path segments, 1,024 characters per relative
path, 1 MiB build information and an 8 MiB generated manifest. Reads are bounded;
individual file identity/size/timestamps are checked around hashing. Snapshots
use sorted relative paths and contain no installation directory.

The raw `sipi.frozen-runtime/1` environment manifest describes the
`unpacked-bundle-files/1` selection policy, exact file sizes/hashes, executing
payload filename, runtime versions and embedded build information. Source-wheel
hashes in build information describe build inputs; the compiled payload is not
declared to be those original wheels. Record artifact items are:

- `sipi`, kind `executable`: SHA-256 of the actual extracted executable.
- `sipi-frozen-runtime`, kind `runtime`: SHA-256 of the exact UTF-8 environment
  manifest returned with the record.

These remain `host-declared` file identities, not signatures, a trusted publisher
chain, loaded-memory attestation or an atomic filesystem snapshot. System DLLs
outside the bundle are excluded. The compressed outer EXE has a different hash;
the packaging inventory and external smoke report identify it separately.
Matching hashes do not establish numerical or measured physical accuracy.
Existing record-size, failed/incomplete-result, cancellation and explicit project
selection rules still apply. No project or record is written automatically.

## Acceptance scope

`workbench/tests/test_frozen_recording.py` exercises synthetic bundle boundaries,
file changes, record/project round trips and independent smoke verification.
Synthetic files do not establish Windows execution. The real Windows build must
also run `workbench/packaging/smoke.py`: two recorded executions through spawned
calculation workers, identical request/receipt but distinct run IDs, independent
hashing of the live extracted files, raw project attachment/lookup, normal exit
and empty extraction directory. Failures retain a failed report. The smoke first
requests graceful shutdown on failure, then stops only its owned process tree
if needed. A cleanup error is recorded alongside the original failure instead
of replacing it; cleanup failure after an otherwise successful run still fails. A candidate is
accepted on Windows only after those checks pass for its exact commit and EXE.

The build retains the reviewed packaging/runtime pins and notices. This feature
does not resolve the separate native/static redistribution, interactive Windows
10/11, isolated-network or signing gates. No browser engine is added to the EXE.

[한국어](FROZEN_RECORDING.ko.md)
