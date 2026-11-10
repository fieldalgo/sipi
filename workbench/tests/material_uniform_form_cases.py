"""Bounded single-material sampling inputs for settings acceptance."""
import json
from paired_material_cases import material_study
from material_normal_form_cases import normal_study
from sipi.execution import normalize_saved, execute_saved


def uniform_study(kind, *, edited=False):
    document = material_study(kind).to_dict()
    document['sampling'] = dict(kind='uniform', count=5 if edited else 8, seed=17 if edited else 9,
        variables=[dict(name='dk', lower=1. if edited else 2., upper=5. if edited else 6.)])
    document['material_evaluation']['frequency_hz'] = 2e8 if edited else 1e8
    return json.loads(normalize_saved(json.dumps(document)))


def cases():
    rows = [dict(name=kind, original=uniform_study(kind), input=(doc := uniform_study(kind, edited=True)),
                 execution=execute_saved(json.dumps(doc))) for kind in ['constant', 'debye']]
    doc = normal_study('constant', mixed=True)
    rows.append(dict(name='mixed-normal', input=doc, execution=execute_saved(json.dumps(doc))))
    return rows


if __name__ == '__main__':
    print(json.dumps(cases(), allow_nan=False))
