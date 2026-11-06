# Changelog

## [Unreleased]

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
