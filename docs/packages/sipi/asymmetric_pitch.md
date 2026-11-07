# Unequal pairs at fixed centre spacing

The same two-width pitch rule applies to [unequal buried striplines](asymmetric_stripline.md), whose individual vertical midpoints lie halfway between planes.

For `asymmetric_coupled_microstrip`, study and design `fixed_pitch_m=p` means
the horizontal distance between trace centres. Each row derives the bottom-edge gap:

```
gap = p - left_width/2 - right_width/2
```

Nominal half-widths plus gap must equal p within `1e-12` relative tolerance.
At least one of `left_width` or `right_width` must be an independent variable;
independent `gap` sampling is forbidden. Both widths and other geometry variables
can be sampled together. Top widths do not define pitch, and existing overlap,
taper and clipping checks still apply.

This fixes **centre distance**, not either absolute centre coordinate. The
template centres the entire bottom-width span at x=0; unequal-width changes can
translate both centres together. Finite-box effects therefore remain relevant.
Supply explicit air/box dimensions and check convergence for the intended geometry.
Existing equal-width templates retain `gap=p-width` and their prior centre rules.

All bounded corners must have valid geometry before any field solve. Unbounded
normal samples that yield nonpositive gap remain failed rows, without clipping
or resampling. Correlation still describes independent sampling variables; the
gap is derived deterministically. JSON field names and legacy canonical inputs
are unchanged. Older readers reject the new template; record engine/wheel hashes.

```python
from sipi import asymmetric_coupled_microstrip, ImpedanceDesignDocument
from sipi.study import ImpedanceStudyDocument

parameters = dict(left_width=.4e-3, right_width=.65e-3, gap=.25e-3,
    substrate_height=.5e-3, eps_r=4, left_thickness=35e-6, right_thickness=50e-6,
    left_top_width=.32e-3, right_top_width=.55e-3, tan_delta=.02,
    air_height=6e-3, box_width=12e-3)
pitch = .775e-3
mesh = dict(edge_size=2e-6, far_size=.125e-3, grade=.1)
study = ImpedanceStudyDocument('asymmetric_coupled_microstrip', parameters,
    sampling=dict(kind='corners', variables=[
        dict(name='left_width', lower=.35e-3, upper=.45e-3),
        dict(name='right_width', lower=.6e-3, upper=.7e-3)]),
    quantity='z_diff_forward', mesh=mesh, fixed_pitch_m=pitch)
for row in ImpedanceStudyDocument.loads(study.dumps()).sample_parameters():
    section = asymmetric_coupled_microstrip(**row)
    assert abs(section.traces[1].x-section.traces[0].x-pitch) < 1e-12*pitch
goal = ImpedanceDesignDocument('asymmetric_coupled_microstrip', parameters,
    variable='left_width', bounds=[.3e-3, .8e-3], target=100,
    quantity='z_diff_forward', tolerance=1, mesh=mesh, fixed_pitch_m=pitch)
result = ImpedanceDesignDocument.loads(goal.dumps()).solve()
assert abs(result.residual) <= 1 and abs(result.refined_residual) <= 1
```

The target is the [real forward-current launch impedance](asymmetric_pair.md),
not a separately tracked asymmetric mode. The saved goal reuses the same gap
constraint and requires both requested and refined meshes to meet tolerance.
This one-variable search does not optimize yield or guarantee manufacturing accuracy.
Fixed-frequency material overrides remain available with geometry-only variables.

Tests check physical centre distance, one/both widths with other variables,
sampling/JSON replay, immutable snapshots, invalid bounded and unbounded inputs,
material-study connection and the actual 100±1 Ω refined goal. The field solver
and prior independent-field/convergence gates are unchanged.

[Study](study.md) · [Unequal pair](asymmetric_pair.md) · [한국어](../../locales/ko/pages/packages/sipi/asymmetric_pitch.md)
