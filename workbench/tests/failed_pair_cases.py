"""Real retained paired-target failures; no replacement solver values."""
import json
from paired_material_cases import pair_material_goal
from sipi.execution import execute_saved, normalize_saved


def cases():
    original = json.loads(pair_material_goal().dumps())
    original['targets_ohm']['z_diff'] = 101.
    for variable in original['variables']:
        variable['bounds'] = [2.2, 5.8]
    original['initial'] = [3.2, 3.5]
    original['material_evaluation']['frequency_hz'] = 2e8
    rows = []
    for name in ['budget', 'convergence', 'refinement']:
        document = json.loads(json.dumps(original))
        if name == 'budget':
            document['max_evaluations'] = 2
        elif name == 'convergence':
            document['targets_ohm'] = {'z_diff': 500., 'z_common': 200.}
        else:
            document['tolerances_ohm'] = {'z_diff': .01, 'z_common': .01}
        text = normalize_saved(json.dumps(document))
        rows.append(dict(name=name, input=json.loads(text), execution=execute_saved(text)))
    return rows


if __name__ == '__main__':
    print(json.dumps(cases(), allow_nan=False))
