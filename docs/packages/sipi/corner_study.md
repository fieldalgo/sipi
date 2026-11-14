# Corner-controlled geometry and material samples

`CornerImpedanceStudyDocument` applies a fixed explicit corner target to an
existing impedance study. Its strict `sipi.corner-impedance-study/1` object
has `schema`, `study` and `corner_size` keys. The nested study retains versions
1–4, template/quantity admission, sampling, fixed-pitch/spacing constraints and
material-variable bindings.

```python
from sipi import CornerImpedanceStudyDocument
from sipi.study import ImpedanceStudyDocument

study = ImpedanceStudyDocument('stripline', dict(width=.0006,
    plane_spacing=.002, eps_r=4., thickness=.0004, box_width=.008),
    quantity='z0', mesh=dict(edge_size=1e-5, far_size=.0002, grade=.15),
    sampling=dict(kind='sweep', count=2,
        variables=[dict(name='width', lower=.00055, upper=.00065)]))
saved = CornerImpedanceStudyDocument(study, corner_size=2.5e-6)
assert saved.samples().shape == (2, 1)
assert CornerImpedanceStudyDocument.loads(saved.dumps()).dumps() == saved.dumps()
# result = saved.analyze(max_evaluations=2)
```

The finite positive corner target cannot exceed the nested study's resolved
nominal `edge_size`. It stays fixed across samples. Each constructed row
retains a [corner-section snapshot](corner_document.md); material overrides
remain in the original study and, for sampled materials, the row's material
evaluation. Replaying only the geometry does not reproduce material overrides.

The original sample sequence is unchanged. Every planned row is attempted,
including duplicates and rows after a failure. Invalid unbounded normal samples
are retained as failures, never resampled. The caller's evaluation budget is
checked before fields. Statistics exist only if all rows succeed and describe
the listed finite samples; they are not a production-yield certification.

Material-only rows can reuse one exact geometry-and-corner snapshot's mesh and
vacuum capacitance within a call. Every material is evaluated again. A changed
geometry or corner target has a different cache key. Common saved execution,
requests, records and projects retain the complete wrapper and row inputs.
No new default or implicit admission in existing goal contracts is introduced.

Validation includes actual width samples with separate finer meshes and an
independent quadratic capacitance reference; uniform-material samples preserve
the analytic inverse-square-root impedance relation while reusing a mesh.
Original studies retain their regression results. These checks do not establish
loss accuracy or convergence of every sample or template. Refine the corner,
edge, far and grade controls together when comparing full resolution levels.

[한국어](../../locales/ko/pages/packages/sipi/corner_study.md)
