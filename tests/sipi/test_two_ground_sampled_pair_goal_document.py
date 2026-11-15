# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved finite-grid paired goals preserve exact factories and failure history."""
import itertools
import json
import numpy as np
import pytest

from sipi import CrossSection
from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument as Line
from sipi.two_ground_sampled_pair_goal_document import TwoGroundSampledForwardPairDesignDocument as Document
from sipi.two_ground_sampled_pair_goal import seek_two_ground_sampled_forward_pair_impedances as seek
from sipi.execution import execute_saved, normalize_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_execution_record import ARTIFACTS
from test_two_ground_pair_goal_document import document as single_document, _QUANTITIES
from test_two_ground_sampled_pair_goal import synthetic, targets, document as independent_line, F

SELECTED = [.00043331845625629, .00028959075290925696]
PHYSICAL_F = [2e9,3.5e9,5e9]


def document(physical=False, *, initial=None, max_evaluations=64):
    raw = single_document(physical).to_dict()
    frequencies = PHYSICAL_F if physical else F
    requested = np.array([[90.,44.5]]*3) if physical else targets(frequencies=frequencies)
    tolerance = .1 if physical else 1e-6
    return Document(raw['study'],frequencies=frequencies,conductors=raw['conductors'],
        reference=raw['reference'],ground_thickness=raw['ground_thickness_m'],
        targets={q:requested[:,i].tolist() for i,q in enumerate(_QUANTITIES)},
        tolerances={q:[tolerance]*3 for q in _QUANTITIES},initial=initial,
        max_evaluations=max_evaluations,**raw['panel'])


def independent_factory(width,gap,frequencies):
    raw = independent_line(width,gap,frequencies).to_dict()
    raw['cross_section']['layers'][0]['name'] = 'dielectric'
    cross = Line.from_dict(raw).cross_section
    raw['cross_section']['mesh'] = cross.section.mesh_settings(**cross.mesh_options)
    return Line.from_dict(raw)


def test_field_free_normalization_snapshot_and_project_restore(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preparation meshed'))
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('preparation solved'))
    doc = document(); text = doc.dumps()
    assert normalize_saved(text) == Document.loads(text).dumps() == text
    raw = doc.to_dict(); raw['frequency_hz'].reverse(); raw['targets_ohm'][_QUANTITIES[0]][0] = 1.
    assert doc.dumps() == text
    request = SavedExecutionRequest(text)
    project = SavedProject(request,project_id='grid-goal',design_id='a',title='Grid goal',label='Source')
    assert SavedProject.loads(project.dumps()).prepare('a').request_id == request.request_id


@pytest.mark.parametrize('where',['root','study','sampling','panel','targets','tolerances','positive','top','coating'])
@pytest.mark.parametrize('kind',['extra','missing'])
def test_strict_nested_fields(where,kind):
    raw = document().to_dict()
    target = {'root':raw,'study':raw['study'],'sampling':raw['study']['sampling'],'panel':raw['panel'],
        'targets':raw['targets_ohm'],'tolerances':raw['tolerances_ohm'],'positive':raw['conductors']['positive'],
        'top':raw['reference']['top'],'coating':raw['conductors']['positive']['coatings'][0]}[where]
    if kind == 'extra': target['unexpected'] = 1
    else: target.pop(next(iter(target)))
    with pytest.raises((ValueError,TypeError)): Document.from_dict(raw)


@pytest.mark.parametrize('kind',['schema','duplicate','nan','frequency-count','frequency-order','anchor',
    'target-shape','target-zero','target-bool','tolerance-shape','tolerance-zero','budget','bool-budget',
    'initial-size','initial-outside','one-variable','uniform','refinement','old-source'])
def test_invalid_saved_controls_precede_fields(monkeypatch,kind):
    raw = document().to_dict(); text = None
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('invalid goal solved'))
    if kind=='schema':raw['schema'] += 'unknown'
    if kind=='duplicate':text=json.dumps(raw).replace('"max_evaluations": 64','"max_evaluations": 64, "max_evaluations": 64')
    if kind=='nan':text=json.dumps(raw).replace('"max_evaluations": 64','"max_evaluations": NaN')
    if kind=='frequency-count':raw['frequency_hz'] = [1e9]
    if kind=='frequency-order':raw['frequency_hz'].reverse()
    if kind=='anchor':raw['study']['material_evaluation']['frequency_hz'] = 2e9
    if kind=='target-shape':raw['targets_ohm'][_QUANTITIES[0]] = [100.]
    if kind=='target-zero':raw['targets_ohm'][_QUANTITIES[0]][1] = 0.
    if kind=='target-bool':raw['targets_ohm'][_QUANTITIES[0]][1] = True
    if kind=='tolerance-shape':raw['tolerances_ohm'][_QUANTITIES[0]] = [[.1]]*3
    if kind=='tolerance-zero':raw['tolerances_ohm'][_QUANTITIES[1]][1] = 0.
    if kind=='budget':raw['max_evaluations'] = 3
    if kind=='bool-budget':raw['max_evaluations'] = True
    if kind=='initial-size':raw['initial'] = [.0003]
    if kind=='initial-outside':raw['initial'] = [1.,1.]
    if kind=='one-variable':raw['study']['sampling']['variables'].pop()
    if kind=='uniform':raw['study']['sampling'].update(kind='uniform',count=4,seed=9)
    if kind=='refinement':raw['panel']['panels_per_edge'] = 129
    if kind=='old-source':raw['study']['schema'] = 'sipi.impedance-study/1'
    with pytest.raises((ValueError,TypeError)): Document.loads(text or json.dumps(raw))


def test_source_factory_matches_independent_geometry_at_corners_and_initial(monkeypatch):
    import sipi.two_ground_sampled_pair_goal_document as module
    doc = document(True,initial=SELECTED,max_evaluations=4); sentinel = object()
    def inspect(make,bounds,frequencies,requested,**controls):
        for w,g in [controls['initial'],*itertools.product(*bounds)]:
            assert make(w,g).dumps() == independent_factory(w,g,PHYSICAL_F).dumps()
        np.testing.assert_array_equal(requested,[[90.,44.5]]*3)
        np.testing.assert_array_equal(controls['tolerances'],[[.1,.1]]*3)
        assert frequencies == PHYSICAL_F and controls['max_evaluations'] == 4
        return sentinel
    monkeypatch.setattr(module,'seek_two_ground_sampled_forward_pair_impedances',inspect)
    assert doc.solve() is sentinel


def test_full_grid_preflight_includes_nominal_initial_and_all_corners(monkeypatch):
    import sipi.two_ground_sampled_pair_goal_document as module
    previous = module._refinements; seen = []
    def capture(text):
        seen.append(Line.loads(text));return previous(text)
    monkeypatch.setattr(module,'_refinements',capture)
    doc = document(True,initial=SELECTED,max_evaluations=4)
    assert len(seen) == 6
    assert all(line.to_dict()['frequency_hz'] == PHYSICAL_F for line in seen)
    raw = doc.to_dict();bounds=[(v['lower'],v['upper']) for v in raw['study']['sampling']['variables']]
    expected=[(.00038,.00028),tuple(SELECTED),*itertools.product(*bounds)]
    for actual,(w,g) in zip(seen,expected): assert actual.dumps() == independent_factory(w,g,PHYSICAL_F).dumps()


def test_material_leaf_and_fixed_pitch_bindings_reach_every_frequency(monkeypatch):
    import sipi.two_ground_sampled_pair_goal_document as module
    from sipi.dielectric import DebyeDielectric,dielectric_to_dict
    raw = document().to_dict();source=raw['study'];source['schema']='sipi.impedance-study/4'
    source['fixed_pitch_m']=.0008;source['parameters']['gap']=.0008-source['parameters']['width']
    source['material_evaluation']['materials']={'dielectric':dielectric_to_dict(DebyeDielectric(3.,(.7,),(1e9,)))}
    source['material_variables']={'strength':dict(region='dielectric',path=['strengths',0])}
    source['sampling']['variables']=[dict(name='width',lower=.0003,upper=.0004),dict(name='strength',lower=.5,upper=.9)]
    doc=Document.from_dict(raw);sentinel=object()
    def inspect(make,bounds,frequencies,requested,**controls):
        for width,strength in itertools.product(*bounds):
            line=make(width,strength);data=line.to_dict();traces=line.cross_section.section.traces
            assert data['frequency_hz']==F
            assert traces[1].x-traces[0].x==pytest.approx(.0008,rel=1e-14)
            assert data['materials']['dielectric']['parameters']['strengths']==[strength]
        return sentinel
    monkeypatch.setattr(module,'seek_two_ground_sampled_forward_pair_impedances',inspect)
    assert doc.solve() is sentinel


def test_synthetic_saved_goal_receipt_and_record(monkeypatch):
    synthetic(monkeypatch);doc=document();result=doc.solve();request=SavedExecutionRequest(doc.dumps());receipt=request.run()
    assert receipt['execution']['status']=='complete' and receipt['execution']['result']==result.to_dict()
    np.testing.assert_allclose(result.parameters,[.000405,.00016],rtol=1e-6)
    record=SavedExecutionRecord(request,receipt,run_id='grid-goal:complete',artifacts=ARTIFACTS)
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt
    project=SavedProject(request,project_id='grid-goal',design_id='a',title='Goal',label='A').attach_record('a',record,select=True)
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedProject.loads(project.dumps()).current_record('a').dumps()==record.dumps()


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_saved_current_failure_preserves_every_attempt_and_original_cause(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt);doc=document(initial=[.000405,.00016],max_evaluations=4)
    request=SavedExecutionRequest(doc.dumps());receipt=request.run();out=receipt['execution']
    assert out['status']=='failed' and out['result'] is None
    error=out['error'];assert error['attempts']==len(calls)==attempt and len(error['history'])==attempt-1
    assert error['input']==json.loads(calls[-1])==error['cause_details']['input']
    assert error['cause_type']=='TwoGroundPanelLineError' and error['cause_details']['cause_type']=='ArithmeticError'
    assert error['frequencies_hz']==F
    record=SavedExecutionRecord(request,receipt,run_id='grid-goal:failed',artifacts=ARTIFACTS)
    assert record.to_dict()['schema']=='sipi.execution-record/1'
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt


def test_saved_interrupt_propagates(monkeypatch):
    calls=synthetic(monkeypatch,fail_at=2,interrupt=True)
    with pytest.raises(KeyboardInterrupt):execute_saved(document(initial=[.000405,.00016],max_evaluations=4).dumps())
    assert len(calls)==2


@pytest.mark.parametrize('mode',['budget','diagnostics','bytes'])
def test_caller_limits_precede_solver(monkeypatch,mode):
    monkeypatch.setattr(Document,'solve',lambda *a,**k:pytest.fail('rejected request solved'))
    kwargs={'max_evaluations':63} if mode=='budget' else {'diagnostics':['characteristic']} if mode=='diagnostics' else {'max_input_bytes':16}
    with pytest.raises(ValueError):execute_saved(document().dumps(),**kwargs)


def test_saved_physical_selected_input_matches_independent_direct_four_attempts(record_property):
    doc=document(True,initial=SELECTED,max_evaluations=4);request=SavedExecutionRequest(doc.dumps(),max_evaluations=4)
    receipt=request.run();record_property('two_ground_saved_grid_goal_receipt',json.dumps(receipt,sort_keys=True))
    assert receipt['execution']['status']=='complete'
    direct=seek(lambda w,g:independent_factory(w,g,PHYSICAL_F),[[.00035,.0005],[.0002,.0004]],PHYSICAL_F,
        [[90.,44.5]]*3,tolerances=[[.1,.1]]*3,initial=SELECTED,max_evaluations=4)
    record_property('two_ground_saved_grid_goal_direct',json.dumps(direct.to_dict(),sort_keys=True))
    assert len(direct.history)==4 and receipt['execution']['result']==direct.to_dict()
    record=SavedExecutionRecord(request,receipt,run_id='grid-goal:physical',artifacts=ARTIFACTS)
    project=SavedProject(request,project_id='physical-grid',design_id='a',title='Selected input',label='A').attach_record('a',record,select=True)
    assert SavedProject.loads(project.dumps()).current_record('a').receipt==receipt


def test_maximum_saved_grid_and_resource_cap_without_fields(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('grid admission meshed'))
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('grid admission solved'))
    raw=document().to_dict();raw['frequency_hz']=np.geomspace(F[0],F[-1],64).tolist()
    for key in ('targets_ohm','tolerances_ohm'):
        for q in _QUANTITIES:raw[key][q]=[raw[key][q][0]]*64
    text=Document.from_dict(raw).dumps();assert normalize_saved(text)==text
    assert len(json.loads(text)['frequency_hz'])==64
    raw['frequency_hz'].append(6e9)
    for key in ('targets_ohm','tolerances_ohm'):
        for q in _QUANTITIES:raw[key][q].append(raw[key][q][0])
    with pytest.raises(ValueError,match='2..64'):Document.from_dict(raw)


def test_later_frequency_material_refusal_precedes_any_field(monkeypatch):
    from sipi.dielectric import TabulatedDielectric,dielectric_to_dict
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('material admission meshed'))
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('material admission solved'))
    material=dielectric_to_dict(TabulatedDielectric((1e9,2e9),(4.,4.),(.003,.003)))
    old=single_document().to_dict();old['study']['material_evaluation']['materials']={'dielectric':material}
    assert type(single_document()).from_dict(old).to_dict()['study']==old['study']
    raw=document().to_dict();raw['study']['material_evaluation']['materials']={'dielectric':material}
    with pytest.raises(ValueError,match='outside the dielectric table'):Document.from_dict(raw)
