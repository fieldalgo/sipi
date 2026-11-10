# SIPI workbench candidate

[한국어](README.ko.md)

The [project workflow](PROJECTS.md) keeps input variants in the ten-form workspace
and adds saved-run history to **Saved analysis**. Project files and separate
environment manifests are downloaded explicitly; nothing is uploaded automatically.
The [receipt transport](RECEIPTS.md) binds saved calculations to their exact input controls.
The [installed artifact helper](ARTIFACTS.md) captures actual distribution files for host provenance.
[Recorded execution](RECORDING.md) can export raw result records and environment manifests from **Saved analysis → Run and keep record** in an installed wheel or staged browser workspace.
[Browser recording](BROWSER_RECORDING.md) uses checked staged source artifacts for the same record transport.
[Windows candidate recording](FROZEN_RECORDING.md) identifies the unpacked executable and bundle; acceptance requires its exact real Windows build and smoke.

This source candidate runs the independently installed SIPI engine through a
local default-browser UI or a browser Worker. It is not a released application.
The native packaging target is one installation-free Windows x64 EXE. It embeds
Python, the engine and UI assets; it does not embed a browser or need a remote
calculation service. Actual EXE size and Windows acceptance require a successful
Windows build and smoke report. Download-wheel sizes are not EXE measurements.

The basic workspace offers ten cross-section forms, impedance targeting,
tolerance samples, saved mesh settings and line/circuit results.
**Saved analysis** opens raw JSON for the contracts registered by the pinned
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

## Save a design and keep editing

Choose a template, enter its dimensions and materials, then use **Save editable
design**. **Open design** restores those fields from the downloaded JSON, so you
can edit, calculate, search a target width or run a study. This uses
[`sipi.template-section/1`](../docs/packages/sipi/template_document.md): original
template arguments, their resolved geometry and all mesh settings stay together.
Opening checks that the current engine reproduces the saved geometry exactly.
A mismatched or unsupported file leaves your current design intact.

The ten forms are microstrip, stripline, offset stripline, coupled microstrip, coupled stripline, grounded coplanar,
coupled grounded coplanar, planar coated microstrip, planar coated pair and coated grounded coplanar. Other engine templates can use **Saved analysis**;
this page does not infer a form from arbitrary geometry. **Export geometry**
keeps the existing cross-section JSON download. Opening that geometric file
preserves its geometry and mesh but does not enable dimension editing.

Use **Offset stripline** for one signal with an explicit bottom-face height
between two ground planes. This is a separate form from centred **Stripline**;
its height is required, not nullable. Plane spacing includes copper thickness,
and changing spacing or thickness keeps an explicit height fixed. The whole
conductor must stay strictly inside the planes. The preview, editable JSON,
A/B project and fixed mesh retain the same input. Its width target is `z0`,
frequency export has two single-ended ports, and **Bottom-face height** is a
study variable. No centred-template file is silently converted.

The qualified single-trace check uses a thin uniform dielectric section and
an independent infinite-parallel-plane Green-panel reference, with separate
mesh, lateral-domain and vertical-reflection gates. Finite 35 µm rectangular
copper has an independent same-mesh complex/vacuum finite-element check.
Width targets retain both requested and refined mesh tolerance checks. These
checks do not certify arbitrary placements, materials or measured PCB accuracy.

For **Coupled stripline**, plane spacing is the full distance between the two
ground planes and gap is measured between the bottom copper edges. Both traces
have the same bottom width and profile. The target and study quantity is
differential impedance; frequency response retains four single-ended ports plus
its mixed-mode representation. Choose centred placement or an explicit `trace_height` with **Vertical placement**.
The height is measured from the lower plane to the copper bottom face; the
whole conductor must remain strictly between the two planes. Saved precise
heights appear in the schematic and survive mm/µm/mil changes, width edits,
fixed meshes and project variants. Returning to centred placement explicitly
saves the existing nullable value; this does not change the JSON schema.

Explicit height stays fixed when spacing or thickness changes. A centred
trace follows `(plane_spacing - thickness) / 2`. Width targets keep placement
unchanged, and a manually positioned pair exposes **Bottom-face height** in
parameter studies. Centred/null height is not a numeric study variable. Study
bounds that touch or cross either plane are rejected before field solves.
This control belongs to the coupled-stripline form; it does not silently
convert a centred single stripline into another template.

The qualified thin-strip uniform-dielectric checks use an independent
parallel-plane Green-function panel calculation, its centred single-strip
elliptic-integral limit and separate mesh/domain/reflection tests. A finite
35 µm rectangular pair also has an independent same-mesh complex/vacuum
finite-element comparison. These checks do not establish general measured
PCB accuracy or certify every placement and material.
A failed finer-mesh target check retains its evaluation history instead of
accepting a coarse result. The saved goal document uses the requested mesh;
the separate refined impedance is verification, not a substituted saved mesh.

For **Coupled coplanar**, two equal signal traces lie between finite side grounds
above a backing ground plane. **Gap** is the signal-to-signal bottom-edge gap;
**Signal–ground gap** is the bottom-edge distance to each side ground. **Ground
width** applies to each rectangular side ground. Grounds share the signal
thickness; taper changes only the signals. Width targeting and studies use
differential impedance, and network export has four signal ports. Studies can
vary either ground dimension; ground width is also available for single-signal
coplanar. Imported air height and box width remain exact and can be edited in Domain bounds. Check
mesh and outer-domain convergence after changing these finite grounds.
For automatic width targets, this pair keeps the resolved edge size and growth,
reduces the far size by four, and still requires the separate finer-mesh check.
The default edge size already accounts for the ground gaps. Explicit mesh
settings are unchanged. If the finer result misses your tolerance, inspect and
refine the mesh before retrying; neither the point limit nor tolerance is relaxed.

The form reference uses zero-thickness vacuum conductors and an independent
image-charge panel calculation. Mesh refinement and an enlarged finite domain
are checked separately. This reference does not establish finite-thickness or
measured manufacturing accuracy; unequal signals and independent ground thickness
need their separate engine contracts through **Saved analysis**.

For **Planar coated pair**, the two equal signals have a bottom-edge gap and
an optional shared taper. The coating fills beside and above both traces with
a flat top; its height starts at the substrate surface and must exceed copper
thickness. **Air height** starts above that coating. Substrate and coating have
separate permittivities and loss tangents. Width targets and studies use
`z_diff`; network export retains four single-ended ports and mixed-mode data.
Coating height and permittivity are study variables. Invalid clearance at any
bounds-box corner is rejected before solving. Input units, fixed mesh, JSON
and project variants preserve the original physical values.

This pair's automatic width target keeps the resolved edge size and growth
that already account for the coating, divides far size by four, and retains
the mandatory separate refinement and original point limit. Explicit settings
stay fixed. Qualified checks cover the thin vacuum image-panel reference,
finite tapered complex-capacitance assembly, mesh and air/box convergence,
and the air-coating/plain-line limit. They do not establish general measured
manufacturing accuracy or a conformal-coating model.

For **Coated coplanar**, one signal lies between two finite rectangular grounds,
with a bottom reference plane and a full-width flat coating. **Gap** is the
signal-bottom-edge to ground-edge spacing; **Ground width** is the width of
each side ground. Signal taper leaves both grounds rectangular. Coating height
starts at the substrate and includes copper height; air clearance starts above
it. Targets and studies use `z0`; network export has two single-ended ports.
Coating height/permittivity, gap and ground width can be sampled with the
same fixed nominal mesh and prevalidated bounds. Automatic width targeting
retains coating-aware edge/growth defaults and divides far size by four before
the unchanged mandatory refinement. Explicit meshes remain fixed. Qualified
image-panel, independent complex-FE, mesh/outer and air-limit checks are
separate from measured manufacturing accuracy or a conformal-film model.

Changing display units does not round the stored SI inputs. Unedited parameters
and any inputs without a visible field retain their
saved values. An explicit field edit invalidates displayed results. A successful
target search saves the returned width and mesh. Reopened designs retain that
mesh during subsequent edits; check mesh and outer-domain convergence again for
the changed geometry. Choosing another template starts fresh default settings.
An editable design file contains inputs, not calculation results, target bounds,
study settings or A/B project history.

The engine pin includes 109 registered saved schemas. Registration/normalization
does not establish that every possible calculation is suitable for the browser,
within its job limits, or independently validated. The editable path shares the
native/Worker adapter; current-platform acceptance must use the exact staged
engine and assets. Advancing the pin alone is not a Windows or Worker pass.

## Display units and physical inputs

Choose mm, µm or mil for cross-section lengths and width bounds. Switching
units changes the display, not the stored SI geometry, target-search bounds
or length-study bounds. An explicit edit updates only that physical value;
display rounding cannot overwrite the opposite bound. Material bounds remain
dimensionless. Changing a study variable resets its physical bounds from
the current nominal input, independently of the display unit.

An empty copper thickness stays invalid through unit changes; enter `0`
explicitly for the thin-conductor model. Empty study bounds also stay invalid.
Target and study settings remain session controls and are not added to input
project files. The frequency-response length still uses its separately labelled
mm input, while mesh inspection always shows µm.

## Set and inspect the finite domain

Open **Domain bounds** to inspect the actual calculation width and total height
without solving or changing inputs. Surface templates also show the air layer's
height; striplines have no air-height control. Imported geometry exposes only
read-only inspection. The preview remains a cropped schematic, not a drawing of
the finite computational boundary.

Choose **Set width** or **Set height** to enter an explicit box width or air-layer
height in the current mm/µm/mil display unit. When inspected values are available,
selecting an explicit mode starts from that resolved value. Other original
parameters and a previously fixed mesh stay unchanged. Unit changes do not
round stored SI values. Use **Automatic** to return that dimension to the
existing template default; automatic bounds can change when geometry changes.
Fresh automatic requests omit optional bounds, and the existing template-file
normalization fills their null defaults. Saved null and exact explicit values
survive reopening and A/B input projects. These controls do not add domain
sizes to the manufacturing-tolerance variables.

Inspection preserves a displayed result; editing bounds clears it. Compare
results for enlarged bounds separately from mesh refinement. A box that cannot
contain the copper is rejected, and changing size does not certify convergence.
For planar coatings, air height is the air layer above the coating, not the
coating height measured from the substrate. Saved mesh settings are retained
after domain edits, so check their suitability again for the changed region.

## Inspect and refine the mesh

Open **Mesh settings** and choose **Inspect current mesh** to resolve the current
settings without solving or changing inputs. The displayed lengths are always
in micrometres, independent of the geometry display unit. Inspection and an
ordinary calculation leave an automatic mesh automatic.

**Refine mesh ×2** explicitly fixes a new mesh with edge size, far size and growth
halved; minimum angle is unchanged. Results are cleared. Recalculate and compare
convergence. This operation does not certify accuracy or adjust the outer domain.
Fixed settings survive geometry edits, unit changes, editable files and A/B inputs.
**Use automatic mesh** discards the fixed settings and clears results. Automatic
width targets retain their existing finer starting mesh and separate refinement
check. Saving resolves the settings in the file; reopening restores a fixed mesh.
Geometry-only imports can be inspected but not changed with these controls.

## Keep A/B cross-section inputs in a project

Use **Duplicate design** to keep the current cross-section as one variant and
edit a copy. **Current design** switches between variants, keeping changes to
the design you leave. **Design name** changes its label. Template selection and
opening an editable design replace the active variant's cross-section.

**Save input project** downloads `sipi-project.json`; **Open project** restores
its first design, then the selector opens the other variants. These actions
validate inputs without automatically calculating. Exact SI inputs, hidden
template settings and resolved mesh survive display-unit changes. A calculation
or target search must still satisfy its own model and convergence checks.

This file stores cross-section geometry, materials and mesh. Target bounds,
study options, frequency-response settings and new workbench results are not
added. Existing validated records in an opened project are preserved; an input
change clears their current selection and a duplicate starts without records.
The screen does not display old records as a newly calculated result.

All project designs must use the ten supported editable templates. Other
inputs, invalid/damaged projects and files over 200 KiB are rejected without
replacing the current project. The encoded request limit is 256 KiB; oversized
updates are rejected without truncation. A geometry-only import cannot replace
an active editable project design; use an editable design or a separate workspace.
Cancel also discards pending or late file reads. Projects live in this tab until
you download them: no automatic disk save, recovery or cloud storage is provided.
After a failed operation, correct the input and retry or reopen a saved file.

## Run from source

An installed development SIPI wheel also contains this local UI and adapter:
run `sipi` or `sipi gui`. Use `sipi gui --no-browser` for an explicit local URL.
See [installed UI](../docs/packages/sipi/local_ui.md). The wheel build copies
these canonical sources; it does not bundle a browser or third-party runtime.
Source/editable checkouts can continue using the launcher below.

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

## Keep a comparison baseline

After a successful cross-section calculation, choose **Keep current as baseline**.
The workspace takes a separate snapshot of that result and its actual geometry,
mesh and engine metadata. Change a dimension, outer domain or mesh and calculate
again to compare the new result. **Clear baseline** removes the snapshot; keeping
a new result explicitly replaces it. Inspect the geometry/mesh details to see
which physical inputs or numerical settings changed.

Comparison requires one or two signals with the same names in the same order;
it does not infer conductor correspondence. Shared finite scalar quantities and
every C, L and G-at-1-GHz matrix entry are shown in the stated units. Asymmetric
pairs retain matrix comparisons without inventing symmetric scalar summaries.
Change means current minus baseline; the percentage divides by the absolute
baseline value. Zero baselines have no percentage. A nonfinite matrix or an
overflowing displayed difference refuses comparison.

Editing inputs, failed calculations and cancellation hide current differences
while retaining the baseline. Changing display units does not change either
result. On narrow screens, the primary line metric moves above the other
summary values; comparison tables scroll inside their panel. The snapshot lives only in this tab: it is not saved in an input project
and disappears on reload. Use Saved analysis records for persistent execution
history. Network traces and study rows are not compared here. A small difference
alone is not a mesh/domain convergence certificate or an accuracy measurement.

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
The smoke also checks two recorded runs, independently hashes the live unpacked
bundle and verifies raw project attachment/lookup before shutdown.
Startup failures also retain bounded stdout/stderr with session tokens redacted,
including processes which exit before announcing the local URL.
The smoke uses `--no-browser`: Windows 10/11 interactive default-browser acceptance, isolated-network verification,
signing and complete native/static redistribution review remain separate gates.
No ZIP or online launcher replaces the one-EXE target.

See [dependency versions and terms](THIRD_PARTY.md).

## Saved goal mesh limits

The browser and portable candidates use the exact engine in
`packaging/engine-ref.txt`. A saved impedance goal that exceeds the mesher's
point budget produces a failed result with the completed history, failed
parameter, search/refinement stage, resolved geometry/mesh and selected
material context. The Saved analysis view can export that failed result;
recorded executions and projects retain it without rerunning the failed solve.
It is not a successful design. No automatic retry or relaxed mesh is applied.
Other solver errors, cancellation and timeouts keep their existing behavior.
Actual platform build and execution evidence is required for each candidate;
changing the pin alone does not establish Windows or release acceptance.
