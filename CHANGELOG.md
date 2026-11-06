# Changelog

## [Unreleased]

- Add strict impedance-study JSON v2 for fixed total plane spacing, preserving v1 serialization and retaining invalid derived samples as failures.

- Add single and edge-coupled two-dielectric stripline templates, independent material sampling, and symmetric-interface Cohn validation without averaging materials in the solver.

- Add a coupled grounded-coplanar template with separate signal/ground clearances, JSON and tolerance-study support, and independent image-charge reference checks.

- Extend impedance studies to offset, edge-coupled and broadside striplines with reproducible sampling, strict quantities and horizontal fixed-pitch constraints.

- Validate installed first-party files against exact wheels before regression, reject same-version stale or shadowed imports, and preserve failed-run JSON evidence without stale passing XML.

- Extract SIPI as an independent distribution with unchanged numerical implementation, JSON contracts and regression fixtures. Retain galerkin and meshine as external dependencies.
