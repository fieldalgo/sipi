# Saved corner-resolution sections

`CornerCrossSectionDocument` stores an existing `CrossSectionDocument` and
an explicit corner target in metres. The strict `sipi.corner-cross-section/1`
object has exactly three keys: `schema`, `cross_section`, `corner_size`.
The nested cross-section retains its original version 1, 2 or 3 contract.

```python
from sipi import stripline, CrossSectionDocument, CornerCrossSectionDocument
from sipi.execution import normalize_saved

section = stripline(width=.0006, plane_spacing=.002, eps_r=4.,
                    thickness=.0004, box_width=.008)
original = CrossSectionDocument(section, mesh=dict(
    edge_size=1e-5, far_size=.0002, grade=.15))
saved = CornerCrossSectionDocument(original, corner_size=2.5e-6)
text = saved.dumps()
assert normalize_saved(text) == text
assert CornerCrossSectionDocument.loads(text).cross_section.dumps() == original.dumps()
# parameters = saved.analyze()
```

Construction and loading do not solve fields. The target must be finite,
positive, non-Boolean and no greater than the resolved `edge_size`. Accessors
return detached geometry/options, and the saved document is immutable. Duplicate
keys, unknown fields, unsupported versions and nonfinite numbers reject.
Use `saved.mesh_options` when reproducing the calculation: using only the nested
document would omit the separate corner target.

The common saved execution, request, record and project interfaces accept this
standalone section. Editing the target creates a different input; a project keeps
old records but clears the selected result for the changed design. Record artifact
declarations remain required and are host declarations, not automatic provenance
verification. Existing cross-section documents still reject a `corner_size` mesh
key. Saved line, study and goal contracts do not implicitly accept this wrapper.

Field validation reuses the four direct-control geometry cases and compares
actual matrices exactly. Record/project reopening uses explicitly cached results
and is not counted as another field calculation. See the
[mesh-control limits](corner_mesh_control.md): saving an input adds neither
absolute accuracy certification nor surface-loss convergence evidence.

[한국어](../../locales/ko/pages/packages/sipi/corner_document.md)
