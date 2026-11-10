"""Delivered starting documents and their actual loopback static response."""
import http.client
import json

import pytest
from pathlib import Path

from sipi import CrossSection, LumpedNetworkDocument
from sipi.execution import normalize_saved
from material_goal_cases import material_goal
from paired_material_cases import pair_material_goal, material_study
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


@pytest.mark.parametrize('module', ['saved-examples.js', 'material-results.js'])
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
