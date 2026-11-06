# Changelog

## [Unreleased]

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
