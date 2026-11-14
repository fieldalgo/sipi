# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved explicit shape-current grids preserve admission, attempts and receipts."""
import itertools
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.sampled_panel_pair_goal_document import SampledPanelForwardPairDesignDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.shape_sampled_panel_pair_goal_document import ShapeSampledPanelForwardPairDesignDocument as Document
from sipi.execution import normalize_saved,execute_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from test_execution_record import ARTIFACTS
from test_sampled_panel_pair_goal_document import document as bulk_document
from test_layered_sampled_panel_goal_document import document as coated_document
from test_shape_sampled_panel_pair_study import synthetic
from test_sampled_panel_pair_goal import F,targets
from test_pair_line_goal_document import Q


def document(coated=True):
    return Document(coated_document() if coated else bulk_document())


@pytest.mark.parametrize('coated',[False,True])
def test_field_free_normalization_and_independent_snapshots(monkeypatch,coated):
    forbidden=lambda *a,**k:pytest.fail('normalization reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',forbidden)
    doc=document(coated);text=doc.dumps()
    assert normalize_saved(text)==text==Document.loads(text).dumps()
    raw=doc.to_dict();raw['design']['frequency_hz'][0]=1;raw['step_fraction']=.002
    assert doc.dumps()==text and doc.design.to_dict()['frequency_hz']==F.tolist()
    with pytest.raises(ValueError):SampledPanelForwardPairDesignDocument.loads(text)


@pytest.mark.parametrize('where',['root','design','study','sampling','panel','conductor','coating','targets_ohm','tolerances_ohm'])
@pytest.mark.parametrize('change',['extra','missing'])
def test_exact_keys_at_every_saved_level(where,change):
    raw=document().to_dict();d=raw['design']
    mapping=dict(root=raw,design=d,study=d['study'],sampling=d['study']['sampling'],
        panel=d['panel'],conductor=d['conductor'],coating=d['conductor']['reference']['coatings'][0],
        targets_ohm=d['targets_ohm'],tolerances_ohm=d['tolerances_ohm'])
    node=mapping[where]
    if change=='missing':node.pop(next(iter(node)))
    else:node['unexpected']=1
    with pytest.raises(ValueError):Document.from_dict(raw)


@pytest.mark.parametrize('value',[True,None,0.,1e-6,.02,np.inf])
def test_invalid_shape_step(value):
    raw=document().to_dict();raw['step_fraction']=value
    with pytest.raises((ValueError,TypeError)):Document.from_dict(raw)


@pytest.mark.parametrize('kind',['schema','duplicate','nan','wrong-nested','refinement','frequency','anchor','target','tolerance','budget'])
def test_invalid_saved_contracts_precede_fields(monkeypatch,kind):
    raw=document().to_dict();text=json.dumps(raw)
    if kind=='schema':raw['schema']='sipi.shape-sampled-panel-forward-pair-design/2'
    if kind=='duplicate':text=text.replace('"step_fraction": 0.001','"step_fraction": 0.001, "step_fraction": 0.001')
    if kind=='nan':text=text.replace('"step_fraction": 0.001','"step_fraction": NaN')
    if kind=='wrong-nested':raw['design']=raw['design']['study']
    if kind=='refinement':raw['design']['panel']['panels_per_edge']=129
    if kind=='frequency':raw['design']['frequency_hz'][1]=raw['design']['frequency_hz'][0]
    if kind=='anchor':raw['design']['study']['material_evaluation']['frequency_hz']=1
    if kind=='target':raw['design']['targets_ohm'][Q[0]]=1.
    if kind=='tolerance':raw['design']['tolerances_ohm'][Q[1]][-1]=True
    if kind=='budget':raw['design']['max_evaluations']=3
    if kind not in ('duplicate','nan'):text=json.dumps(raw)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('invalid input solved'))
    with pytest.raises(ValueError):Document.loads(text)


def test_unsolved_corner_offset_collision_precedes_fields(monkeypatch):
    raw=bulk_document().to_dict();raw['study']['sampling']['variables'][1]['lower']=1e-8
    nested=SampledPanelForwardPairDesignDocument.from_dict(raw)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('corner solved'))
    with pytest.raises(ValueError,match='touch or overlap'):Document(nested)


def test_no_implicit_dict_constructor():
    with pytest.raises(TypeError):Document({})


@pytest.mark.parametrize('coated',[False,True])
def test_dispatch_keeps_initial_all_corners_and_named_frequency_arrays(monkeypatch,coated):
    import sipi.shape_sampled_panel_pair_goal_document as module
    from test_sampled_panel_pair_goal import document as bulk_line
    from test_layered_panel_goal import factory as coated_line
    raw=document(coated).to_dict();raw['design']['initial']=[.4e-3,.2e-3];raw['step_fraction']=.002
    doc=Document.from_dict(raw);seen=[];sentinel=object()
    def inspect(factory,bounds,frequencies,requested,**options):
        assert bounds==[[.15e-3,.6e-3],[.1e-3,.3e-3]] and frequencies==F.tolist()
        np.testing.assert_array_equal(requested,targets())
        np.testing.assert_array_equal(options['tolerances'],np.full((3,2),1e-6))
        assert options['initial']==[.4e-3,.2e-3] and options['max_evaluations']==64
        for w,g in [options['initial'],*itertools.product(*bounds)]:
            line=(coated_line(w,g) if coated else bulk_line(w,g)).to_dict()
            line['line']['frequency_hz']=F.tolist()
            expected=ShapePanelTransmissionLineDocument(PanelTransmissionLineDocument.from_dict(line),step_fraction=.002)
            assert factory(w,g).dumps()==expected.dumps();seen.append((w,g))
        return sentinel
    monkeypatch.setattr(SampledPanelForwardPairDesignDocument,'solve',lambda *a,**k:pytest.fail('old-method solve'))
    monkeypatch.setattr(module,'seek_shape_sampled_panel_forward_pair_impedances',inspect)
    assert doc.solve() is sentinel and len(seen)==5


@pytest.mark.parametrize('coated',[False,True])
def test_independent_modal_search_common_execution_and_saved_record(monkeypatch,coated):
    synthetic(monkeypatch);doc=document(coated);goal=doc.solve()
    np.testing.assert_allclose(goal.parameters,[1.35*.3e-3,.8*.2e-3],rtol=1e-6)
    for row in goal.history:
        np.testing.assert_allclose(row.impedances,targets(row.parameters[0]/.3e-3,row.parameters[1]/.2e-3),rtol=1e-12)
    output=execute_saved(doc.dumps(),max_evaluations=64)
    assert output['status']=='complete' and output['result']==goal.to_dict() and output['error'] is None
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=64);receipt=request.run()
    saved=SavedExecutionRecord(request,receipt,run_id='shape-grid-goal:modal',artifacts=ARTIFACTS)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    restored=SavedExecutionRecord.loads(saved.dumps())
    assert restored.receipt==receipt and restored.prepare().to_dict()==request.to_dict()
    corrupt=json.loads(saved.dumps());corrupt['receipt']['execution']['result']['parameters'][0]*=2
    with pytest.raises(ValueError):SavedExecutionRecord.from_dict(corrupt)


@pytest.mark.parametrize('options',[dict(max_evaluations=63),dict(diagnostics=['characteristic']),dict(max_input_bytes=16)])
def test_caller_limits_before_fields(monkeypatch,options):
    doc=document();forbidden=lambda *a,**k:pytest.fail('rejected input solved')
    monkeypatch.setattr(Document,'solve',forbidden)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',forbidden)
    with pytest.raises(ValueError):execute_saved(doc.dumps(),**options)


@pytest.mark.parametrize('coated',[False,True])
@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_failed_batch_retains_full_grid_and_original_partial_current(monkeypatch,coated,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt)
    raw=document(coated).to_dict();raw['design'].update(initial=[1.35*.3e-3,.8*.2e-3],max_evaluations=4)
    doc=Document.from_dict(raw);request=SavedExecutionRequest(doc.dumps(),max_evaluations=4);receipt=request.run()
    out=receipt['execution'];error=out['error']
    assert out['status']=='failed' and out['result'] is None
    assert error['frequencies_hz']==F.tolist() and error['attempts']==len(calls)==attempt and len(error['history'])==attempt-1
    assert error['stage']==['search','volume-refinement','panel-refinement','joint-refinement'][attempt-1]+'/extraction'
    assert error['cause_type']=='ShapePanelLineError' and error['input']==json.loads(calls[-1])
    detail=error['cause_details']
    assert detail['input']==error['input'] and detail['stage']=='current' and detail['partial_current']['samples']==[]
    assert detail['message']=='original failed current batch'
    saved=SavedExecutionRecord(request,receipt,run_id='shape-grid-goal:failure',artifacts=ARTIFACTS)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    restored=SavedExecutionRecord.loads(saved.dumps());assert restored.receipt==receipt


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_interrupts_propagate(monkeypatch,attempt):
    synthetic(monkeypatch,fail_at=attempt,interrupt=True);raw=document().to_dict()
    raw['design'].update(initial=[1.35*.3e-3,.8*.2e-3],max_evaluations=4)
    with pytest.raises(KeyboardInterrupt):SavedExecutionRequest(Document.from_dict(raw).dumps(),max_evaluations=4).run()


def test_maximum_grid_is_one_whole_attempt_with_no_frequency_budget_inflation(monkeypatch):
    import sipi.shape_sampled_panel_pair_goal_document as module
    raw=document().to_dict();grid=np.geomspace(F[0],F[-1],64).tolist()
    d=raw['design'];d['frequency_hz']=grid
    d['targets_ohm']={q:[100.+i]*64 for i,q in enumerate(Q)}
    d['tolerances_ohm']={q:[.01]*64 for q in Q};d['max_evaluations']=4
    def inspect(factory,bounds,frequencies,values,**options):
        assert frequencies==grid and values.shape==(64,2) and options['tolerances'].shape==(64,2)
        assert options['max_evaluations']==4
        assert factory(.4e-3,.2e-3).line.line.to_dict()['frequency_hz']==grid
        return 'inspected'
    monkeypatch.setattr(module,'seek_shape_sampled_panel_forward_pair_impedances',inspect)
    assert Document.from_dict(raw).solve()=='inspected'
    d['frequency_hz'].append(4e9)
    for key in ('targets_ohm','tolerances_ohm'):
        for q in Q:d[key][q].append(1.)
    with pytest.raises(ValueError):Document.from_dict(raw)


def test_fixed_pitch_and_material_leaf_keep_coatings_and_full_grid(monkeypatch):
    import sipi.shape_sampled_panel_pair_goal_document as module
    from sipi.dielectric import DebyeDielectric,dielectric_to_dict
    raw=document().to_dict();d=raw['design'];s=d['study']
    s['schema']='sipi.impedance-study/4';s['fixed_pitch_m']=.95e-3
    s['material_evaluation']['materials']['substrate']=dielectric_to_dict(DebyeDielectric(3.,(.7,),(1e9,)))
    s['material_variables']={'strength':dict(region='substrate',path=['strengths',0])}
    s['sampling']['variables']=[dict(name='left_width',lower=.4e-3,upper=.8e-3),dict(name='strength',lower=.5,upper=.9)]
    d['initial']=[.65e-3,.7]
    def inspect(factory,bounds,frequencies,values,**options):
        assert bounds==[[.4e-3,.8e-3],[.5,.9]] and frequencies==F.tolist()
        for w,strength in ((.4e-3,.5),(.65e-3,.7),(.8e-3,.9)):
            result=factory(w,strength).to_dict();line=result['line']['line'];traces=line['cross_section']['traces']
            assert result['step_fraction']==.001 and line['frequency_hz']==F.tolist()
            assert line['conductor']==d['conductor'] and line['materials']['substrate']['parameters']['strengths']==[strength]
            assert abs(traces[1]['x']-traces[0]['x']-.95e-3)<1e-15
        return 'inspected'
    monkeypatch.setattr(module,'seek_shape_sampled_panel_forward_pair_impedances',inspect)
    assert Document.from_dict(raw).solve()=='inspected'
