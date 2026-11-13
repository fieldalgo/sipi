# Saved quasi-static frequency inputs

[한국어](../../locales/ko/pages/packages/sipi/quasistatic_line_document.md)

`QuasistaticLineDocument` saves an explicit or editable cross-section and a
uniform-line frequency calculation. It reuses the existing quasi-static field
and network engines. Loading validates inputs without meshing or solving;
`analyze()` extracts the cross-section once and returns `line`, `network` and
canonical `input_json`. It does not write files.

```python
from sipi.template_document import TemplateSectionDocument
from sipi.quasistatic_line_document import QuasistaticLineDocument
from sipi.execution import execute_saved

section = TemplateSectionDocument('stripline',
    dict(width=.5e-3, plane_spacing=1e-3, eps_r=4, tan_delta=.01),
    mesh=dict(edge_size=8e-6, far_size=.3e-3, grade=.25))
plan = QuasistaticLineDocument(section, [0, 1e8, 2e8],
    resistance=5.3, length=.075, z_ref=47)
text = plan.dumps()
result = QuasistaticLineDocument.loads(text).analyze()
receipt = execute_saved(text)
```

Strict `sipi.quasistatic-line/1` contains exactly `schema`, `section`,
`frequency_hz`, `resistance_ohm_per_m`, `length_m`, `reference_ohms`.
`section` is an existing cross-section or template-section document. Editable
inputs retain the factory parameters, exact geometry and resolved mesh; raw
geometry remains raw. Frequencies are a nonempty, finite, nonnegative,
strictly increasing array in Hz. Resistance and length are finite nonnegative
scalars in ohm/m and m; reference impedance is a finite positive scalar in ohm.
Missing/extra keys, duplicate JSON keys, unknown versions, booleans and
nonfinite numbers in numeric fields reject. Returned dictionaries are copies.

The resistance is **supplied**, equal on every signal and diagonal in conductor
coordinates. It must include any return contribution the caller intends.
The engine uses extracted C/L and constant-tangent G(f). It does not infer
copper resistance, skin effect, roughness, internal inductance or material
dispersion. Use the separate transmission-line material/metal contracts when
those models are intended. Frequency-grid acceptance is not a quasi-TEM
validity or accuracy certificate; check mesh and outer-domain convergence.

The common execution result retains C, C0, C_loss and L plus the full complex
single-ended network, ordered near signals then far signals. A pair's full
matrix is retained even when it is asymmetric. The diagnostic options for
frequency-dependent transmission-line documents are not accepted here.

Validation includes independent V/I boundary equations with matrix exponentials,
DC series-resistance and zero-length through limits, reciprocity/passivity,
exact direct/saved matrices, and one field extraction. These checks concern
this serialization/propagation contract, not measured manufacturing accuracy.
