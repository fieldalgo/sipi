# Shared execution of saved inputs

[Saved two-parameter impedance goals](pair_design_document.md) retain two targets and full failure context.

[Saved conductivity profiles](conductivity_profile_document.md) retain the exterior port plane and check frequency budgets before integration.

[Saved periodic mixed sources](periodic_mixed_circuit.md) preserve both source kinds, time arrays and harmonic/mean powers.

[Saved mixed circuits](mixed_circuit.md) preserve per-port voltage/current kinds, ideal boundaries and topology-specific power.

[Saved periodic current sources](periodic_norton_circuit.md) retain time waveforms, open terminals and harmonic/mean powers.

[Saved Norton circuits](norton_circuit.md) preserve explicit current sources, open terminals and per-frequency powers.

`sipi.execution` gives browser Workers and local application processes the same
entry point to the existing engine documents. It performs no file, network,
browser or process operations and introduces no new numerical model.

[Physical constants](constants.md) have an explicit CODATA revision independent of the runtime.

```python
import json
from sipi import LumpedNetworkDocument
from sipi.execution import normalize_saved, execute_saved, saved_schemas

document = LumpedNetworkDocument([0, 1e9], resistance=10, inductance=2e-9)
text = normalize_saved(document.dumps())
result = execute_saved(text)
assert result["status"] == "complete"
assert result["input"] == document.to_dict()
wire_text = json.dumps(result, allow_nan=False)
print(result["result"]["network"]["s"])
print(saved_schemas())
```

`normalize_saved` returns the document's canonical JSON with its original
schema version and resolved settings. It does not mesh or solve fields; some
network validators perform small algebraic calculations. `saved_schemas()`
lists the closed registry: cross-section/1–3, impedance-study/1–4,
impedance-design/1–3, circular-aperture/1, aperture-section/1,
aperture-study/1, aperture-design/1, transmission-line/1–6, volume-line/1,
lumped-network/1, network-assembly/1, network-transforms/1–2, circuit/1, capacitance-3d/1, network-band/1, line-length-design/1–2, tem-ports-3d/1, impedance-yield/1, yield-design/1–2, dielectric-fit/1, line-quantity-design/1–2 and line-quantity-study/1–2 and line-quantity-yield/1, periodic-network/1, periodic-circuit/1, norton-circuit/1, periodic-norton-circuit/1, mixed-circuit/1, periodic-mixed-circuit/1, conductivity-profile/1, pair-impedance-design/1–2, sampled-impedance-design/1, lossless-startup/1, rlgc-startup/1, coupled-rlgc-startup/1–4, startup-port-waves/1–9, norton-rlgc-startup/1, mixed-rlgc-startup/1, debye-rlgc-startup/1, coupled-debye-rlgc-startup/1, psd-coupled-debye-rlgc-startup/1, debye-capacitive-startup/1, debye-reactive-startup/1, multiconductor-rlgc-startup/1, multiconductor-debye-rlgc-startup/1, grid-plate-capacitance/1, strip-grid-capacitance/1, thick-grid-strip-capacitance/1, volume-grid-strip-capacitance/1, volume-grid-pair-capacitance/1.
Each name has the `sipi.` prefix. Unknown versions, duplicate keys, nonfinite
numbers (including exponent overflow) and non-text inputs are rejected.

## Result contract

`execute_saved` returns a detached ordinary dictionary with schema
`sipi.execution/1`, canonical `input`, `status`, `result` and `error`. Finite
complex scalars/arrays use `{"real": ..., "imag": ...}` with matching shapes;
real arrays become lists. It never emits NaN or Infinity tokens. The original
input is needed to interpret geometry, materials, units and validity limits.
The package version alone does not identify a development build: applications
must separately record the exact engine commit and wheel/runtime hashes.

| Input | Selected output |
|---|---|
| Cross section | ordered names, C/C0/C_loss in F/m, L in H/m; scalar z0 (ohm), effective permittivity and delay (s/m) for one signal |
| Circular/elliptical aperture | ordered names and complex capacitance in F/m; scalar for circular, matrix for elliptical |
| Study | quantity, unit, every row's index/parameters/document/value/error, failed count and summary |
| Impedance yield | all rows and P/F/U counts, inclusive limits, observed-fraction bounds, exact binomial unresolved envelope and optional target status; see [contract](yield.md) |
| Goal | quantity/unit, parameter, target/value/refined value, both residuals, completed history and resulting geometry; impedance material evaluation retained |
| Transmission/volume line | conductor names, frequency in Hz, R/L/G/C in ohm/m, H/m, S/m, F/m; network and requested diagnostics |
| Distinct-metal transmission line | additionally `conductor_boundaries`: labels, skin depths, roughness factors, complex surface impedances and per-boundary R contributions; see [contract](boundary_conductor.md) |
| Lumped/assembly/transform | final network; assembly component networks and transform source/fixture networks also retained |
| Bounded static 3D | model, ordered names, total C/energy-C in F, unit-voltage ground charge in C, mesh counts and consistency ratios; see [contract](capacitance3d.md) |
| Bounded TEM-port 3D | explicit boundary-model label, network with calculated references, port norms, mesh counts and separate full-boundary/projected power diagnostics; see [contract](ports3d.md) |
| Circuit | final network, terminal response, source/load inputs, conditioning/residuals and optional NEXT/FEXT |

A network contains `frequency_hz`, ordered `port_names`, `basis`, real positive
`reference_ohms` and complex `s`. S has shape (frequency, output port, input port).
Circuit response voltages/currents are V/A, terminations ohms, power waves `a/b`
sqrt(W), `network_power` W, and residual/condition diagnostics dimensionless.
AC uses peak phasors; DC uses the existing static power convention. NEXT/FEXT
are complex voltage ratios, not time-domain peaks or dB values. No logarithm
is taken, so a zero ratio remains representable.

This selected result format omits meshes, field solutions and nested extraction
objects. Use the direct APIs for those objects; the canonical input can replay
them. Geometry matrices do not imply symmetric even/odd modes or a unique
impedance for an asymmetric pair. Aperture C does not imply a total pad
capacitance, propagation impedance or 3D via transition.

## Failure and budgets

- `complete`: the requested base calculation returned. It is not a physical
  validation certificate. Inspect optional diagnostic status separately.
- `incomplete`: a study contains failed samples. All rows remain in order,
  with their errors, and summary is null. No resampling or partial yield is used.
  Yield assessment likewise retains unresolved rows and uses `incomplete`,
  with explicit conservative fraction/confidence bounds instead of dropping failures.
- `failed`: a goal failed its bracket, budget or refined-mesh criterion.
  `result` is null; `error` retains type/message, value unit, completed history
  and the failing parameter when the underlying API supplies it.

Malformed input and other solver errors propagate as exceptions. The transport
must present them as failures. Cancellation/timeout is the caller's responsibility;
this module does not disguise an interrupted solve as an empty successful result.

Both functions default to `max_input_bytes=262144` UTF-8 bytes. Execution's
`max_evaluations=128` accepts integers 2–10000. Study sample counts and a goal's
saved evaluation budget must fit it before field solving. Bounded TEM-port 3D
counts one evaluation per frequency before any port or volume solve. A goal keeps its
saved budget, without clamping or changing the input. These limits **do not
bound meshing, recursive algebra, memory, elapsed time or output size**.
Applications still need an isolated Worker/process, cancellation and their
own resource policy; this function is not a sandbox for arbitrary untrusted jobs.

`diagnostics=["characteristic", "modes"]` is opt-in and accepted only for
top-level transmission/volume line documents. It reuses extracted RLGC without
another field solve. Each diagnostic has its own complete/failed status;
DC rejection or an unresolved mode does not erase base RLGC/S. Mode errors
retain their frequency index/Hz when available. Matrix and mode arrays follow
the [characteristic](characteristic.md) and [mode](modes.md) contracts, including
one-watt normalization and explicit degeneracy/tracking gates.

Validation compares direct APIs and serialized results for geometry, complex
local C, shared/volume RLGC, diagnostics, study rows/statistics, goals, circuits,
Touchstone and network composition. Input ambiguity, budgets and retained
failures are checked independently. These are adapter checks; they do not
replace the numerical reference and convergence tests of each engine.

[한국어](../../locales/ko/pages/packages/sipi/execution.md)

[Fixed-candidate yield design](yield_design.md) retains every candidate and cost, simultaneous confidence and selection status. The sum of all planned samples must fit the budget before any solve. Any unresolved row makes execution `incomplete`; calculation completion is separate from candidate selection.

[Saved face lines](face_line.md) additionally retain Q, face and whole-boundary integrated currents and the original current-flux diagnostic in `conductor_boundaries`.

[Saved ground faces](ground_face_line.md) retain expanded ground-face diagnostics in line/6.

[Saved lossy goals](line_goal_document.md) check the caller budget before fields and retain attempts, phases, inputs and completed history on failure.

[Lossy studies](line_study.md) retain all rows and return incomplete with null summary when any sample fails.

[Saved periodic response](periodic_document.md) requires explicit incident samples at every final-basis port and checks the N time-sample budget before field/FFT work. Results are periodic steady-state V/I, power waves and optional discrete impulse weights, not a transient or causality certificate.

[Saved periodic circuits](periodic_circuit.md) explicitly name every Thevenin source/load and retain time responses, DC/peak harmonic diagnostics, per-frequency powers and their mean-power sums.

[Saved current-source startup](norton_startup_document.md) preserves ampere samples and separate source-shunt loss.

[Saved mixed-source startup](mixed_startup_document.md) preserves typed V/A waveforms and separate source series/shunt losses.

[Saved Debye startup](debye_startup_document.md)

[Saved coupled Debye](coupled_debye_startup_document.md) preserves matrix poles and finite terminal resistances.

[Saved PSD Debye](psd_debye_startup_document.md) explicitly preserves singular strengths.

[Saved external capacitive inputs](debye_capacitive_startup_document.md) distinguish F from F/m.

[Saved external RL inputs](debye_reactive_startup_document.md) distinguish external ohm/H/F from per-length line inputs.

[Saved three/four-signal inputs](multiconductor_startup_document.md) preserve explicit signal count, SI inputs and actual time-row budgets.

[Explicit saved version9](startup_waves_document.md) adds three/four-signal inputs with six/eight references while preserving prior versions.

[Saved bounded grid/plate inputs](grid_plate_document.md) preserve SI geometry, explicit cell counts and one static field evaluation.


[Saved bounded thin trace/grid input](strip_grid_document.md) preserves explicit geometry, dielectric regions and one physical field evaluation.


[Saved finite ground-grid inputs](thick_grid_strip_document.md) retain explicit thickness and one field evaluation.


[Saved finite trace and grid volumes](volume_grid_strip_document.md) retain both thicknesses and one field evaluation.


[Saved paired trace and grid volumes](volume_grid_pair_document.md) preserve explicit trace gap and both voltage bases.


[Saved three/four-signal Debye inputs](multiconductor_debye_startup_document.md) preserve explicit poles, signal count and actual time-row budgets.


[Explicit saved wave version10](startup_waves_document_v10.md) adds three/four-signal Debye inputs while preserving versions1–9.


[Saved multiconductor PSD Debye inputs](psd_multiconductor_debye_startup_document.md) preserve singular losses/strengths and the original time-row budget.


[Explicit saved wave version11](startup_waves_document_v11.md) adds three/four-signal PSD Debye inputs while preserving versions1–10.


[Saved multiconductor capacitive inputs](multiconductor_debye_capacitive_startup_document.md) preserve explicit external storage and actual time-row budgets.


[Explicit saved wave version12](startup_waves_document_v12.md) adds multiconductor Debye capacitive inputs while preserving versions1–11.


[Saved multiconductor series RL inputs](multiconductor_debye_reactive_startup_document.md) preserve explicit branch state semantics and actual time-row budgets.


[Explicit saved wave version13](startup_waves_document_v13.md) adds multiconductor Debye series RL inputs while retaining versions1–12.


[Explicit saved wave version14](startup_waves_document_v14.md) adds multiconductor Debye current-source inputs while retaining versions1–13.


[Explicit saved wave version15](startup_waves_document_v15.md) adds typed multiconductor Debye inputs, preserving versions1–14. The registry becomes90 schemas/37 templates at this addition.


[Explicit saved wave version16](startup_waves_document_v16.md) adds multiconductor mixed-boundary inputs, preserving versions1–15. At this addition the registry becomes92schemas/37templates.


[Saved independent-width volume inputs](asymmetric_volume_grid_pair_document.md) preserve both widths, resource budgets and full geometry identity.
