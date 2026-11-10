"""Delivered starting documents and their actual loopback static response."""
import http.client
import json

import pytest
from pathlib import Path

from sipi import CrossSection, LumpedNetworkDocument
from sipi.execution import normalize_saved
from material_goal_cases import material_goal
from paired_material_cases import pair_material_goal, material_study
from material_goal_form_cases import edited_goal
from material_sweep_form_cases import edited_study
from test_desktop import server


def test_catalog_documents_are_exact_validated_inputs_without_solving(monkeypatch):
    source = (Path(__file__).resolve().parents[1] / 'ui/saved-examples.js').read_text()
    # The shipped module contains a JSON data literal, with no runtime builder.
    rows = json.loads(source.split('export const SAVED_EXAMPLES = ', 1)[1].removesuffix(';\n'))
    expected = [LumpedNetworkDocument([0, 1e9], resistance=10, inductance=2e-9),
        material_goal('constant'), material_goal('debye'), pair_material_goal(),
        material_study('constant'), material_study('tensor')]
    assert [row['id'] for row in rows] == ['rlc', 'constant-target', 'debye-target',
                                         'pair-target', 'material-sweep', 'correlated-study']
    def forbidden(*args, **kwargs):
        raise AssertionError('loading or normalizing an example must not solve')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    for row, doc in zip(rows, expected):
        assert row['document'] == doc.to_dict()
        text = json.dumps(row['document'], ensure_ascii=False)
        assert len(text.encode()) < 200*1024
        assert json.loads(normalize_saved(text)) == row['document']
        assert row['label'] and row['description']


@pytest.mark.parametrize('module', ['saved-examples.js', 'material-results.js', 'material-goal-form.js'])
def test_ui_module_is_served_as_javascript_without_authentication(server, module):
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
    try:
        connection.request('GET', '/' + module)
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader('Content-Type').split(';')[0] == 'text/javascript'
        assert response.read() == (Path(__file__).resolve().parents[1] / 'ui' / module).read_bytes()
    finally:
        connection.close()


@pytest.mark.parametrize('kind', ['constant', 'debye'])
def test_edited_material_goal_validates_without_meshing(kind, monkeypatch):
    original = material_goal(kind).to_dict()
    def forbidden(*args, **kwargs):
        raise AssertionError('editing or normalizing must not solve')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    edited = edited_goal(kind).to_dict()
    assert json.loads(normalize_saved(json.dumps(edited))) == edited
    assert edited['target_ohm'] == 51 and edited['bounds'] == [2.5, 7.5]
    assert edited['material_evaluation']['frequency_hz'] == 2e8
    assert edited['max_evaluations'] == 48
    edited.update(target_ohm=original['target_ohm'], bounds=original['bounds'],
                  max_evaluations=original['max_evaluations'])
    edited['material_evaluation']['frequency_hz'] = original['material_evaluation']['frequency_hz']
    assert edited == original


@pytest.mark.parametrize('kind', ['constant', 'debye'])
def test_edited_material_sweep_checks_corners_without_meshing(kind, monkeypatch):
    original = material_study(kind).to_dict()
    def forbidden(*args, **kwargs):
        raise AssertionError('editing a sweep must not solve')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    edited = edited_study(kind)
    assert edited['sampling']['count'] == 5
    assert edited['sampling']['variables'][0] == dict(name='dk', lower=1., upper=5.)
    assert edited['material_evaluation']['frequency_hz'] == 2e8
    edited['sampling'] = original['sampling']
    edited['material_evaluation']['frequency_hz'] = original['material_evaluation']['frequency_hz']
    assert edited == original
    invalid = material_study('constant').to_dict()
    invalid['sampling']['variables'][0]['lower'] = -.5
    with pytest.raises(ValueError, match='relative permittivity'):
        normalize_saved(json.dumps(invalid))


def test_edited_pair_settings_validate_without_meshing(monkeypatch):
    original = pair_material_goal().to_dict()
    def forbidden(*args, **kwargs):
        raise AssertionError('editing paired targets must not solve')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    edited = json.loads(json.dumps(original))
    edited['targets_ohm']['z_diff'] = 101.
    edited['variables'][0]['bounds'] = edited['variables'][1]['bounds'] = [2.2, 5.8]
    edited['initial'] = [3.2, 3.5]
    edited['material_evaluation']['frequency_hz'] = 2e8
    assert json.loads(normalize_saved(json.dumps(edited))) == edited
    edited['initial'][1] = 6.
    with pytest.raises(ValueError, match='initial'):
        normalize_saved(json.dumps(edited))
    edited.update(initial=original['initial'], variables=original['variables'], targets_ohm=original['targets_ohm'])
    edited['material_evaluation']['frequency_hz'] = original['material_evaluation']['frequency_hz']
    assert edited == original
