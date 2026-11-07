# SIPI workbench candidate

[한국어](README.ko.md)

This source candidate runs the independently installed SIPI engine through a
local default-browser UI or a browser Worker. It is not a released application.
The native packaging target is one installation-free Windows x64 EXE. It embeds
Python, the engine and UI assets; it does not embed a browser or need a remote
calculation service. Actual EXE size and Windows acceptance require a successful
Windows build and smoke report. Download-wheel sizes are not EXE measurements.

The basic workspace offers five cross-section forms, mesh controls, impedance
targeting, tolerance samples, saved section JSON and line/circuit results.
**Saved analysis** opens raw JSON for all 21 versioned contracts registered by
[`sipi.execution`](../docs/packages/sipi/execution.md). It checks and saves
canonical inputs, runs calculations and exports finite complex-valued results.
Failed study rows and target-search histories remain visible and downloadable;
incomplete studies do not receive a summary. Optional characteristic/mode
diagnostics can fail without discarding the base line result. Editing inputs
or cancelling invalidates displayed/exportable results. Dedicated forms for
every saved contract are not implemented. Explicit-mesh bounded static 3D
capacitance inputs return total C in farads, with their saved insulating
boundary and conductor order. They do not imply a geometry editor, via
transition L/S or open-space fringing.

## Run from source

Use an environment containing SIPI at `packaging/engine-ref.txt`, galerkin and
meshine at that engine's `dependencies.json` pin, and the numerical packages in
[`packaging/requirements-windows.txt`](packaging/requirements-windows.txt).
No editable source path should shadow those installations.

```sh
python workbench/desktop/main.py
```

The program opens a random localhost port in the default browser. The session
token stays in the URL fragment/session storage. Host, Origin and API token
checks restrict access; this is a desktop loopback service, not a hosted server.
Use **Exit** to stop it. Merely closing a browser tab does not stop the server.
`--no-browser` prints the local URL for automation. Requests are limited to
256 KiB, saved input to 200 KiB, studies/goals to 128 evaluations and each job
to five minutes. These are not a complete memory/output-size quota. Cancelling
stops the calculation process or Worker.

## Local browser staging and acceptance

Staging requires clean checkouts at the exact engine and shared-package pins,
installed setuptools/wheel and access to the official asset sources. The
stager verifies archive/lock hashes, builds pure first-party wheels and retains
licenses, source links and a runtime inventory. Use a new output directory.
Git attributes keep original notice bytes unchanged on Windows; their hashes
must not be repaired by editing upstream texts or relaxing the check.

```sh
python workbench/packaging/browser.py --engine ENGINE_CHECKOUT --shared SHARED_CHECKOUT --output .validation/web
python -m pytest -q workbench/tests
node --test workbench/tests/*.test.mjs
node workbench/tests/browser.mjs .validation/basic-native
node workbench/tests/saved-browser.mjs .validation/saved-native
node workbench/tests/browser.mjs .validation/basic-worker .validation/web
node workbench/tests/saved-browser.mjs .validation/saved-worker .validation/web
```

The automated browser checks require Chromium/Chrome and Node with native
WebSocket support. Set `SIPI_PYTHON` or `CHROME` to select executables. Worker
assets remain local during these checks; staging initially requires downloads.
Do not copy staged third-party binaries to public hosting before completing
the redistribution review. No hosting or routing configuration is included.

Functional acceptance is separate from numerical parity. The native and Worker
stacks use different SciPy/Shapely/GEOS versions. An elliptical pair generated
996/1754 native nodes/triangles versus 995/1752 in the Worker; its C0 normwise
difference was 1.03e-5. Reusing identical meshes after the explicit CODATA 2022
fix agreed within 1.14e-15 relative in the checked capacitance/surface cases.
This does not establish general remeshing or all-result pointwise parity.
Existing tolerances remain unchanged. All results retain the engine's physical
model limits; a local aperture capacitance is not a complete 3D transition.

## Windows candidate verification

The topic-only `workbench-candidate.yml` workflow builds exact first-party
wheels, checks adapter behavior, audits installed payloads and invokes Nuitka
2.8.10 with CPython 3.13.17 and the installed Visual Studio 2022 compiler. It
uploads reports and notices only, never the EXE or third-party runtime binaries.
Both the standalone and SciPy-vendored NumPy compatibility namespaces load
FFT/linear-algebra modules dynamically. The pinned build explicitly includes
those four modules, exercises the installed sources and requires them in the
completed compiler report. This inclusion check does not replace EXE execution.
For a matching prepared Windows environment:

```sh
python workbench/packaging/windows.py
python workbench/packaging/smoke.py .validation/sipi-windows/FieldAlgo-SIPI.exe
```

`inventory.json` records exact versions, compiler installation, source-wheel
hashes, bundled native files and actual EXE size/hash. `build-info.json` is
embedded and included in calculation exports. `smoke.json` records measured
startup, calculation, exit and temporary-file cleanup from a Unicode/space path;
failed launches retain a failed report.
Startup failures also retain bounded stdout/stderr with session tokens redacted,
including processes which exit before announcing the local URL.
The smoke uses `--no-browser`: Windows 10/11 interactive default-browser acceptance, isolated-network verification,
signing and complete native/static redistribution review remain separate gates.
No ZIP or online launcher replaces the one-EXE target.

See [dependency versions and terms](THIRD_PARTY.md).
