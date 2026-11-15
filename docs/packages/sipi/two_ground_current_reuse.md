# Reusing identical two-ground currents within a paired goal

[한국어](../../locales/ko/pages/packages/sipi/two_ground_current_reuse.md)

The single-frequency and finite-frequency two-ground paired goal entry points
reuse successful vacuum-current factors only within one request. Nominal and
volume-only evaluations have identical current inputs; panel-only and joint
evaluations also share current inputs. Each line attempt still performs its
original admission, metal loss, dielectric extraction and numerical checks.
All four requested attempts and their histories remain visible. Repeating a
current calculation with unchanged controls is not a separate resolution test.

The private request scope retains at most eight recently used immutable factor
results. It keys the exact solver callable identity, rectangular domain size,
ordered polygon binary64 bytes, trace names/ground roles and panel, ground-mode
and interpolation controls. Dielectric metadata, frequency, surface metal and
volume mesh controls are excluded because they are not inputs to the vacuum
current solve. Their own validation and calculations remain unchanged.

A hit cannot bypass section, current-control or solver-capability admission;
metal/skin-depth admission still precedes current extraction. Failures are not
cached. Nested goals have separate scopes, and exceptions or interrupts clear
and restore the previous scope. Direct current/line calls outside a paired goal
remain uncached. No shared solver, numerical tolerance, geometry, JSON schema,
search budget, refinement criterion or outer-domain requirement is changed.

Verification checks every key component, excluded metadata, callable lifetime,
bounded eviction, failure retry, admission after a previous success, nested and
concurrent request isolation, and interrupt cleanup. The registered selected
single-frequency and finite-grid cases compare cached and uncached complete
results, including history and current/mesh observations, for exact equality.
The intended reduction is four current solves to two for four line attempts;
this count is not a claimed elapsed-time speedup. Source, installed artifacts
and browser results are reported separately for their exact versions.

See the [single-frequency goal](two_ground_pair_goal_document.md) and
[finite-frequency goal](two_ground_sampled_pair_goal_document.md) for physical
contracts and limitations. Reuse neither certifies absolute accuracy nor removes
independent panel, volume, outer-domain or measurement validation requirements.
