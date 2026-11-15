# Impedance goals with explicit corner resolution

`seek_corner_impedance` performs the existing bounded one-variable impedance
search with an explicit `corner_size` in metres. Pass that value separately
from `mesh`; it must be finite, positive and no greater than the resolved
`edge_size` at each evaluation.

```python
from sipi import stripline, seek_corner_impedance

def section(width):
    return stripline(width=width, plane_spacing=.002, eps_r=4.,
                    thickness=.0004, box_width=.008)

options = dict(corner_size=2.5e-6,
    mesh=dict(edge_size=1e-5, far_size=.0002, grade=.15),
    tolerance=.1, search_tolerance=.025, max_evaluations=12)
# result = seek_corner_impedance(section, (.00055, .00065), 44.3, **options)
```

The original endpoint checks, bracketing, bisection, evaluation budget,
quantity definitions, material options and optional `return_line=True` apply.
After selection, the exact saved geometry and selected material are reused.
The final solve halves `corner_size`, `edge_size`, `far_size` and `grade`,
retaining the angle setting. The requested result must meet `search_tolerance`
(or `tolerance` when omitted), and the refined result must meet `tolerance`.
Search failure and refinement disagreement retain their original history.

The result's document is a `CornerCrossSectionDocument`. Save its full input;
the nested original cross-section alone omits the corner target. With material
overrides, retain `material_evaluation_json` too. Returned line matrices are
read-only snapshots of the selected requested mesh, not the refinement mesh.
The refined result is still mandatory when a line is requested.

`GoalMeshSizeLimitError` preserves the original cause, completed history,
failed parameter/stage and resolved corner-section input. Neither this wrapper
nor its exception increases mesh or evaluation limits. Existing `seek_impedance`
and saved design schemas keep their original mesh contract; a saved corner goal
is a separate future contract.

Actual geometry-width and uniform-material searches check both target
residuals, explicit refinement, independent quadratic capacitance and the
homogeneous impedance relation. These finite checks do not certify every
factory, global optimality, outer-domain convergence or conductor-loss accuracy.

[한국어](../../locales/ko/pages/packages/sipi/corner_goal.md)
