# Saved two-ground forward pair goals

[한국어](../../locales/ko/pages/packages/sipi/two_ground_pair_goal_document.md)

`TwoGroundForwardPairDesignDocument` stores a strict
`sipi.two-ground-forward-pair-design/1` input for the
[bounded pair search](two_ground_pair_goal.md). It selects two real diagonals of
the full complex mixed-coordinate characteristic impedance, with separate
Ic=0 and Id=0 launches. These are not independent propagation-mode impedances.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_pair_goal_document import TwoGroundForwardPairDesignDocument

study = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00038, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, tan_delta=.003, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9, materials={},
    sampling=dict(kind='corners', variables=[
        dict(name='width', lower=.00035, upper=.0005),
        dict(name='gap', lower=.0002, upper=.0004)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
q = ('differential_forward_impedance_real', 'common_forward_impedance_real')
design = TwoGroundForwardPairDesignDocument(study,
    conductors=dict(positive=metal, negative=metal),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, targets=dict(zip(q, [90., 44.5])),
    tolerances=dict(zip(q, [.1, .1])), initial=[.00038, .00028],
    max_evaluations=64, panels_per_edge=128, ground_modes=128, interpolation_degree=12)
assert TwoGroundForwardPairDesignDocument.loads(design.dumps()).dumps() == design.dumps()
```

The example prepares input without field work; it does not promise that its
chosen targets are achievable. Lengths are metres, frequency Hz, targets and
absolute tolerances ohms. Study/3 or /4 preserves its ordered geometry/material
bindings, fixed pitch and fixed plane-spacing rules. Two strictly positive,
nondegenerate corner bounds are required. Metals remain fixed, with independent
whole-surface signal, top and bottom laws; no implicit perfect conductor is used.

Construction checks the nominal source, initial point (or midpoint), four
corners and their volume-only, panel-only and joint refinement inputs. Missing,
unknown, duplicate or nonfinite JSON fields are refused. Panel controls must all
be present in saved JSON. Preflight does not prove interior feasibility or any
physical accuracy. The inherited 4..10000 attempt budget includes failed solves
and optimizer probes, with three attempts reserved for refinements. Original
absolute targets and the 0.005 relative refinement gates are unchanged.

`design.solve()` and `execute_saved(design.dumps())` share the direct search.
The execution receipt retains selected geometry, history, all three refinement
inputs, separate surface-current evidence and dielectric-mesh identities. A
failed goal retains the original `TwoGroundPanelLineError` details and completed
attempts; interrupts propagate. Requests, records and projects can reopen inputs
and results without recomputing. No callable or automatic retry is serialized.

The explicit shared `galerkin.laplace_two_ground` capability is supplied by
the revision in `dependencies.json`. Missing capability produces a failed
receipt, never a fallback. Existing extraction defaults remain unchanged.
Finite-domain refinement is not outer-boundary convergence, empirical accuracy,
production yield or browser/Windows qualification. Existing schemas are unchanged.

[Identical current factors are reused within a request](two_ground_current_reuse.md); line attempts and numerical criteria remain unchanged.
