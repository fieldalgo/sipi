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
ideal ground planes and lossless quasi-static differential/common impedances.
It does not compute conductor loss, manufacturing yield, broadband compliance
or three-dimensional transitions. The ordinary workbench remains available.

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
another can start. The pilot link opens the existing company email address in the user's mail client.
It does not send email or attach designs automatically. No collection server,
telemetry or design upload is added.

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

## Task-specific results

The compact workbench places the cross-section inputs beside two distinct tasks.
**Check current dimensions (02)** shows single-calculation status, results and
errors. **Find a width for your target (03)** keeps search progress, cancellation,
selected width, refinement and search errors beside the target fields. A successful
search applies its exact selected width to the cross-section inputs; its result
stays in section 03. The file controls have their own status message.

If the target is not bracketed, section 03 lists the two actual boundary widths
in mm and their differential impedances in ohms. It suggests reviewing the range,
target or stackup without changing your inputs. The two boundary samples do not
prove that another range can reach the target. Raw search history remains available
under failure details. Any edit or new action clears stale result/error messages;
the explicitly retained A snapshot remains available. Numerical search and
refinement criteria are unchanged.
