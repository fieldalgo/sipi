"""Existing single-variable normal sampling contract for settings acceptance."""
import json
from paired_material_cases import material_study
from sipi.execution import normalize_saved, execute_saved


def normal_study(kind, *, mixed=False, seed=9):
    document = material_study(kind).to_dict()
    document['sampling'] = dict(kind='normal', count=4 if mixed else 6, seed=seed,
        correlation=[[1.]], variables=[dict(name='dk', mean=2. if mixed else 4., std=2. if mixed else .2)])
    return json.loads(normalize_saved(json.dumps(document)))


def cases():
    rows = [dict(name=kind+('-mixed' if mixed else '-complete'),
                 input=(document := normal_study(kind, mixed=mixed)),
                 execution=execute_saved(json.dumps(document)))
            for kind in ['constant', 'debye'] for mixed in [False, True]]
    document = normal_study('constant', mixed=True, seed=10)
    rows.append(dict(name='constant-seed', input=document, execution=execute_saved(json.dumps(document))))
    return rows


if __name__ == '__main__':
    print(json.dumps(cases(), allow_nan=False))
