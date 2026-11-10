# SIPI workbench candidate

[한국어](README.ko.md)

The [project workflow](PROJECTS.md) keeps input variants in the twelve-form workspace
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

The basic workspace offers twelve cross-section forms, impedance targeting,
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

## Unbacked coplanar form

**Unbacked coplanar** has one signal and two finite side ground conductors,
with no backplane. The substrate lies between lower and upper air. The outer
edges are insulating finite-domain boundaries; this is not a radiation boundary.
Gap is the bottom-edge signal-to-ground separation. Taper changes only the
signal; the ground traces remain rectangular.

In **Domain bounds**, lower air can be automatic (ten times substrate height)
or explicitly set. Inspecting or fixing it preserves the other parameters and
any fixed mesh. Editable JSON, unit changes and project variants retain exact
physical inputs. Lower air, upper air and box width are convergence controls,
not manufacturing variables in the basic tolerance form. Gap and ground width
can be sampled with the existing fixed nominal mesh policy.

The fixed-mesh vacuum width example (0.5 mm width, 0.2 mm gap, 1 mm ground
width, 0.5 mm substrate, relative permittivity 1, zero thickness, 12 mm upper
and lower air, 24 mm box; edge 1 µm, far 0.25 mm, growth 0.1) uses an independent
finite-ground free-space target of 115.58150659942925 Ω. Search bounds 0.4–0.6 mm
and tolerance 1 Ω require both the requested and refined mesh checks. This
precise example completed in the native host, but its browser width search hit
the five-minute limit. That browser run remains a failure. A separate explicit
mesh example (edge 4 µm, far 0.5 mm, growth 0.2) uses the same geometry, target,
search bounds and 1 Ω residual gates; it still performs independent refinement.
The application does not switch mesh settings after a failed run. The same
large-domain example previously reached the 300,000-point limit when automatic
width targeting pre-refined both edge size and growth before its mandatory
refinement. Automatic width targeting for this form now retains the factory's
resolved edge size and growth, while dividing its far size by four. It still
requires the independent refinement and both residual gates. Explicit meshes
and other forms retain their policies. This is a selected automatic policy,
not a fallback after an error; point and time limits remain unchanged. The
precise explicit-mesh browser failure above remains outside its acceptance. Check mesh and outer-domain convergence
for the actual material, geometry and requested accuracy. Automatic domain
sizes and a successful search alone do not establish that accuracy.

## Download sample rows as CSV

After a supported `sipi.impedance-study/4` calculation, use **Save sample table
CSV** to download every sample row in its original order. The columns identify
the input schema, impedance quantity, row index, ordered variables, impedance
in ohms and outcome. CSV uses all reported numeric digits, not the seven-digit
screen rounding. Failed impedance cells stay empty and their outcome retains
the failure reason; no row is omitted and no summary is invented.

**View saved run** offers **Save saved-run samples CSV** for that historical
execution, without changing or calculating the current input. Explicitly viewing
a saved run also permits its CSV export while preserving unrelated unapplied
settings in the current form. The historical
filename is `sipi-saved-study-samples.csv`; a current result uses
`sipi-study-samples.csv`. Editing inputs or unapplied settings clears the export;
unsupported result shapes have no CSV action. Busy and closed workspaces cannot
export. CSV is a table convenience: keep the JSON execution record and environment
manifest for full input, control and provenance details.

Files use UTF-8 with a BOM, comma-separated quoted text and CRLF records. Text
that starts with spreadsheet formula prefixes or certain control characters is
prefixed with an apostrophe; numeric cells retain their numeric values. Embedded
commas, quotes and newlines are escaped. The JSON keeps the original text.
This does not certify how every spreadsheet application interprets a file.


## Four material corner combinations

In **Saved analysis**, choose **Four material corner combinations** to edit the
two lower/upper bounds and evaluation frequency. The known two-variable
`sipi.impedance-study/4` corner form supports the constant permittivities of
two distinct principal axes in one material. The description identifies each
ordered variable and axis; reversing the input variable order preserves it.
Other bindings and shapes remain editable in JSON.

**Apply settings** validates the original and candidate before changing the input.
All four Cartesian endpoint combinations are evaluated in the saved order.
There is no random seed or sample count. Invalid material corners reject before
field calculations; calculation failures retain their row and suppress aggregate
statistics. Reported extrema describe these four points, not guaranteed extrema
inside the bounds or manufacturing yield. Geometry, angle, loss, mesh and saved
execution/project history retain their original contracts.


## Bounded uniform material samples

In **Saved analysis**, choose **Bounded uniform material tolerance** or open a
single-variable `sipi.impedance-study/4` uniform input. Edit the lower and upper
bounds, sample count (2–128), integer seed (0–4294967295) and evaluation frequency.
**Apply settings** validates the original and proposed input before replacing it;
invalid material bounds leave your original input intact. This form supports one
constant relative permittivity or one Debye strength. Other bindings remain in JSON.

The seed repeats the same sampling input. Uniform samples use the specified input
bounds; finite random samples do not prove output extremes or manufacturing yield.
This differs from the unbounded normal distribution. The sampler, geometry, mesh,
material poles and all failed rows remain unchanged. Failed calculations retain
their original row and withhold aggregate statistics. Current settings, project
restoration and historical records remain separate.


## Save a design and keep editing

Choose a template, enter its dimensions and materials, then use **Save editable
design**. **Open design** restores those fields from the downloaded JSON, so you
can edit, calculate, search a target width or run a study. This uses
[`sipi.template-section/1`](../docs/packages/sipi/template_document.md): original
template arguments, their resolved geometry and all mesh settings stay together.
Opening checks that the current engine reproduces the saved geometry exactly.
A mismatched or unsupported file leaves your current design intact.

The twelve forms are unbacked coplanar, microstrip, stripline, offset stripline, coupled microstrip, coupled stripline, grounded coplanar,
coupled grounded coplanar, planar coated microstrip, planar coated pair, coated grounded coplanar and coupled coated grounded coplanar. Other engine templates can use **Saved analysis**;
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

For **Coated coplanar pair**, two equal signals sit between the finite grounds.
**Gap** is the signal-to-signal bottom-edge gap; **Signal–ground gap** is the
separate distance from each outer signal edge to its ground. Signal taper does
not taper the grounds. The same planar coating and air-clearance definitions
apply. Targeting and studies use differential impedance, with four single-ended
ports and a mixed-mode response. Both gaps, ground width and coating dimensions
can be studied with the fixed nominal mesh. Automatic width targets retain
resolved edge/growth before the unchanged refinement, and explicit meshes are
preserved. The qualified image-panel, complex-FE, mesh/domain and air-limit
checks cover the stated symmetric geometry, not measured manufacturing accuracy.

Width-target matrix output reuses the selected requested-mesh calculation after
the separate refinement passes. It does not solve that selected mesh again.
Both runtimes pin the supporting engine; existing inputs, history and numerical
limits are unchanged. This avoids one redundant solve, without promising that
every explicit mesh will finish within the calculation deadline.

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

All project designs must use the twelve supported editable templates. Other
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

The local HTTP host sends its response before closing the sending side, then
spends at most one second discarding at most 1 MiB of unread socket data. This
keeps ordinary oversized requests from losing their rejection to a connection
reset, without raising the 256 KiB accepted-input limit or waiting indefinitely
for a stalled sender. It does not guarantee response delivery to an aborted or
unbounded sender. Windows candidate smoke checks actual oversized-request
responses before calculations, normal exit and temporary-file cleanup.

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

## Material targets from saved input

Open a `sipi.impedance-design/3` material-target document in **Saved analysis**,
check the input, run it, and export the input/result JSON. The selected material
snapshot and search/refinement history stay attached to the result. The fixed
engine reuses an identical geometry mesh and vacuum capacitance within that
search, evaluates each material anew, and builds the required refinement
separately. This does not change evaluation budgets or numerical acceptance.

The actual browser acceptance includes constant-permittivity and Debye-strength
stripline goals on native and Worker runtimes. It checks input/result export,
selected models and history, numerical agreement within relative 1e-10, and
both mesh residuals within the original 1-ohm goal tolerance. These are runtime
contract checks, not measured-board validation or a general speed guarantee.
A changed width normally requires a new mesh; existing job limits still apply.

## Paired material targets and material studies

**Saved analysis** also accepts `sipi.pair-impedance-design/2` and
`sipi.impedance-study/4`. Open the JSON, check it, calculate and export the
input/result. Pair targets preserve both selected material values and the
separate requested/refined results. Studies retain every sampled material and
failed row; one failed row leaves the summary incomplete. Identical material
geometries reuse a mesh within that analysis, while each material field is
computed again. Separate calls start with an empty cache.

The browser acceptance exercises a fixed-geometry diagonal-tensor pair goal
and constant, Debye, correlated-tensor and mixed-validity normal studies on
native and Worker runtimes. The pair case requires both requested/refined
100/34-ohm targets within the original 1/.5-ohm tolerances. Across the two
optimizers, selected parameters agree within relative 1e-4 and impedances
within 1e-5; iteration histories may differ but must retain consistent models,
geometry, budgets and refinement. Study values agree within relative 1e-10 or
absolute 1e-14 with identical inputs, row order and failure status. Exports
preserve the actual execution. Existing scalar-target criteria stay unchanged.
These bounded runtime checks do not establish measured accuracy, general
optimization convergence or automatic study mesh convergence.

## Start a saved analysis from an example

On **Saved analysis**, choose a starting example and press **Load example**.
The catalog includes an RLC network, constant or Debye material targets, paired
differential/common targets, a dielectric sweep and a correlated dielectric
study. Choosing an item only changes its description; loading it replaces the
input, clears stale results and leaves existing project history intact. Edit
the values, check them, run the analysis and save the input/result or
project to continue later. Loading is disabled during a calculation or after
shutdown. These are bounded starting inputs, not a visual editor for every
engine model or a guarantee of accuracy for edited geometries and materials.

## Read material results

Saved scalar/pair material targets show selected input values and separate
requested/refined target, impedance, residual and tolerance rows. Material
studies show the original zero-based row index, sampled input values, impedance
or retained error, and the engine's sample statistics only when all rows pass.
A failed row never becomes a partial aggregate summary. Values use the input
units and are rounded to seven significant digits on screen; raw JSON, exports
and records retain the full reported values.

Viewing a historical material record labels its table **Saved run** and uses
that record's execution, even when the current input differs. Editing input,
cancelling or starting another run clears the old table. Unsupported schemas,
unsupported errors and unavailable display shapes retain the raw JSON view. Tables
are a read-only presentation, with no additional solver or statistics step.

## Edit a material target

Load the constant or Debye material target example to open **Material target
settings**. Change the target and allowed error in ohms, positive ordered
search bounds, evaluation frequency in Hz and evaluation budget (3–128).
The form supports a single constant relative-permittivity or Debye-strength
binding in `sipi.impedance-design/3`; other target inputs retain the JSON workflow.
The quantity, material region and searched parameter are identified above the
fields. Geometry, material poles, mesh and fixed dimensions remain unchanged.

Edits are drafts until **Apply settings**. Checking, running and saving the
current design are disabled while a draft exists; **Reset form** restores the
current input's values. Applying checks the original and proposed documents
with the existing engine validator, without solving. Invalid settings leave
the input unchanged. A successful apply updates the JSON and clears previous
results, while project history remains available. You can then run, record,
save the project and reopen it. Loading another input replaces any unapplied
draft; it does not modify a historical record. The form is disabled while busy
or closed. Editing JSON remains available, and cancels acceptance of a pending
form update. Material model validity and requested/refined target checks still
apply; this is not a new optimization or accuracy guarantee.

## Inspect a failed impedance target

Saved scalar impedance targets show **Impedance target not accepted** when a
bounded search fails. The requested target, interval and every completed
evaluation remain visible, with separate search/refinement stages. The final
row is not an accepted solution. A mesh-limit failure shows its stopped attempt
separately, without inventing an impedance; zero completed evaluations is an
explicit outcome. No values are recalculated by this view.

The view supports known scalar design schemas 1–3 and their existing goal/mesh
failure contracts. Other errors or malformed display shapes keep raw JSON.
Viewing an old failure uses that saved record and leaves current input alone;
editing or recovering with a successful run clears the old failure display.
Failed records stay in project history and export unchanged. Numerical target
tolerance, mesh limits and runtime limits remain unchanged.

## Edit a material sweep

Load **Dielectric sweep**, or open a saved single-variable constant-permittivity
or Debye-strength sweep, to show **Material sweep settings**. Set finite ordered
lower/upper sample bounds, sample count (2–128) and evaluation frequency (Hz).
**Apply settings** checks both the original and proposed `impedance-study/4`
input before replacing it. Existing material/endpoint checks can reject a
range; the original input stays unchanged, with no clamping or resampling.
Geometry, material poles, mesh, quantity and sampling kind stay in the document.

Drafts block running and saving the current input until applied or reset.
Switching inputs replaces the draft and shows only that input's supported
fields. Explicitly reloading the same example, file or project also resets the
draft, even when the saved input bytes are identical. Editing raw JSON resets
the form draft too. Projects restore current settings while historical records stay
unchanged. Unsupported sampling inputs keep their
JSON workflow. Their existing failed rows and withheld
aggregate summary remain intact. A completed finite sweep is a set of sampled
values, not a guarantee of manufacturing bounds or continuous-range coverage.

## Edit two material targets

Load **100 Ω differential / 34 Ω common targets** to show **Paired material target settings**.
Set differential and common-mode targets and allowed errors in ohms, positive
ordered bounds for each variable, an initial value inside each interval,
evaluation frequency in Hz and an integer evaluation budget from 2 to 128.
Variable 1 and 2 follow the saved variable order; the description names each
alias and its principal material axis. Both targets must pass on the requested
and refined meshes. This is a local search, and the evaluation budget guarantees
neither a solution nor an elapsed-time limit.

The form supports `pair-impedance-design/2` with two distinct constant
principal-axis permittivity bindings in one material, explicit initial values,
and differential/common-mode targets. Other bindings or implicit initial values
retain their JSON workflow. **Apply settings** validates the original and
candidate documents before replacing the input. Geometry, variable order,
material angle/loss, mesh and all unedited values remain unchanged.

Drafts block execution and current-input saving until applied or reset. Input
restoration and switching between pair, scalar and sweep settings discard old
drafts; hidden fields cannot affect another input. A failed pair search keeps
its original error and completed history in the raw execution record. Increasing
the budget is a new explicit input, not a reinterpretation of that failure.
Project history retains the failed and successful runs separately, while
viewing an old run leaves the current form unchanged.

## Read a failed paired target search

Known paired target failures show **Paired impedance targets not accepted**,
both requested targets and tolerances, two search intervals and all completed
evaluations in their original order. Each row includes both parameter values,
both impedances and its search/refinement stage. A budget-stopped evaluation
has a separate parameter context; it has no calculated impedance and is not
counted as an additional completed evaluation. Convergence and refined-target
failures show their reported context without selecting a solution.

This view accepts the existing `PairImpedanceGoalError` budget, convergence and
refined-target contracts for pair design schemas 1–2. Other phases, unknown
errors or malformed history retain raw JSON. Failed status and numerical
criteria are unchanged. Viewing a historical failure leaves current input
alone; a subsequent successful run clears failure presentation while keeping
the failed record in project history and export.

## Edit single-variable normal material sampling

Load **Single-variable material tolerance**, or open a saved single-variable
constant-permittivity or Debye-strength normal study. **Normal material sampling
settings** exposes the finite mean, positive standard deviation, sample count
(2–128), integer random seed (0–4294967295) and evaluation frequency (Hz).
Mean and standard deviation are dimensionless. A negative mean is not silently
changed. **Apply settings** validates the original and candidate documents;
it does not run or filter the samples.

The form supports `impedance-study/4` with one material variable and the explicit
one-variable correlation matrix `[[1]]`. The two principal-axis variables below
have a separate correlated form; other inputs keep their JSON workflow.
Geometry, material model/poles, binding, quantity,
mesh, sampling method and correlation remain unchanged. Draft, reset, input
restoration and historical-record behavior match the other settings forms.

Normal sampling is unbounded. Invalid physical samples remain in their original
row positions with errors; they are not clamped or drawn again. An incomplete
run has no aggregate summary. A seed reproduces this sampling input, and a new
seed is a new explicit input recorded separately. Sample statistics are not a
manufacturing limit, worst-case bound or yield guarantee. The original full
precision input, rows, failures and any complete summary remain in exports.

## Edit correlated principal-axis material sampling

Load **Correlated dielectric study** to edit the two saved principal-axis
constant permittivity distributions. **Correlated material sampling settings**
shows each variable's mean and positive standard deviation, input correlation
from −1 to 1, sample count (2–128), integer seed (0–4294967295) and evaluation
frequency (Hz). The description maps variable 1/2 to the saved aliases and
material axes. The variable order and bindings stay unchanged.

The form supports two distinct constant principal-axis bindings in one material
and an explicit symmetric correlation matrix `[[1,rho],[rho,1]]`. It changes both
off-diagonal entries together. The existing engine permits the rank-one ±1
boundaries: standardized draws are equal or opposite, respectively. Other
material models, variable counts and correlation shapes stay in the JSON path.

This is an input distribution correlation, not the observed finite-sample or
impedance correlation. The existing seeded sampler is unchanged. Both normal
distributions remain unbounded; invalid rows are retained without resampling
or an aggregate summary for incomplete runs. Strict original/candidate checks,
explicit apply/reset, same-input restoration and project history behave as in
the other settings forms. Geometry, material angle/loss, mesh, quantity and
all unedited settings remain unchanged. No manufacturing or yield guarantee is
inferred from the sampled results.
