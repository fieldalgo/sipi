"""Explicit two-material Cartesian corners for settings acceptance."""
import json
from paired_material_cases import material_study
from material_normal_form_cases import normal_study
from sipi.execution import normalize_saved, execute_saved


def corner_study(*, reversed_order=False, edited=False):
    document = material_study('tensor').to_dict()
    variables = [dict(name='x', lower=2.8 if edited else 2., upper=3.4 if edited else 4.),
                 dict(name='y', lower=4.3 if edited else 4., upper=5.2 if edited else 6.)]
    if reversed_order:
        variables.reverse()
    document['sampling'] = dict(kind='corners', variables=variables)
    document['material_evaluation']['frequency_hz'] = 2e8 if edited else 1e8
    return json.loads(normalize_saved(json.dumps(document)))


def cases():
    rows = [dict(name='reversed' if reverse else 'ordered',
                 original=corner_study(reversed_order=reverse),
                 input=(doc := corner_study(reversed_order=reverse, edited=True)),
                 execution=execute_saved(json.dumps(doc))) for reverse in [False, True]]
    document = normal_study('constant', mixed=True)
    rows.append(dict(name='mixed-normal', input=document, execution=execute_saved(json.dumps(document))))
    return rows


if __name__ == '__main__':
    print(json.dumps(cases(), allow_nan=False))
