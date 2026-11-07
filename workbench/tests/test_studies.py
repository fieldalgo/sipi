"""Physical parameter studies, deterministic sampling and failure accounting."""
from copy import deepcopy
from pathlib import Path
import sys

import numpy as np
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from engine import document, execute, study_documents
import sipi

REQUEST = dict(action='study', template='stripline',
    parameters=dict(width=.5e-3, plane_spacing=1e-3, eps_r=4, thickness=0),
    mesh=dict(edge_size=5e-6, far_size=.5e-3, grade=.2),
    study=dict(mode='sweep', variables=[dict(parameter='eps_r', lower=3.6, upper=4.4)], points=3, seed=42))


def test_uniform_dielectric_sweep_follows_exact_tem_scaling():
    result = execute(REQUEST)['study']
    assert result['status'] == 'complete'
    assert result['failed'] == 0
    rows = result['rows']
    assert len(rows) == 3
    assert rows[0]['impedance'] > rows[1]['impedance'] > rows[2]['impedance']
    for row in rows:
        eps = row['parameters']['eps_r']
        assert row['impedance']/rows[1]['impedance'] == pytest.approx(np.sqrt(4/eps), rel=1e-10)
        assert np.asarray(row['line']['C'])/rows[1]['line']['C'] == pytest.approx(eps/4, rel=1e-10)
        assert row['document']['mesh'] == result['nominal_document']['mesh']
        assert row['line']['C'] == sipi.CrossSectionDocument.from_dict(row['document']).analyze().C.tolist()
    assert result['summary']['minimum'] == rows[2]['impedance']
    assert result['summary']['maximum'] == rows[0]['impedance']


def test_width_sweep_preserves_direct_solver_values_and_capacitance_direction():
    request = deepcopy(REQUEST)
    request['study']['variables'] = [dict(parameter='width', lower=.45e-3, upper=.55e-3)]
    rows = execute(request)['study']['rows']
    c = [row['line']['C'][0][0] for row in rows]
    assert c[0] < c[1] < c[2]
    for row in rows:
        direct = sipi.stripline(**{**request['parameters'], **row['parameters']}).analyze(**request['mesh'])
        assert row['impedance'] == direct.z0


def test_corner_combinations_and_seeded_uniform_inputs_are_exact():
    request = deepcopy(REQUEST)
    request['study'].update(mode='corners', variables=[dict(parameter='width', lower=.4e-3, upper=.6e-3), dict(parameter='eps_r', lower=3, upper=5)])
    settings, rows = study_documents(request, document(request))
    assert settings['points'] == 4
    assert [tuple(row[0].values()) for row in rows] == [(.4e-3,3),(.4e-3,5),(.6e-3,3),(.6e-3,5)]
    request['study']['mode'] = 'monte_carlo'
    a, rows = study_documents(request, document(request))
    b, repeated = study_documents(request, document(request))
    assert a == b
    assert [r[0] for r in rows] == [r[0] for r in repeated]
    # Published NumPy PCG64/default_rng seed42 sequence, before affine scaling.
    first = rows[0][0]
    assert (first['width']-.4e-3)/.2e-3 == pytest.approx(.7739560485559633, abs=1e-15)
    assert (first['eps_r']-3)/2 == pytest.approx(.4388784397520523, abs=1e-15)
    assert all(.4e-3 <= r[0]['width'] <= .6e-3 and 3 <= r[0]['eps_r'] <= 5 for r in rows)
    assert a['distribution'] == 'independent uniform'


@pytest.mark.parametrize('change', [
    dict(points=33), dict(points=True), dict(seed=-1), dict(seed=True), dict(mode='unknown'),
    dict(variables=[dict(parameter='width', lower=1, upper=0)]),
    dict(variables=[dict(parameter='eps_r', lower=.9, upper=4)]),
    dict(variables=[dict(parameter='width', lower=False, upper=.001)]),
    dict(variables=[dict(parameter='gap', lower=.0001, upper=.0002)]),
    dict(mode='corners', variables=[dict(parameter='width', lower=.0004, upper=.0006)]*2),
    dict(variables=[dict(parameter='width', lower=float('nan'), upper=.001)]),
])
def test_invalid_plan_is_rejected_before_any_solve(change, monkeypatch):
    request = deepcopy(REQUEST); request['study'].update(change)
    def forbidden(self):
        pytest.fail('Invalid study reached a solve')
    monkeypatch.setattr(sipi.CrossSectionDocument, 'analyze', forbidden)
    with pytest.raises(ValueError):
        execute(request)


def test_failed_sample_remains_in_report_and_withholds_statistics(monkeypatch):
    original = sipi.CrossSectionDocument.analyze
    count = 0
    def fail_second(self):
        nonlocal count
        count += 1
        if count == 2:
            raise ValueError('Deliberate solver failure')
        return original(self)
    monkeypatch.setattr(sipi.CrossSectionDocument, 'analyze', fail_second)
    study = execute(REQUEST)['study']
    assert study['status'] == 'incomplete'
    assert study['failed'] == 1
    assert study['summary'] is None
    assert len(study['rows']) == 3
    assert study['rows'][1]['status'] == 'error'
    assert study['rows'][1]['error'] == 'Deliberate solver failure'
    assert 'impedance' not in study['rows'][1]
    assert study['rows'][2]['status'] == 'complete'
