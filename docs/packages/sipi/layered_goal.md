# Saved goals with fixed metal coatings

Explicit `sipi.line-quantity-design/4` connects [layered surface metals](layered_metal.md)
to the existing one-variable lossy goal search. It builds transmission-line/7
snapshots. Versions 1 through 3 keep their previous line/6 inputs and accepted
quantities; the constructor still defaults to version 1.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_goal_document import LineQuantityDesignDocument
from sipi.execution import normalize_saved

source = ImpedanceStudyDocument('stripline',
    dict(width=.5e-3, plane_spacing=1e-3, thickness=50e-6,
         eps_r=4., tan_delta=.02, box_width=4e-3),
    quantity='z0', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05),
    sampling=dict(kind='sweep', count=2,
        variables=[dict(name='width', lower=.3e-3, upper=.8e-3)]))
metal = dict(kind='layered', conductivity=58e6, relative_permeability=1.,
    coatings=[dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
              dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])
goal = LineQuantityDesignDocument(source,
    conductor=dict(kind='surface-boundaries', conductors={'signal': metal},
                   reference=metal, ground_thickness=35e-6),
    quantity='impedance_real', target=50., tolerance=.5, max_evaluations=24,
    schema='sipi.line-quantity-design/4')
assert normalize_saved(goal.dumps()) == goal.dumps()
```

`goal.solve()` searches the bounded geometry or dielectric variable. Coating
thickness, conductivity and permeability remain fixed. Scalar targets are real
characteristic impedance in ohms or propagation attenuation in Np/m. Paired
targets are explicitly forward-launch real differential or common impedances;
the full asymmetric characteristic matrix is retained. They are not finite-load
impedance or insertion loss, and no simultaneous two-variable search is implied.

The selected input and its separately refined mesh must both meet the same
requested absolute tolerance. The input snapshots preserve the layer order,
material values and source constraints. Invalid cores, skin-depth failures,
unbracketed targets and exhausted budgets keep the original attempts, completed
history and failure stage. The search does not clip, repair or replace a failed
candidate. Parsing and budget checks do not run field solves.

Outer-domain validity is separate from the search's mesh check. Tests include
a finite stripline target with an independently doubled box, direct API replay,
scalar 2x2 transfer and paired 4x4 forward-eigenspace comparisons. Transfer
comparisons use the extracted RLGC and therefore do not independently validate
field accuracy. The local planar coating model retains its documented geometric
limits; these checks do not establish measured foil accuracy or all-geometry
convergence. The result is a bounded candidate, not a global optimum or a
manufacturing yield certificate.

[한국어](../../locales/ko/pages/packages/sipi/layered_goal.md)
