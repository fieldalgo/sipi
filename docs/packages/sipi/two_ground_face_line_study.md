# Two-ground face-metal quantity samples

[한국어](../../locales/ko/pages/packages/sipi/two_ground_face_line_study.md)

`TwoGroundFaceLineQuantityStudyDocument` in `sipi.two_ground_face_line_study`
stores `sipi.two-ground-face-line-quantity-study/1`. It combines the existing
ordered quantity-sampling loop with [face-metal lines](two_ground_face_panel_line.md).
The whole-boundary study, previous schemas and extraction defaults are unchanged.

Choose exactly one of four quantities at a single positive frequency:

| Source | Quantity | Meaning | Unit |
|---|---|---|---|
| z0 | impedance_real | Real scalar characteristic impedance | ohm |
| z0 | attenuation | Real propagation constant | Np/m |
| z_diff_forward | differential_forward_impedance_real | Re(Zdd), separate Ic=0 launch | ohm |
| z_diff_forward | common_forward_impedance_real | Re(Zcc), separate Id=0 launch | ohm |

The paired quantities use the full complex forward characteristic matrix;
they do not assume independent symmetric propagation modes. The source label
selects inputs, without executing the source's quasi-static study. To evaluate
both paired launches in one result use the [paired study](two_ground_face_pair_study.md).

The seven strict root keys are schema, study, quantity, conductors, reference,
ground_thickness_m and panel. Study/3 or /4 retains ordered geometry/material
variables, seed, correlation, fixed-pitch constraints and original sampling.
Face/coating/roughness laws remain fixed across samples. The new constructor
uses degree 16; existing defaults are unchanged. Nominal input is admitted
without fields. Unknown/missing keys, duplicate keys and nonfinite values are refused.

All samples must fit max_evaluations (2..10000) before fields. Each row remains
an attempt, including duplicates and invalid samples. Preparation, extraction
and diagnostic failures preserve their stage and available input/current/mesh
records; later rows still run. Interrupts propagate. No clipping, dropping,
resampling or reweighting is performed. Descriptive statistics require every
row to succeed and are not manufacturing-yield confidence bounds. Arbitrary
samples are not automatically certified for convergence or measured accuracy.

Shared saved execution, requests, records, projects and CLI retain the same
complete/incomplete semantics. Record/project restoration does not rerun fields.
This example prepares an attenuation sweep without calculating:

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_face_line_study import TwoGroundFaceLineQuantityStudyDocument

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1., roughness=dict(kind="smooth"))

source = ImpedanceStudyDocument("offset_stripline", dict(width=.0006,
    plane_spacing=.002, trace_height=.0007, eps_r=4., thickness=.00005,
    tan_delta=.003, box_width=.008), quantity="z0", frequency=2e9, materials={},
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05),
    sampling=dict(kind="sweep", count=3,
                  variables=[dict(name="width", lower=.00055, upper=.00065)]))
faces = dict(zip(("bottom", "top", "left", "right"),
                 [metal(sigma) for sigma in (58e6, 35e6, 21e6, 45e6)]))
document = TwoGroundFaceLineQuantityStudyDocument(source, quantity="attenuation",
    conductors=dict(signal=faces), ground_thickness=35e-6,
    reference=dict(kind="surfaces", bottom=metal(58e6), top=metal(21e6),
                   sides=None, conductors={}), panels_per_edge=64, interpolation_degree=16)
text = document.dumps()
assert TwoGroundFaceLineQuantityStudyDocument.loads(text).dumps() == text
assert document.samples().shape == (3, 1)
# Field work is explicit: result = document.analyze(max_evaluations=3)
```

Validation covers all four independent synthetic quantities, ordered/correlated
invalid samples, material leaves, failures and record restoration. The registered
2 GHz offset-line widths 0.55/0.60/0.65 mm retain independent complex sqrt(Z/Y)
and sqrt(ZY) checks at 1e-12 and 64/128/256-panel R/L/C0 changes at 0.01.
Those 8 mm boxes use 128 ground modes. Separate endpoint mesh-halving and finite
8/16/32 mm outer checks explicitly use 256 ground modes and 256 panels, with
0.01 limits on R/L/C0, real impedance and attenuation. Earlier scalar large-box
128-mode failures remain failures; the new explicit-resolution study does not
qualify the default at that larger box. Refer to associated records for actual
results. Finite selected cases do not establish infinite-domain, arbitrary-shape,
browser, cross-platform or measured qualification.
