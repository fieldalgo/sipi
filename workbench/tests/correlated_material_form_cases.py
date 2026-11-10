"""Existing two-material normal sampling with finite and rank-one correlations."""
import json
from paired_material_cases import material_study
from sipi.execution import normalize_saved, execute_saved


def correlated_study(name):
    if name not in ('complete', 'mixed', 'positive-rank-one', 'negative-rank-one'):
        raise ValueError('unknown correlated settings case')
    document = material_study('tensor').to_dict()
    sampling = document['sampling']
    sampling.update(count=6 if name in ('complete', 'mixed') else 4, seed=17)
    rho = 1. if name == 'positive-rank-one' else -1. if name == 'negative-rank-one' else -.4
    sampling['correlation'] = [[1., rho], [rho, 1.]]
    for index, variable in enumerate(sampling['variables']):
        variable.update(mean=[3.2, 4.8][index], std=[.2, .3][index])
        if name == 'mixed':
            variable.update(mean=2., std=2.)
    document['material_evaluation']['frequency_hz'] = 2e8
    return json.loads(normalize_saved(json.dumps(document)))


def cases():
    return [dict(name=name, input=(document := correlated_study(name)),
                 execution=execute_saved(json.dumps(document)))
            for name in ['complete', 'mixed', 'positive-rank-one', 'negative-rank-one']]


if __name__ == '__main__':
    print(json.dumps(cases(), allow_nan=False))
