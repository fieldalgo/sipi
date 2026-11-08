# Saved goals at explicit frequency samples

`SampledImpedanceDesignDocument` stores `sipi.sampled-impedance-design/1` and
connects named template variables to the [sampled impedance API](sampled_design.md).
It saves exactly two positive bounded variables and one real quasi-static
quantity (`z0`, `z_diff` or `z_common`) at 2..64 explicitly ordered frequencies.
Compatible named templates reuse the existing scalar/symmetric-pair study
registry. No functions or executable code are serialized.

The example starts at the reference dimensions, so two attempts cover the
requested and refined meshes. A distant initial point needs a larger saved
budget, for example 64 with `initial=[.35e-3,5.5]`.

```python
from sipi import SampledImpedanceDesignDocument
from sipi.dielectric import DebyeDielectric
from sipi.execution import normalize_saved, execute_saved

goal = SampledImpedanceDesignDocument('coupled_stripline',
    dict(width=.5e-3, gap=.1e-3, plane_spacing=1e-3, eps_r=1., box_width=8e-3),
    variables=['width','strength'], bounds=[[.3e-3,.7e-3],[2.,6.]],
    frequencies=[1e8,1e10], targets=[57.23463009022641,97.84159316427296],
    tolerances=[.5,.5], quantity='z_diff', max_evaluations=2,
    mesh=dict(edge_size=1e-6,far_size=.125e-3,grade=.1),
    materials={'dielectric':DebyeDielectric(2.,[4.],[1e9])},
    material_variables={'strength':dict(region='dielectric',path=['strengths',0])})
text = goal.dumps()
assert normalize_saved(text) == text
out = execute_saved(text, max_evaluations=2)
assert out['status'] == 'complete'
assert out['result']['frequencies_hz'] == [1e8,1e10]
assert out['result']['evaluations'] == 2
assert all(row['quantity']=='z_diff' for row in out['result']['history'])
assert all(abs(r)<=.5 for r in out['result']['refined_residuals_ohm'])
```

## Strict input contract

Every top-level field is required: `schema`, `template`, `parameters`,
`variables`, `quantity`, `frequencies_hz`, `targets_ohm`, `tolerances_ohm`,
`initial`, `max_evaluations`, `mesh`, `fixed_pitch_m`, `fixed_plane_spacing_m`,
`materials` and `material_variables`. Unknown fields/versions, duplicate keys
and nonfinite values are rejected. Normalization returns detached canonical
copies and does not perform field work or optimization.

`variables` contains exactly two ordered objects with `name` and positive,
strictly increasing `bounds`. `initial` is null (midpoint) or two values within
those bounds. Frequencies are finite, nonnegative and strictly increasing;
targets and absolute tolerances are positive vectors of the same length, in
ohms. The parameter batch budget is an integer from 2 to 10000. Frequency order
is never silently sorted independently of the targets.

`materials` is a region-name to encoded dielectric-model object. Empty overrides
preserve geometry dielectric variables such as `eps_r`; nonempty overrides
retain existing study exclusions against competing geometry material inputs.
`material_variables` is empty for geometry-only variables, or binds one/two
listed aliases to distinct existing numeric leaves using `region` and `path`
under model `parameters`. The study's path/type/name rules remain unchanged.
Two material aliases do not establish identifiability or a unique fit.
Existing fixed pitch and total-plane-spacing constraints compose normally.

## Preflight across frequencies

The first-frequency study validator checks nominal and corner inputs and
resolves geometry/mesh constraints. Additional checks validate nominal, all
four corners and the explicit/default initial geometry and sampled models at
**every** frequency. Each geometry constructed for these additional checks is
reused across its frequency list. These are unmeshed checks outside the solve
batch budget; they do not establish validity throughout the continuous domain.

First-frequency validity is insufficient. Two rotated principal dielectric
axes may coincide as complex values at one frequency and differ at another,
making a later paired input invalid. Similarly, valid diagonal endpoint tensors
can have a tilted initial tensor between them. The saved contract rejects these
cases before fields rather than postponing the error until a search attempt.
The API still preserves failures at other interior points encountered in search.

## Execution, replay and scope

`solve()` reconstructs named geometry/material callbacks and returns the existing
`SampledImpedanceDesign`. `execute_saved()` uses the existing `sipi.execution/1`
envelope, byte limit and diagnostic rules. Its `max_evaluations` must cover the
saved batch budget before solving, without clamping. A batch is one attempted
parameter tuple, not a count of frequency-specific solves; the frequency list
is separately capped at 64. Two allowed batches may therefore evaluate more
than two frequency samples. Neither limit is a time or memory guarantee.

Success retains the chosen values, quantity/frequencies, both mesh inputs,
material sweep and history. Save the goal JSON to repeat the search; each row's
quantity, geometry and material sweep permit individual replay. Failure returns
`status='failed'`, `result=None`, attempted count, stage, failed parameters,
cause type, current available inputs and completed rows with their own models.
Malformed inputs and insufficient caller budgets raise before solving.

Acceptance checks strict parsing, copies, variable/frequency order, aliases,
geometry dielectric variables, constraints, all-frequency/initial/corner model
preflight, budgets and failure transport. Actual saved execution matches the
raw API on the same canonical inputs. The thin Cohn fixture above meets .5 ohm
per sample on requested and refined meshes and in its independent expressions.
Distant-start recovery and outer-domain convergence belong to the underlying
API's separate acceptance. Only listed frequency points are constrained; no
continuous-band guarantee, global or measured material identification follows.
This schema does not update an application engine or establish browser/Windows
support; older readers reject it.

[Sampled API](sampled_design.md) · [Execution](execution.md) ·
[한국어](../../locales/ko/pages/packages/sipi/sampled_design_document.md)
