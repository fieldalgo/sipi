# Differential pair preview

[한국어](PAIR_PREVIEW.ko.md)

The local review entry is `/pair-preview.html` on the existing workbench server.
Start `python workbench/desktop/main.py --no-browser`, and insert
`pair-preview.html` between the printed origin slash and `#token=…` fragment.
Installed wheels include the same page; launch `python -m sipi gui --no-browser`.
Keep the printed token private. This does not publish a website.

This focused entry reuses the existing engine, LocalTransport/BrowserTransport,
and `sipi.template-section/1` input format. It offers equal rectangular
microstrip and centred stripline pairs, constant uniform relative permittivity,
ideal ground planes and lossless quasi-static differential/common impedances,
plus per-metre conductor loss (see below). It does not compute manufacturing
yield, broadband compliance, channel insertion loss or three-dimensional
transitions. The ordinary workbench remains available.

Enter millimetres, relative permittivity and explicit box/air dimensions.
Find width holds the edge-to-edge gap fixed and varies both widths together.
The existing bounded search and separate mesh check must both meet the requested
target tolerance; no search criteria or numerical tolerances are relaxed.
Single calculations do not check mesh convergence. Target refinement does not
establish outer-boundary convergence. Exported records retain the original
request, exact selected geometry, matrices, mesh, search history and engine info.
Engine version alone is not a build identifier; retain the source/wheel hashes
with acceptance evidence.

Save design downloads canonical editable JSON with the current geometry and
resolved mesh. It does not save target settings or a result; export the calculation
record before saving inputs. Reopening keeps exact SI values and saved mesh,
and requires a fresh calculation. Unsupported shapes/material settings are
refused, not silently removed. Editing, failed opening, cancellation or a failed
calculation hides the prior result. A cancelled task must finish stopping before
another can start. No collection server, telemetry or design upload is added.

Run the real Chromium acceptance from the repository root:

```sh
SIPI_PYTHON=python PYTHONPATH=src node workbench/tests/pair-preview-browser.mjs OUTPUT
```

For an independently staged browser runtime, add its directory as a second
argument. The existing browser staging command copies this page and sets its
runtime marker. An old staged engine does not validate current code: record
exact manifest, source, wheel and UI hashes. Test records include two real
calculations and two 100-ohm searches, exact save/reopen, input invalidation,
invalid geometry, cancellation/restart, mobile overflow and external requests.
These checks verify this workflow, not all parameter values or all browsers.
Numerical parity, independent physical references and redistribution review
remain separate requirements before public use.

## CCL condition comparison

The initial dimensions and permittivity are illustrative, not a supplier grade.
Material labels and source/measurement notes are user-provided context only;
they do not select a material law, frequency, temperature or loss model.
After calculating, **Keep result as A · start B** freezes that complete record
and leaves its inputs ready for editing. Change permittivity or stackup inputs,
then calculate or search a width for B. The table shows both selected geometries,
calculation types and target checks; a width search displays the selected width,
not the initial search width. Differences can reflect geometry, mesh and target
settings as well as material changes, and do not qualify a material.

Editing, opening, failures and cancellation clear B but retain A until explicit
replacement/clear or page reload. A is an in-memory snapshot, not autosaved.
**Export A/B records** downloads a `sipi.preview-comparison/1` report with `a`
and `b`, each holding the original request, complete engine result and material
label/notes. It is a report, not an engine input or reopenable project. The
existing editable design schema is unchanged and does not store these labels,
notes, target settings or A/B results. On design reopen, material identity is
reset to unidentified; enter context and recalculate. Save the comparison report
before closing the page. No HTML from user labels is interpreted.

Browser acceptance also changes dielectric permittivity in each template,
checks immutable A/exact B exports, notes, selected geometry, stale-result
handling, explicit clear, and rendering of markup-like labels as plain text.

## Numeric input arrows

Use the up/down buttons or ArrowUp/ArrowDown for small changes: trace width,
gap, substrate height/plane spacing and width-search bounds change by 0.01 mm;
copper thickness by 0.001 mm; box width and air height by 0.1 mm; relative
permittivity by 0.1; target impedance by 1 ohm; and target tolerance by 0.01 ohm.
The controls respect each field's minimum. You can still type any valid decimal;
opening a design or receiving a calculated width does not round it onto a step grid.
Changing a value invalidates the current result as before.
On touch screens the arrow buttons are wider so that each is easier to tap.
Tab skips the arrow buttons; in a focused field, ArrowUp/ArrowDown do the same.

## Task-specific results

The compact workbench places the cross-section inputs beside two distinct tasks.
**Impedance result** shows single-calculation status, results and
errors. **Find trace width** keeps search progress, cancellation,
selected width, refinement and search errors beside the target fields. A successful
search applies its exact selected width to the cross-section inputs; its result
stays beside the target controls. The file controls have their own status message.

On wide screens **Impedance result** sits directly below **Calculate impedance**
in the right column, and **Find trace width** sits below the drawing with its
four target fields in one row. Narrow screens stack drawing, inputs, impedance
result and width search in that order, so each result follows its button.

Each status line shows its state: a turning marker while a task runs, a green
line after a completed calculation, search, save or open, and a red line
starting with **Error** when it fails. The boundary table states its width
unit (mm). The colours repeat the text; they do not replace it.

When you start a calculation, search, save or open from the keyboard, focus moves
to **Cancel** while the task runs (Enter cancels it). When the task finishes or is
cancelled, focus returns to the button that started it.

If the target is not bracketed, the width-search panel lists the two actual boundary widths
in mm and their differential impedances in ohms. It suggests reviewing the range,
target or stackup without changing your inputs. The two boundary samples do not
prove that another range can reach the target. Raw search history remains available
under failure details. Any edit or new action clears stale result/error messages;
the explicitly retained A snapshot remains available. Numerical search and
refinement criteria are unchanged.

## Structure presets and drawing

The left library contains four original examples: Surface pair and Compact surface
(microstrip), Buried pair and Thin core pair (centred stripline). Selecting one loads
all cross-section dimensions, Dk and calculation boundaries, resets the imported or
search-resolved mesh to automatic, and resets material context to an example.
It clears the latest result and errors while retaining baseline A and the current
width target, bounds and tolerance. Presets are illustrative starting points, not
supplier grades or promises of a particular impedance. No third-party drawings,
model identifiers or material libraries are included.

Select W, S, H, T or εr on the cross-section to focus its input. The controls also
accept Tab followed by Enter or Space. Inputs and drawing highlight together.
Geometry edits and a successful width search change the preset label to **Custom
dimensions**. Opening a saved design also uses that label and retains its exact
values and mesh. A preset click is an explicit replacement of the current geometry.

The bounded drawing proportions keep dimension labels readable; it is a schematic,
not a scaled layout or a fabrication coupon. W is each trace width, S the edge-to-edge
gap, H the substrate height or total ground-plane spacing, and T copper thickness.
For stripline the traces remain centred between the planes. The full workbench
continues to provide the broader set of supported engine structures.

## Conductor loss

**Conductor loss** sits below the width search. Enter the conductivity in MS/m
(58 for annealed copper), the surface roughness (smooth, or the empirical
Hammerstad correction with an RMS height in µm) and up to 16 frequencies in GHz
separated by commas. **Calculate conductor loss** uses only existing public
engine paths: it resolves the current cross-section with the ordinary
`document` action, then runs a saved `sipi.transmission-line/8` line through
`saved-analyze` with the `modes` diagnostic. Line/8 uses the panel conductor
currents by default, and the engine saves its default panel controls
(64 panels per edge, 512 ground modes, interpolation degree 14 for both pair
structures). The page chooses no numerical settings. Traces and the ground plane
use one surface metal; the ground thickness is the copper thickness T. The line
is 1 m long with a 50 Ω port reference, which does not affect the per-metre
values shown.

For each frequency the table shows the self and mutual resistance in Ω/m, the
differential and common conductor attenuation in dB/m, and the dielectric
attenuation of both modes in a separate column. The attenuation is the engine's
single-mode contribution `alpha_conductor` (Np/m, converted with 20/ln 10);
the differential mode is the one whose conductor voltages have opposite signs.
This preview keeps tan δ = 0, so the dielectric column is zero. The values are
per-metre line properties, not insertion loss of a terminated channel.

A calculation usually takes a few seconds (about 5 s for each preset at three
frequencies on the local Linux build); some cross-sections take tens of seconds,
and the first browser-runtime calculation also loads the engine. The status
line counts the elapsed seconds, and **Cancel** stops the calculation. The
engine refuses inputs outside its conductor model (for example a skin depth
too large for the copper thickness, or T = 0); the message appears in red and
nothing is retained.

A geometry, preset, material-note, open or width-search change, or any change of
the loss inputs, clears the loss result. Calculating the impedance clears it as
well; calculating loss keeps the impedance result. **Export loss record**
downloads `sipi-pair-conductor-loss.json` with the geometry request, the loss
settings, the exact line/8 text, the engine's `sipi.execution/1` result
(R, L, G, C, network and modes) and the material labels. `execution.input` is
the normalized line/8 document and can be run again with `sipi run`. Loss
settings are not stored in the saved design: its `sipi.template-section/1`
format is unchanged, and existing design files open as before. The A/B
comparison still compares impedance only.

The browser acceptance test calculates the Surface pair loss, checks the line/8
input, panel controls and displayed values against the exported engine result,
then checks a refused frequency, cancellation and invalidation by an edit.
These checks ran on Linux Chromium with the local native engine only; the
staged browser (Pyodide) runtime, other browsers and operating systems were not
checked.
