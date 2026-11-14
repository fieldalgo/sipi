# Saved coated panel pair goals

`PanelForwardPairDesignDocument.from_study(...)` explicitly creates
`sipi.panel-forward-pair-design/2`. It saves the two ordered source variables,
fixed coated conductors, two real impedance targets and separate panel
controls. It constructs only line/7 plus panel-line/2; it does not select a
coated FEM goal. The existing constructor taking `ForwardPairDesignDocument`
retains the version 1 contract and canonical input.

Version 2 has exactly `schema`, `study`, `conductor`, `targets_ohm`,
`tolerances_ohm`, `initial`, `max_evaluations` and `panel`. It has no nested
`design` key. The study is version 3 or 4 with `z_diff_forward`, one positive
material evaluation frequency and corners sampling with exactly two variables
whose positive bounds strictly increase. Fixed pitch, fixed stack height and
material-variable rules remain those of the source study; no preliminary
quasi-static study is solved. Metal coatings stay fixed during the search.

Targets and tolerances have exactly the keys
`differential_forward_impedance_real` and `common_forward_impedance_real`.
They are positive ohm values for Re(Zdd) and Re(Zcc) of the full complex
characteristic matrix. `initial` is null (midpoint) or two in-bounds values
in the source variables' order and units. All lengths are metres.

The example begins at a previously qualified point and performs four actual
field evaluations. For a search from a missed target, use
`initial=[.7e-3,.35e-3]` and `max_evaluations=64` in both the document and the
common execution call.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_goal_document import PanelForwardPairDesignDocument
from sipi.execution import execute_saved, normalize_saved

study = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3,
         substrate_height=.5e-3, eps_r=4., tan_delta=.02,
         left_thickness=35e-6, right_thickness=50e-6,
         box_width=.024, air_height=.010),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='corners', variables=[
        dict(name='left_width', lower=.4e-3, upper=.9e-3),
        dict(name='gap', lower=.2e-3, upper=.6e-3)]))
metal = dict(kind='layered', conductivity=58e6, relative_permeability=1.,
    coatings=[dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
              dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])
quantities = ('differential_forward_impedance_real', 'common_forward_impedance_real')
doc = PanelForwardPairDesignDocument.from_study(study,
    conductor=dict(kind='surface-boundaries', conductors=dict(positive=metal, negative=metal),
                   reference=metal, ground_thickness=35e-6),
    targets=dict(zip(quantities, [110., 40.])),
    tolerances=dict(zip(quantities, [.25, .125])),
    initial=[.0006073049209836395, .0004082505417130786], max_evaluations=4)
text = doc.dumps()
assert doc.to_dict()['schema'] == 'sipi.panel-forward-pair-design/2'
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=4)
assert output['status'] == 'complete'
assert len(output['result']['refinements']) == 3
```

Normalization checks nominal, initial/midpoint and four corner inputs,
including each future volume, panel and joint refinement, without fields.
It retains all metal, core/skin-depth, boundary and panel resource admission
rules. This is not proof of validity everywhere inside the bounds. Failed
intermediate candidates remain failed attempts; no repair or resampling runs.

The saved budget is an integer from 4 through 10000. Common execution rejects
a smaller caller budget before solving. The existing goal algorithm reserves
three real refinement attempts and requires all target and separate 0.5%
refinement gates. A solver exception retains attempts, completed history,
exact failed input and stage; it is not a partially qualified result.

`goal_input` returns fresh normalized source/control fields for either version;
`panel_options` returns a copy. The legacy `design` accessor applies only to
version 1 and raises TypeError for version 2, preventing implicit conversion
to the existing FEM design document. Use `dumps`/`loads` for exact saved replay.

Regression searches the coated asymmetric example from a missed point and
replays the exact field inputs through both direct and common execution.
Independent coating transfer, full characteristic and nonzero network checks
remain those of the [direct coated goal](layered_panel_goal.md). Its outer
checks are separate and are not automatically added by this saved wrapper.
Small mutual resistance, finite-domain and measured-accuracy limitations remain;
a successful diagonal goal does not close those accuracy questions.

[Legacy saved goals](panel_pair_goal_document.md) · [한국어](../../locales/ko/pages/packages/sipi/layered_panel_goal_document.md)
