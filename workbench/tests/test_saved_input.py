"""Raw saved input routing and real loopback execution preserve engine semantics."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from engine import execute
from test_desktop import server, call, finish
from sipi import (LumpedNetworkDocument, EllipticalAperture, RoundConductor,
                  ApertureSectionDocument, ApertureStudyDocument, ApertureDesignDocument)
from sipi.execution import execute_saved, normalize_saved


def text():
    return LumpedNetworkDocument([0, 1e9], resistance=10, inductance=2e-9).dumps()


def aperture():
    return ApertureSectionDocument(EllipticalAperture(.8e-3, .8e-3,
        [RoundConductor('s', .28e-3)], eps_r=3.96), mesh=dict(size=.1e-3, angular_divisions=16))


def test_saved_actions_reuse_engine_and_strict_raw_text():
    assert execute(dict(action='saved-normalize', text=text()))['document_text'] == normalize_saved(text())
    assert execute(dict(action='saved-analyze', text=text()))['execution'] == execute_saved(text())
    for bad in ('{"schema":1,"schema":2}', '{"x":NaN}', '{"x":1e999}', '[]'):
        with pytest.raises(ValueError): execute(dict(action='saved-normalize', text=bad))
    for request in ({'action':'saved-analyze'}, {'action':'saved-analyze','text':text(),'path':'x'},
                    {'action':'saved-normalize','text':text(),'diagnostics':[]}):
        with pytest.raises(ValueError): execute(request)
    with pytest.raises(ValueError, match='max_input_bytes'):
        execute(dict(action='saved-normalize', text=' '*(200*1024)+text()))


def test_saved_pages_and_spawned_result_roundtrip(server):
    for path in ('/saved.html', '/saved.js', '/saved.css', '/saved-examples.js'):
        assert call(server, 'GET', path, authenticated=False)[0] == 200
    assert call(server, 'POST', '/api/job', dict(action='saved-analyze', text=text()))[0] == 202
    got = finish(server)
    assert got['status'] == 'complete'
    assert got['result']['execution'] == execute_saved(text())


def test_goal_failure_is_a_retained_report_not_transport_success_claim(server):
    doc = ApertureDesignDocument(aperture(), variable='conductor_0_diameter',
        bounds=[.2e-3, .35e-3], target=200e-12, tolerance=1e-14)
    assert call(server, 'POST', '/api/job', dict(action='saved-analyze', text=doc.dumps()))[0] == 202
    transport = finish(server)
    assert transport['status'] == 'complete'  # Delivery succeeded; analysis did not.
    report = transport['result']['execution']
    assert report['status'] == 'failed' and report['result'] is None
    assert 'refined mesh misses' in report['error']['message']
    assert report['error']['history'][-1]['stage'] == 'refinement'


def test_failed_study_rows_reach_the_client_unchanged():
    doc = ApertureStudyDocument(aperture(), sampling=dict(kind='normal', count=3, seed=771,
        variables=[dict(name='width', mean=.8e-3, std=1e-3)], correlation=[[1.]]))
    report = execute(dict(action='saved-analyze', text=doc.dumps()))['execution']
    assert report == execute_saved(doc.dumps())
    assert report['status'] == 'incomplete' and report['result']['summary'] is None
    assert len(report['result']['rows']) == 3 and report['result']['failed'] > 0


def test_saved_3d_capacitance_runs_in_spawned_process(server):
    from galerkin.mesh3d import box_mesh
    from sipi.capacitance3d_document import Capacitance3DDocument
    mesh = box_mesh(.004, .003, .002, 2, 2, 2)
    doc = Capacitance3DDocument(mesh, eps_r=3.8,
        conductors={'top': mesh.boundary['z1']}, ground=mesh.boundary['z0'])
    normalized = execute(dict(action='saved-normalize', text=doc.dumps()))
    assert normalized['document_text'] == doc.dumps()
    assert call(server, 'POST', '/api/job', dict(action='saved-analyze', text=doc.dumps()))[0] == 202
    output = finish(server)
    assert output['status'] == 'complete'
    assert output['result']['execution'] == execute_saved(doc.dumps())
    bad = doc.to_dict(); bad['ground'] = bad['conductors'][0]['nodes']
    with pytest.raises(ValueError, match='disjoint'):
        execute(dict(action='saved-normalize', text=json.dumps(bad)))


@pytest.mark.parametrize('kind', ['constant', 'debye'])
def test_material_goal_preserves_selected_model_and_refinement_through_host(server, kind):
    from material_goal_cases import material_goal
    doc = material_goal(kind)
    assert execute(dict(action='saved-normalize', text=doc.dumps()))['document_text'] == doc.dumps()
    assert call(server, 'POST', '/api/job', dict(action='saved-analyze', text=doc.dumps()))[0] == 202
    response = finish(server)
    assert response['status'] == 'complete'
    output = response['result']['execution']
    assert output == execute_saved(doc.dumps())
    assert output['status'] == 'complete' and output['error'] is None
    result = output['result']
    assert abs(result['residual']) <= 1 and abs(result['refined_residual']) <= 1
    assert result['history'][-1]['stage'] == 'refinement'
    model = result['material_evaluation']['materials']['dielectric']['parameters']
    chosen = model['eps_r'] if kind == 'constant' else model['strengths'][0]
    assert chosen == result['parameter'] and chosen != 4
    original = doc.to_dict()['material_evaluation']['materials']['dielectric']['parameters']
    assert (original['eps_r'] if kind == 'constant' else original['strengths'][0]) == 4


@pytest.mark.parametrize('kind', ['pair-goal', 'constant', 'debye', 'tensor', 'mixed-normal'])
def test_pair_and_sampled_material_saved_execution_through_host(server, kind):
    from paired_material_cases import pair_material_goal, material_study
    doc = pair_material_goal() if kind == 'pair-goal' else material_study(kind)
    assert execute(dict(action='saved-normalize', text=doc.dumps()))['document_text'] == doc.dumps()
    assert call(server, 'POST', '/api/job', dict(action='saved-analyze', text=doc.dumps()))[0] == 202
    transport = finish(server)
    assert transport['status'] == 'complete'
    actual = transport['result']['execution']
    assert actual == execute_saved(doc.dumps())
    if kind == 'mixed-normal':
        assert actual['status'] == 'incomplete'
        assert actual['result']['failed'] == 2 and actual['result']['summary'] is None
    else:
        assert actual['status'] == 'complete'
    if kind == 'pair-goal':
        result = actual['result']
        assert result['evaluations'] == len(result['history']) <= 64
        assert result['history'][-1]['stage'] == 'refinement'
        for i, tolerance in enumerate([1., .5]):
            assert abs(result['residuals_ohm'][i]) <= tolerance
            assert abs(result['refined_residuals_ohm'][i]) <= tolerance
            model = result['material_evaluation']['materials']['dielectric']['parameters']
            assert model[['axis1', 'axis2'][i]]['parameters']['eps_r'] == result['parameters'][i]
