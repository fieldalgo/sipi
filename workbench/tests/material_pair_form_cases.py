"""Bounded paired material settings cases; runtime parity, not a physical reference."""
import json
from paired_material_cases import pair_material_goal
from sipi.execution import execute_saved, normalize_saved


def cases():
    original = json.loads(pair_material_goal().dumps())
    rows = []
    for name, budget in [('changed', 64), ('budget-failure', 2)]:
        document = json.loads(json.dumps(original))
        document['targets_ohm']['z_diff'] = 101.
        for variable in document['variables']:
            variable['bounds'] = [2.2, 5.8]
        document['initial'] = [3.2, 3.5]
        document['material_evaluation']['frequency_hz'] = 2e8
        document['max_evaluations'] = budget
        execution = execute_saved(normalize_saved(json.dumps(document)))
        rows.append(dict(name=name, original=original, input=document, execution=execution))
    return rows


if __name__ == '__main__':
    print(json.dumps(cases(), allow_nan=False))
