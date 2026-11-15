# SIPI product and calculation boundaries

[한국어](architecture.ko.md)

Status: responsibility and extraction design, inspected against `fb3abe6`.
This document does not create a distribution, namespace, repository, web route
or release. The existing `sipi` imports, CLI and versioned documents remain
unchanged. SIPI is the product; transmission-line design is its first focused
workflow. A calculation library and a user-facing product need not have the
same scope, distribution boundary or release schedule.

## Responsibilities

| Boundary | Owns | Representative current implementation |
| --- | --- | --- |
| Shared numerical packages | General meshes, elements, field assembly and numerical solves; no SIPI product dependency | External `galerkin` and `meshine`, pinned by [dependencies.json](../dependencies.json) |
| Transmission-line domain | Cross-sections, materials, per-length RLGC extraction, modes and uniform-line propagation; line-specific inverse design, tolerance studies and convergence assessments | [crosssection.py](../src/sipi/crosssection.py), [templates.py](../src/sipi/templates.py), [quasistatic.py](../src/sipi/quasistatic.py), conductor/dielectric models, [line_model.py](../src/sipi/line_model.py), [propagation.py](../src/sipi/propagation.py), design/study documents |
| Shared network and circuit domain | Ordered ports, reference impedances, network data, composition, termination, excitation and interchange, usable by more than one physical model | [network.py](../src/sipi/network.py), [connection.py](../src/sipi/connection.py), [termination.py](../src/sipi/termination.py), [circuit_document.py](../src/sipi/circuit_document.py), [touchstone.py](../src/sipi/touchstone.py) |
| Other physical domains | Power-plane conduction and explicitly bounded 3D analyses, with their own model contracts | [plane.py](../src/sipi/plane.py), [capacitance3d.py](../src/sipi/capacitance3d.py), [ports3d.py](../src/sipi/ports3d.py) |
| Product application | Saved-document dispatch, requests, result binding and multi-design projects | [execution.py](../src/sipi/execution.py), [execution_request.py](../src/sipi/execution_request.py), [execution_record.py](../src/sipi/execution_record.py), [project.py](../src/sipi/project.py) |
| Hosts and presentation | Forms, drawing, file access, process/Worker lifecycle, cancellation, stale-result handling and packaging | [workbench](../workbench/README.md), [cli.py](../src/sipi/cli.py), [project_io.py](../src/sipi/project_io.py), [setup.py](../setup.py) |

These are responsibility boundaries, not a file-move list. For example,
`network.py` contains both the reusable `LineNetwork` representation and
line-specific `rlgc_network`/`quasistatic_network` functions. The former belongs
to the shared network contract; the latter belong to transmission-line
propagation. A file name alone is insufficient to decide extraction ownership.
Likewise, distributed RLGC ladder dynamics belong to the line model, whereas
general excitation/termination and network interconnection contracts should be
reusable. Existing startup and circuit compositions need function-level review.

`PowerPlane` is an existing DC sheet-conduction model, not an AC PDN product.
Bounded `Capacitance3D` returns total capacitance in F, not per-metre RLGC.
The existing 3D TEM-port model requires explicit tetrahedra, homogeneous media,
two local annular TEM-admittance ports and PEC remaining walls. Its presence
does not establish arbitrary via, connector, radiation or multimode support.
These modules are not part of the two-template [pair preview](../workbench/PAIR_PREVIEW.md).
Preserve them without advertising them as qualified interactive workflows.

## Allowed dependency direction

The intended direction is consumer to provider:

```text
SIPI UI / CLI / local host / browser Worker
                 |
       application dispatch and projects
                 |
     line domain | PI domain | bounded 3D domain
                 |
      shared data and network contracts
                 |
        numerical package APIs as needed
```

This is not a requirement that every network function calls a field solver.
Domain code may call numerical APIs directly. Neither the shared numerical
packages nor a future standalone line library may import the SIPI UI, project
manager or product-wide execution registry. The application may compose domain
providers. Generic JSON validation, finite-number checks, canonicalization and
data contracts should not depend on the product-wide dispatcher.

The line library must be usable from Python without starting a browser, opening
files, creating processes or uploading a model. Standalone line documents and
their semantic validation belong with that library; multi-design project state,
host artifact observation and execution lifecycle do not. Numerical problem
admission remains with the domain; wall-clock limits, process termination and
stale-response checks remain with the host.

## Concrete coupling to resolve before extraction

Static source inspection identifies these boundaries; it is not runtime proof
that the package can already be extracted:

1. [__init__.py](../src/sipi/__init__.py) eagerly re-exports line, power-plane,
   network and other APIs. Preserve existing imports with a compatibility facade
   when implementations eventually move; copying this initializer into a smaller
   distribution would retain the broad dependency surface.
2. `LineNetwork` and shared validation helpers currently live beside line
   propagation in `network.py`. `ports3d.py` imports them. Extracting the entire
   module as a line-only dependency would make a 3D consumer depend on that
   distribution merely to represent network results.
3. `template_document.py` uses JSON helpers from `circuit_document.py` and a
   template registry from `study.py`. Separate neutral validation and template
   registration before attempting an independent section-document API.
4. `project.py` and `execution_record.py` use private helpers from circuit,
   section-document and execution modules. `project_io.py` imports an integer
   validator from `execution.py`. Move neutral helpers in a small, separately
   verified step; do not duplicate validation rules.
5. `execution_request.py` imports concrete line document types through
   `execution.py`, whose registry imports many physical models. Domain providers
   should eventually declare their supported documents and admission metadata;
   the application composes the registry. The current registry remains intact.
6. The desktop engine and UI form lists explicitly select supported models.
   Python API availability, saved-document execution, form availability and
   qualification of a particular Worker/native build are different facts.
   A future capability description must retain those distinctions.

## Contracts across the boundary

| Contract | Preserve or specify before moving code |
| --- | --- |
| Inputs | Existing schema identifier/version, SI physical values, signal/ground order, geometry, material laws and frequency range, resolved mesh and boundary settings |
| Line outputs | Per-metre units: R in ohm/m, L in H/m, G in S/m, C in F/m; ordered conductors; exact meaning of modal and forward-launch quantities |
| Network outputs | Frequency in Hz, ordered ports, positive reference impedances, inward terminal-current convention, existing `exp(+j omega t)` sign convention and complex encoding |
| Result identity | Canonical input and controls, exact engine/dependency artifacts, selected geometry and resolved settings; an unverified host declaration is not a verified build |
| Failures | Typed failure, partial results, rejected/failed samples, search history and resource-limit reason; never convert partial work into success |
| Storage | Existing JSON and project meanings; unknown versions refuse execution while retaining source input. No silent renaming or migration of schema IDs |

Cross-product adapters must declare and test unit, phase and port conversions.
A common package family does not guarantee identical conventions. Keep the
existing tolerances, fixtures, failed records and convergence requirements.

## Packaging and implementation sequence

For now, keep one repository and the existing `sipi` distribution. Do not add a
new dependency or promise an independently installable line package based on
this document. A possible future line distribution name and import path are
deliberately undecided. Separate packages may still share a repository.

1. Document ownership and current cross-boundary dependencies (this step).
2. Extract neutral validation and data contracts without changing results or
   public imports. Check existing serialization and failure behavior.
3. Separate shared network representation from line propagation, then expose a
   headless line facade while preserving the old API and saved files.
4. Let the product compose line/other-domain providers; derive host capability
   descriptions from the exact build and verified workflow coverage.
5. Consider a separately installable line distribution only when a real consumer
   needs it. Require isolated installation without the product UI/project layer,
   complete declared dependencies and notices, compatibility tests, unchanged
   numerical/reference/convergence checks, and exact installed-artifact checks.
6. Requalify the browser Worker and Windows single-EXE consumer separately.
   Package separation does not remove the one-EXE, offline calculation and
   default-browser requirements. Do not add a browser engine to the bundle.

This step changes documentation only. It does not implement steps 2–6, merge a
branch, change dependency pins or establish release readiness.
