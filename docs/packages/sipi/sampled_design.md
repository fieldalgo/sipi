# Impedance goals at explicit frequency samples

`seek_sampled_impedance` adjusts exactly two positive bounded parameters to
match one real quasi-static impedance quantity at 2..64 specified frequencies.
Use `quantity='z0'` for one signal, or `z_diff`/`z_common` for an exchange-symmetric
pair. The quantities use real capacitance and vacuum inductance, with the same
symmetry guards as [pair design](pair_design.md). They are not complex lossy,
loaded or full-wave characteristic impedances.

Frequencies must be finite, nonnegative and strictly increasing. Targets and
absolute tolerances have one positive finite value per frequency, in ohms.
The two parameters have the geometry/material factories' units. `initial` is
inside the positive bounds, or defaults to their midpoint. The example starts
at known reference dimensions and needs two requested/refined attempts. Use
`initial=(.35e-3,5.5)` and `max_evaluations=64` to exercise its search.

```python
from sipi import seek_sampled_impedance
from sipi.templates import coupled_stripline
from sipi.dielectric import DebyeDielectric

def geometry(width, strength):
    return coupled_stripline(width=width, gap=.1e-3, plane_spacing=1e-3,
        eps_r=1., box_width=8e-3)

def material(width, strength):
    return {'dielectric':DebyeDielectric(2.,[strength],[1e9])}

result = seek_sampled_impedance(geometry,
    bounds=((.3e-3,.7e-3),(2.,6.)), frequencies=[1e8,1e10],
    targets=[57.23463009022641,97.84159316427296], tolerances=[.5,.5],
    quantity='z_diff', material_factory=material, initial=(.5e-3,4.),
    max_evaluations=2, mesh=dict(edge_size=1e-6,far_size=.125e-3,grade=.1))
assert len(result.history) == 2
assert result.frequencies == (1e8,1e10)
assert all(abs(r)<=t for r,t in zip(result.refined_residuals,result.tolerances))
assert result.history[0].material_sweep_json == result.history[1].material_sweep_json
report = result.to_dict()
assert report['quantity'] == 'z_diff'
```

## Models, batches and snapshots

`factory(p0,p1)` returns a cross-section. Fixed `materials` or an optional
`material_factory(p0,p1)` supply supported dielectric models; these two options
are mutually exclusive. Omitting both means empty overrides, leaving the
geometry's constitutive inputs. Both callbacks must be deterministic. Control
errors precede callbacks; signal count/order and sampled material validity are
checked before meshing. Tilted transverse tensors are rejected for the paired
quantities. Ordered signal names stay fixed throughout search.

Each attempted parameter batch contains geometry, material encoding, field
extraction and diagnostics. A batch uses one mesh for vacuum capacitance and
all frequency-specific complex capacitances through `dispersive_line`. Each
uncached attempt counts once, including failed attempts and Jacobian probes;
cache hits do not count. This is a batch budget, not a field-solve count.
`max_evaluations` is 2..10000, default 64, reserving one final refinement.
It does not limit memory, internal solves or elapsed time; callers own cancellation.

Each completed `SampledImpedanceEvaluation` identifies its `quantity` and retains `input_json` and
`material_sweep_json` with exactly `frequencies_hz` and encoded `materials`.
Use both snapshots to replay that row. The selected geometry and material
sweep are frozen for refinement, without calling either factory again. Resolved
`edge_size`, `far_size` and `grade` are halved; other mesh and physical inputs
remain fixed. Every sampled target must pass on both meshes. A starting point
already within all tolerances still requires this refinement attempt.

`SampledImpedanceDesign` exposes both results/residual vectors, chosen inputs,
frequency/quantity metadata and complete history; `to_dict()` returns detached
JSON-compatible values. `SampledImpedanceGoalError` preserves quantity,
frequencies, attempted count, stage, failed parameters, original cause and
available current inputs alongside completed rows. Failed model construction
does not invent a current mapping from the previous row. Encoded models remain
available if field validation fails. No saved input schema or callable
serialization is added by this API.

## Numerical policy and independent acceptance

The existing two-parameter policy is shared with paired goals: normalize
parameters to [0,1], residuals by tolerances, use 1%-interval central/one-sided
Jacobian probes and bounded SciPy `least_squares` with `xtol=ftol=1e-4`,
`gtol=1e-3`. An optimizer success flag is insufficient if any target misses.
Rank deficiency, initial-point acceptance or local convergence do not establish
unique parameters or a global optimum. Failed geometry is not clipped/resampled.

The independent thin Cohn stripline fixture has gap .1 mm, plane spacing 1 mm,
width .5 mm and homogeneous Debye eps_inf=2, strength=4, pole=1 GHz. Its two
differential targets at .1/10 GHz are those above. From (.35 mm,5.5), recovered
width and strength must each be within 2% of the reference. Requested mesh
`(1um,.125mm,.1)`, half refinement, box16 mm and independent Cohn values at the
selected inputs must all meet .5 ohm per sample. First/selected batch replays
agree at relative 1e-10. Separate scalar/common tests include DC, check one
mesh per requested/refined batch, and compare individual-frequency extraction
and homogeneous vacuum/sqrt(Re(eps)) scaling at relative 1e-10.

These are explicit numerical gates, not measured-board accuracy. The finite
frequency grid constrains only its listed points; behavior between them is
unconstrained. Material dispersion extrapolation, automatic poles, complex
lossy objectives and continuous-band optimization are outside this contract.
The caller must establish model validity and identifiability. No browser,
application-engine or Windows acceptance follows from these engine checks.

[Pair targets](pair_design.md) · [Material targets](pair_material_design.md) ·
[한국어](../../locales/ko/pages/packages/sipi/sampled_design.md)
