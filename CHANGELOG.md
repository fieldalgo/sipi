# Changelog

## [Unreleased]

- Accept current-driven startup terminal responses in real-reference port-wave diagnostics, preserving source-shunt power separation and the existing saved wrapper contract.

- Save current-driven startup inputs with explicit ampere/shunt units, strict replay, independent time-row budgets and preserved voltage-source schemas.

- Add explicit current-driven coupled startup with near shunt resistances, separate Norton source power/loss and independent LC, KCL, modal and settling validation.

- Save startup port-wave diagnostics with strict nested physical inputs, explicit references, unchanged source versions and delegated delay-term/time-row budgets.

- Add explicit real-reference startup port waves with preserved terminal samples, direction-aware reflection checks, independent phasor comparisons and reconstruction/power guards.

- Save explicit coupled startup v4 with external C/R/L matrices, exact physical replay and preserved earlier-version contracts and time-row budgets.

- Add explicit passive series RL load branches to coupled startup, preserving separate line/capacitor/inductor energy and independent analytic, modal and KCL validation.

- Save explicit capacitive-load startup v3 with separate external energy, exact physical replay, time-row budgets and unchanged v1/v2 contracts.

- Add explicit passive load-capacitance matrices to coupled startup, separating internal and external energy and verifying LC, modal, KCL and settling limits.

- Add explicit coupled startup saved v2 for per-conductor ideal/open/short boundaries, preserving positive-only v1, actual time-row budgets and exact mixed-circuit replay.

- Add explicit mixed ideal/resistive/open/short boundaries for two-signal startup, preserving mutual endpoint capacitance with mass-matrix state elimination and independent analytic/ODE/refinement checks.

- Save strict two-signal RLGC startup matrices and drives, preserving actual sample budgets, full-state replay and common finite execution output.

- Add two-signal passive finite RLGC startup with full constant matrices, positive resistive ends, energy diagnostics and independent modal, asymmetric ODE and scalar-limit checks.

- Save strict finite RLGC startup inputs with independent cell and sample bounds, exact API replay and shared execution that preserves numerical failures.

- Add finite passive scalar RLGC startup circuits with explicit cells, PWL zero-state drives, energy diagnostics and independent analytic, ODE and distributed-line refinement checks.

- Save strict lossless-startup/1 inputs and execute them through the shared adapter, validating actual delay-term budgets without changing the saved hard cap or waveform model.
- Add initially unenergized lossless scalar line responses with explicit PWL drives, resistive/open/short boundaries, finite reflection budgets and independent LC dynamics checks.
- Reuse vacuum capacitance for exactly uniform scalar dielectric samples, preserving general tensor/nonuniform extraction and independently checked complex-field and convergence results.
- Add strict saved finite-frequency impedance goals, validating all sampled material states before fields and preserving batch budgets and complete replay through shared execution.
- Add bounded two-parameter impedance goals at explicit frequency samples, with batched fields, frozen material sweeps, complete failures and independent convergence checks.
- Add strict saved pair material-variable goals, validating sampled initial models and preserving both geometry and per-row material inputs through shared execution.
- Add parameter-dependent material factories to pair impedance targets, retaining per-attempt model snapshots, frozen refinement and independently checked width/material recovery.
- Add strict named two-parameter pair goals, constraint/material snapshots and shared execution with pre-solve budgets and complete failure context.
- Add bounded two-parameter symmetric-pair impedance targets with actual attempt budgets, frozen refinement, failure histories and independent field checks.
- Add unequal unbacked coplanar pairs with finite ground references, paired-width studies/goals and independent free-space and field checks.
- Add strict conductivity-profile/1 JSON and shared execution with pre-integration budgets, exterior-plane metadata and exact kernel replay.
- Add a bounded Gaussian conductivity-profile half-space kernel with explicit exterior-port position, displacement current and independent field/energy/reference-plane checks.
- Clarify common-metal surface scope and link existing Groiss, Cannonball, diffusion and individual face assignments in English and Korean.
- Add unequal planar-coated coplanar pairs with explicit ground copper, coating material studies, fixed-pitch width targets and independent field/limit checks.
- Add an unequal two-dielectric buried coplanar pair with explicit ground copper, composed pitch/stack constraints, material studies, and independently checked fields and width targets.
- Add unequal buried coplanar signal pairs with independent copper, explicit ground dimensions, fixed-pitch studies and forward-impedance goals.
- Add saved periodic mixed source circuits with explicit real waveforms, sample budgets, shared harmonic diagnostics and mean power execution.
- Add real periodic mixed voltage/current sources, ideal terminal combinations and reactive load time responses with harmonic power diagnostics.
- Add versioned mixed circuit documents with explicit per-port source kinds, frequency budgets and finite shared execution results.
- Add explicit mixed Thevenin/Norton terminal boundaries with ideal voltage, short, open and current-source support, per-port residuals and power diagnostics.
- Add strict periodic Norton circuit JSON with explicit current/shunt tables, pre-field sample budgets and shared time/harmonic power execution.
- Add real periodic Norton current-source responses with open terminals, frequency-dependent shunt currents, retained harmonic diagnostics and time/frequency power checks.
- Add versioned Norton circuit inputs and shared execution with explicit final-basis source/admittance tables, pre-field frequency budgets, extraction identity checks and per-frequency powers.
- Add explicit Norton current-source and open-terminal network solutions with passive finite shunt admittances, retained port voltages/currents, circuit diagnostics and topology-specific power accounting.
- Add unequal surface pairs with finite coplanar grounds, explicit ground thickness and saved forward-current studies/goals; validate independent fields, image-panel limits and separate domain/ground sensitivities.
- Add unequal two-dielectric stripline pairs with explicit common bottom faces, independent materials and composed fixed-pitch/plane-spacing studies; validate independent fields and mesh/box convergence.
- Add unequal-width/thickness centred buried stripline pairs with independent tapers, explicit forward-current quantity and shared two-width pitch, material, tolerance and goal contracts.

- Add saved periodic-circuit/1 with explicit Thevenin/load tables, shared extraction guards, retained harmonic diagnostics and finite time/frequency power reporting.

- Add periodic Thevenin sources with finite passive source/load feedback, explicit DC/peak harmonic normalization, retained circuit diagnostics and time/frequency power checks.

- Add saved periodic-network/1 with explicit named wave samples, retained source networks, mixed-mode conversion, pre-field time-sample budgets and common JSON execution.

- Add explicit odd-length periodic S-parameter response and discrete impulse weights, preserving port references and phase with strict DC/grid checks and real voltage/current output.

- Add explicit yield-design/2 for fixed lossy line candidates at one shared quantity/frequency, reusing conservative simultaneous bounds, full budgets and retained unresolved rows.

- Add fixed-study iid yield for lossy scalar and differential quantities, with explicit units, retained unresolved rows and conservative exact binomial confidence bounds.

- Add explicit line-quantity-study/2 for paired full-loss sampling, preserving correlated vectors, geometry/material constraints, failed rows and complete-only statistics.

- Add explicit line-quantity-design/2 for saved differential forward goals, reusing fixed pitch, stack height and material bindings while preserving scalar v1 behavior.

- Add an explicit lossy differential forward-current launch impedance goal, preserving asymmetric coupling, frozen refinement and scalar-only saved v1 contracts.

- Add scalar full-loss geometry/material studies with preserved correlated samples and failures, finite descriptive statistics and shared saved execution.

- Add saved line-quantity-design/1 using existing scalar geometry/material study inputs, strict line/6 conductors and shared execution with retained goal failures.

- Add bounded scalar-line goals for real lossy characteristic impedance or attenuation, with frozen input refinement, counted failures and complete replay snapshots.

- Add transmission-line/6 ground-face JSON with strict pre-mesh validation, retained diagnostics and existing circuit and once-extracted length replay.

- Extend reference surface assignments with four laws per finite ground trace, conserved face-current partitions, pre-mesh skin/label guards and unchanged whole-trace behavior.

- Add two-dielectric buried coplanar templates with separate material coefficients, composed pitch/stack-height constraints and saved tolerance and impedance goals.

- Add single and differential buried coplanar stripline templates with finite side grounds, saved material/tolerance studies and fixed-pitch impedance goals.

- Add strict saved dielectric-fit/1 requests and shared execution with pre-optimizer sample budgets and separate computation/fit acceptance states.

- Add fixed-pole passive Debye fitting with bounded coefficients, conditioning/optimality rejection and retained sampled residuals and acceptance limits.

- Add transmission-line/5 reference-surface JSON with shared extraction diagnostics and existing circuit and sampled-length replay.

- Add explicit reference-plane, side-wall and named ground-trace surface laws with conserved current partitions, individual skin-depth gates and unchanged common-reference behavior.

- Add line-length-design/2 with one field-source extraction, frozen RLGC replay and complete extraction/length attempt accounting through success and failure.

- Add transmission-line/4 face-metal JSON, shared mesh/C0 composition, retained face-current diagnostics and existing circuit replay.

- Add separate bottom/top/side signal surface laws with one shared PEC current solve, conserved face contributions and retained skin-depth/flux gates.

- Add a three-dielectric broadside pair with explicit outer clearances, signed offset and asymmetric forward-impedance study/material/goal reuse; validate independent fields, limits and mesh/box convergence.

- Add fixed-candidate yield-constrained selection with simultaneous confidence, explicit costs, complete failure reports and whole-set evaluation budgets.

- Add saved iid impedance-yield assessment with retained unresolved rows, exact binomial confidence envelopes and explicit target uncertainty; no measured production-yield claim is implied.

- Add transmission-line/3 saved signal/reference metal assignments on one shared mesh, retaining boundary diagnostics through common execution and existing network/circuit inputs.

- Add separate signal/reference surface-metal laws with individual skin-depth gates, retained boundary power contributions and existing roughness contracts.

- Add strict saved 3D TEM-port replay and shared execution with explicit boundary labels, pre-solve frequency budgets, calculated references and retained power diagnostics.

- Add bounded homogeneous 3D Maxwell fields with explicit annular TEM ports, PEC walls, calculated reference impedances and separate full-boundary/TEM-projection power diagnostics; validate coax propagation and independent edge FEM without implying general via or multimode radiation accuracy.

- Add saved sampled-band line-length boundary design with explicit feasible/infeasible brackets, counted evaluations and retained failure histories; no global maximum or continuous-band guarantee is implied.

- Add saved sampled network-band magnitude limits with explicit port direction, mixed-mode conversion, retained failures and finite shared-execution results.

- Add saved single material-parameter impedance goals and a Python material factory, retaining the chosen model snapshot through refined-mesh acceptance and replay.

- Add strict material-parameter study bindings with joint geometry/material sampling, retained per-row model inputs and failures, and shared saved execution.

- Explicitly freeze the dynamic NumPy FFT/linear-algebra compatibility modules used by SciPy and array-api-compat, and reject completed-build reports that omit them before executable smoke.

- Advance the workbench engine pin to the explicit-mesh 3D saved contract and exercise 3D input replay, result export and bounded capacitance in native, Worker and executable acceptance paths.

- Validate shared layered tetrahedral meshing against the closed coaxial capacitance limit, with curved-boundary/radial refinement and explicit axial-resolution checks.

- Add strict explicit-mesh 3D capacitance JSON replay and compact shared execution, preserving conductor order and boundary meaning without field solving during normalization.

- Add bounded static 3D capacitance through the shared tetrahedral assembler, with explicit PEC/ground node sets, charge/energy diagnostics, analytical and independent FEM checks; no full-wave transition or saved-input support is implied.

- Retain bounded, token-redacted executable stdout/stderr when startup fails before the UI URL, so Windows smoke failures preserve their diagnostic cause.

- Preserve hash-pinned upstream notice bytes during Windows Git checkout and verify them with a real autocrlf-enabled checkout regression.

- Pin the Windows candidate to available CPython 3.13.17 after the 3.12.14 setup failure, verify the matching cp313 wheel notices/hashes and collect only explicitly listed reports from the hidden validation directory.

- Add an independent workbench source candidate with strict saved-analysis JSON execution, retained failures, cancellation/export guards and reproducible browser/Windows packaging inputs; Windows executable and redistribution acceptance remain explicit verification gates.

- Fix extraction's SI constants to the published CODATA 2022 values so older SciPy runtimes cannot silently select a different physical reference; retain tabulation rounding and document the change from earlier runtime-dependent values.

- Add a shared strict saved-input execution adapter with finite complex JSON results, explicit budgets, retained study/goal failures and optional line diagnostics for browser and local application transports.

- Add distinct forward-mode tracking with one-watt normalization, conductor/dielectric power-loss contributions and explicit degeneracy/assignment rejection, reusing extracted RLGC without another field solve.

- Add an explicit ten-point Rz Cannonball surface input mapped to the existing causal Huray law, with strict saved selection and independent packing, relaxation and extraction checks.

- Add saved local-capacitance tolerance studies and bounded goals with shared deterministic sampling, preserved invalid rows and mandatory target checks on requested and refined meshes.

- Add local elliptical-aperture Maxwell and power-dual differential/common capacitance matrices for one or two round conductors, with independent panel/FEM references, strict saved inputs and explicit geometry/transition limits.

- Add local homogeneous circular-aperture capacitance with eccentric conductors, explicit radial/angular refinement, strict saved input and independent eccentric-circle/FEM validation; no finite-pad or 3D transition interpretation.

- Clarify the lossless fixed-geometry energy bound and nested-space assumptions behind electrostatic FEM convergence; do not imply entrywise monotonicity for complex or independently remeshed cases.

- Preserve physical centre spacing for unequal surface-pair width studies and refined goals, deriving bottom-edge gap while retaining invalid samples and legacy equal-width behavior.

- Add independently dimensioned surface pairs and an explicit real forward-current differential impedance, with saved correlated tolerance studies and refined-mesh target design while preserving symmetric-mode semantics.

- Expose power-dual differential/common characteristic matrices for asymmetric pairs, retaining cross-coupling, physical voltage/current normalization and existing forward-wave validity gates without another field solve.

- Save ordered cascades and known-fixture removal in explicit network-transforms v2, validating every intermediate port/reference before meshing and preserving per-occurrence extraction diagnostics; keep v1 input bytes and numerical gates.

- Add passive lumped series/shunt RLC branches and strict saved inputs, with exact DC limits, scaled scattering, independent circuit/reference checks, and assembly/transformation/driven-circuit integration.

- Extend normal-thickness films to single and paired finite coplanar grounds, with and without a backing plane, preserving local materials in lower-air translation and saved studies/goals; reject unresolved film features before automatic meshing.

- Add single and paired surface traces with mitered normal-thickness dielectric films, saved geometry/material studies and width goals, with independent field and convergence checks.

- Add full conductor-coordinate characteristic and forward-transfer matrices for asymmetric reciprocal RLGC, with physical branch selection, independent modal references and power-balance checks.

- Preserve fixed-frequency scalar/principal-axis materials in saved geometry-tolerance studies and bounded impedance goals, including refined-mesh replay and explicit real quasi-static impedance limits.

- Save fixed principal-axis dispersive dielectrics and reuse them in shared-mesh and volume line extraction, network assembly and driven circuits, with scalar material compatibility and independent tensor-field checks.

- Accept reciprocal passive transverse permittivity tensors in mesh capacitance extraction and real tensors with local loss tangents in quasi-TEM line parameters, using existing shared P1 kernels.

- Add planar-coated single and paired coplanar sections without a backing ground plane, with saved studies, width goals and independent field/convergence checks.

- Save explicit network assembly with ideal junctions, validated port metadata, one extraction per geometry component, and existing transformation/circuit integration.

- Add explicit named port connections and ideal Kirchhoff junctions, with independent network checks and analytic one-dimensional shunt-stub validation.

- Add single and paired unbacked coplanar templates with finite substrates and grounds, independent free-space references, saved studies and impedance goals.

- Add strict saved sequences of network reference changes and passive port reductions, with one source extraction and existing circuit-document integration.

- Add explicit open, short and finite passive port reduction while preserving retained port order, references and basis, with singular-feedback rejection and independent network checks.

- Add an explicit noncausal Groiss RMS surface-impedance correction and strict saved model selection, preserving the existing resistance-only and causal roughness definitions.

- Add planar-coated single and paired grounded-coplanar sections with finite grounds, independent field checks, JSON replay, tolerance sampling and saved impedance goals.

- Install the required scikit-fem reference tool in the test extra and CI, and report its version during installed-artifact validation instead of relying on an enriched development environment.

- Add planar-coated paired microstrip with independent electrostatic checks, section JSON replay, tolerance sampling and saved impedance design support.

- Add single/symmetric-pair propagation and exact traveling-wave conductor/dielectric attenuation contributions, reusing extracted RLGC and explicitly excluding DC and asymmetric modes.

- Add explicit near/far network cascade and removal of supplied known fixtures, with analytical and independent network checks and conditioning limits.

- Add immutable positive-real S-parameter reference changes with analytic open/short/through checks and independent scikit-rf comparisons.

- Add strict JSON design requests that preserve impedance goals, search bounds, evaluation budgets and geometry constraints while reusing bounded search and refinement checks.

- Add strict impedance-study JSON v2 for fixed total plane spacing, preserving v1 serialization and retaining invalid derived samples as failures.

- Add single and edge-coupled two-dielectric stripline templates, independent material sampling, and symmetric-interface Cohn validation without averaging materials in the solver.

- Add a coupled grounded-coplanar template with separate signal/ground clearances, JSON and tolerance-study support, and independent image-charge reference checks.

- Extend impedance studies to offset, edge-coupled and broadside striplines with reproducible sampling, strict quantities and horizontal fixed-pitch constraints.

- Validate installed first-party files against exact wheels before regression, reject same-version stale or shadowed imports, and preserve failed-run JSON evidence without stale passing XML.

- Extract SIPI as an independent distribution with unchanged numerical implementation, JSON contracts and regression fixtures. Retain galerkin and meshine as external dependencies.
