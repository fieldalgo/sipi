# Two-parameter pair impedance targets

`seek_pair_impedances` adjusts two positive bounded parameters of a callable
`factory(p0, p1)` returning a `CrossSection`. The ordered targets and absolute
tolerances are `(z_diff, z_common)`, in ohms: `2*Z_odd` and `Z_even/2` for the
existing symmetric two-signal even/odd definition. Ordered signal names must
stay fixed. Asymmetric launches, loaded impedances and complex lossy
characteristic impedances are outside this API.

The parameters have the factory's units. The default start is the midpoint;
`initial=(p0,p1)` may select another point inside the closed bounds. The example
starts near an independent thin-conductor reference solution; it still checks
the refined mesh. Use `initial=(.35e-3,.45e-3)` to exercise the width/gap search
used by the independent acceptance test.

```python
from sipi import coupled_grounded_coplanar, seek_pair_impedances

def section(width, gap):
    return coupled_grounded_coplanar(width=width, gap=gap,
        ground_gap=.2e-3, ground_width=1e-3, substrate_height=.5e-3,
        eps_r=1., thickness=0., box_width=12e-3, air_height=6e-3)

result = seek_pair_impedances(section,
    bounds=((.3e-3, .7e-3), (.1e-3, .5e-3)),
    targets=(172.45677879183611, 65.9597000672247),
    tolerances=(1.5, .5), max_evaluations=64,
    mesh=dict(edge_size=2e-6, far_size=.125e-3, grade=.15))
assert all(abs(r) <= t for r, t in zip(result.residuals, result.tolerances))
assert all(abs(r) <= t for r, t in zip(result.refined_residuals, result.tolerances))
saved_geometry = result.document.dumps()
report = result.to_dict()
assert report['quantities'] == ['z_diff', 'z_common']
```

Both requested and refined results must satisfy **both** tolerances. The
refinement uses the frozen selected geometry, halves resolved `edge_size`,
`far_size` and `grade`, and keeps `min_angle` and all physical inputs. It does
not call the factory again. Enlarging the outer box/air and establishing
physical validity remain separate checks. A narrow tolerance does not establish
measured accuracy.

## Search and cost contract

The local bounded search uses existing SciPy `least_squares`, normalized
parameters in [0,1], and residuals divided by their tolerances. Central or
one-sided numerical Jacobian probes span 1% of each parameter interval.
Termination uses `xtol=ftol=1e-4`, `gtol=1e-3`; a successful optimizer flag alone
is insufficient. A stationary point missing either target is failure.
Feasibility, continuity, uniqueness and a global optimum are not guaranteed.
A rank-deficient problem meeting both targets may succeed without determining
unique parameters. Geometry errors are retained, never clipped or resampled.

`max_evaluations` is an integer from 2 to 10000 (default 64). Each uncached
factory/extraction attempt counts, including Jacobian probes and failed
attempts. Repeated physical parameter tuples are cached. One final attempt is
reserved for refinement. An initial point within both tolerances skips search
but still needs this second attempt. Counts therefore differ from SciPy's
`nfev`. Each attempt can perform several field solves; this budget does not
limit time, memory or internal linear solves. Callers own process cancellation.

Control errors raise `ValueError`/`TypeError` before the factory. Later failures
raise `PairImpedanceGoalError`, preserving completed `history`, `attempts`,
`stage`, `failed_parameters`, available `input_json`, `cause_type` and the
original exception cause. A failed attempt has no completed history row.
For fixed materials, errors also retain `material_evaluation_json`, even if
the caller changes its original mapping during a failed run.
`PairImpedanceDesign` and its rows are frozen; document accessors return fresh
snapshots. `to_dict()` contains both mesh inputs, residuals and history. The
callable itself is not serialized, and this API adds no saved input schema.

## Fixed materials

Supply `frequency` (Hz) and `materials` together to reuse fixed scalar or
principal-axis dielectric models. Impedance uses `Re(C_complex)` and vacuum L;
it excludes conductor R and complex lossy propagation. Transversely tilted
anisotropy is rejected by the existing symmetric-pair material contract.
`material_evaluation_json` must accompany the geometry for replay and remains
unchanged between search and refinement. Parameter-dependent material factories
are not supported by this API.

## Independent acceptance

The thin all-vacuum fixture above has an independent image-Green panel reference
with four explicit finite signal/ground intervals and a backing plane at .5 mm.
A 160-panel evaluation at width .5 mm and gap .3 mm gives targets
172.45677879183611 and 65.9597000672247 ohm. From initial (.35,.45) mm, both
requested mesh `(2um,.125mm,.15)` and its half refinement must satisfy 1.5/.5 ohm.
The same selected geometry must satisfy those tolerances on box24/air12 mm
and against the independent 160-panel calculation; both recovered dimensions
must be within 2% of the reference dimensions. The existing panel suite checks
its refinement and independent electrostatic invariants.

Separate controls check a coupled affine objective under parameter unit changes,
endpoint/initial solutions, infeasible and rank-deficient objectives, actual
probe budgets, failed factories/fields, signal identity, frozen refinement and
refinement misses. Uniform dielectric scaling checks both modal impedances
against vacuum values divided by sqrt(Re(eps_r)) at 1e-10. These are explicit
fixture acceptance gates, not a general error estimate, measured-board
validation, browser parity or Windows acceptance.

[Single-parameter design](design.md) · [Materials](material_impedance.md) ·
[한국어](../../locales/ko/pages/packages/sipi/pair_design.md)
