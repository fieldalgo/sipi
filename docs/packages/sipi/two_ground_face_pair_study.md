# Two-ground face-metal manufacturing samples

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_pair_study.md)

`TwoGroundFaceForwardPairStudyDocument` in `sipi.two_ground_face_pair_study`
stores `sipi.two-ground-face-forward-pair-study/1`. It evaluates both real forward
launch impedances from each [face-metal line](two_ground_face_panel_line.md),
using the existing ordered manufacturing-sample loop. The whole-boundary study
and all previous schemas remain unchanged. Import this capability explicitly.

The six root keys are schema, study, conductors, reference, ground_thickness_m
and panel. Nested study/3 or /4 supplies a paired template, one positive
frequency, ordered geometry/material variables, sampling and existing fixed-pitch
constraints. Faces and reference metal laws are fixed across samples. The new
constructor uses interpolation degree 16 by default; original defaults are unchanged.
Unknown/missing keys, duplicate JSON keys and nonfinite values are refused.

Source corners, sweep, uniform and normal samples retain their original order,
seed and correlation. Nominal input is admitted without fields. The complete
sample count must fit max_evaluations (2..10000) before field work. Each sample,
including duplicates, remains an attempted row. Invalid geometry/material input
and failed extraction/diagnostics are recorded; subsequent rows still run.
No row is clipped, dropped, resampled, retried or reweighted. Interrupts propagate.
Both Re(Zdd) and Re(Zcc) succeed or fail together. These are separate Ic=0/Id=0
launches from the full complex characteristic matrix, not uncoupled modal estimates.

Rows retain sampled values, resolved parameters/materials, original face-line
input, failure phase/type/cause, and available face-current and dielectric-mesh
records. The immutable result exposes descriptive statistics only if every row
succeeds. Those statistics are not manufacturing-yield confidence bounds or a
claim of measured process accuracy. There is no automatic convergence guarantee
for each arbitrary sample. The finite geometry, panel/resource, skin-depth and
remaining-core checks of the underlying line still apply.

Saved execution, requests, records, projects and CLI retain complete/incomplete
status and original failed rows. A restored project/record does not rerun fields.
This example converts a [prepared paired goal](two_ground_face_pair_goal_document.md)
into a four-corner study without solving:

```python
from sipi.two_ground_face_pair_study import TwoGroundFaceForwardPairStudyDocument

# `goal` is a prepared TwoGroundFaceForwardPairDesignDocument.
source = goal.to_dict()
study = TwoGroundFaceForwardPairStudyDocument(source["study"],
    conductors=source["conductors"], reference=source["reference"],
    ground_thickness=source["ground_thickness_m"], **source["panel"])
text = study.dumps()
assert TwoGroundFaceForwardPairStudyDocument.loads(text).dumps() == text
assert study.samples().shape == (4, 2)  # Two-variable corners source.
# Explicit field work: result = study.analyze(max_evaluations=4)
```

Validation retains independent modal roots/statistics, correlated invalid samples,
material bindings, per-row typed failures and CLI/project restoration. Registered
physical corners are width 0.43/0.44 mm by gap 0.28/0.30 mm in the 8 by 2 mm,
epsilon_r 4/tan_delta 0.003 geometry at 2 GHz. Each corner is checked at 64/128/256
panels with 0.01 relative R/L/C0 limits and an independent matrix-square-root
forward matrix at 1e-10. The two diagonal corners separately check mesh halving
and finite widths 8/16/32 mm at 256 panels with original 0.01 limits. The associated
record identifies actual results. This is finite selected-case evidence, not
infinite-domain, arbitrary-shape, browser/platform or measured qualification.

[Scalar or single launched-pair quantity samples](two_ground_face_line_study.md)
