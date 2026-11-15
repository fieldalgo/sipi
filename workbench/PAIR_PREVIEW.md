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
