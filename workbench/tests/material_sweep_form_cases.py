"""Changed sweep controls and unchanged normal sampling for actual UI checks."""
import json
from paired_material_cases import material_study
from sipi.execution import execute_saved, normalize_saved


def edited_study(kind):
    data = material_study(kind).to_dict()
    data['sampling']['count'] = 5
    data['sampling']['variables'][0].update(lower=1, upper=5)
    data['material_evaluation']['frequency_hz'] = 2e8
    return json.loads(normalize_saved(json.dumps(data)))


if __name__ == '__main__':
    rows = [dict(name=kind, original=material_study(kind).to_dict(),
                 input=edited_study(kind), execution=execute_saved(json.dumps(edited_study(kind))))
            for kind in ['constant', 'debye']]
    normal = material_study('mixed-normal').to_dict()
    rows.append(dict(name='mixed-normal', original=normal, input=normal,
                     execution=execute_saved(json.dumps(normal))))
    print(json.dumps(rows))
