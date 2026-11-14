# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
import numpy as np
import pytest

from sipi import CrossSection
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_pair_goal_document import PanelForwardPairDesignDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.shape_panel_pair_goal_document import ShapePanelForwardPairDesignDocument
from test_pair_line_goal_document import document as legacy_goal
from test_layered_panel_goal_document import document as coated_goal
from test_shape_panel_pair_goal_physical import factory


def document(coated=True,physical=False):
    nested=(coated_goal(physical=physical) if coated else
            PanelForwardPairDesignDocument(legacy_goal(physical=physical)))
    return ShapePanelForwardPairDesignDocument(nested)


@pytest.mark.parametrize('coated',[False,True])
def test_normalization_is_field_free_and_has_independent_snapshots(monkeypatch,coated):
    forbidden=lambda *a,**k:pytest.fail('normalization reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',forbidden)
    doc=document(coated);text=doc.dumps()
    assert ShapePanelForwardPairDesignDocument.loads(text).dumps()==text
    raw=doc.to_dict();raw['step_fraction']=.01;raw['design']['panel']['panels_per_edge']=64
    goals=doc.goal_input;goals['max_evaluations']=4
    assert doc.dumps()==text and doc.design.panel_options['panels_per_edge']==32
    with pytest.raises(ValueError):PanelForwardPairDesignDocument.loads(text)


@pytest.mark.parametrize('where',['root','design','panel','study','sampling','conductor','coating'])
@pytest.mark.parametrize('kind',['missing','extra'])
def test_all_nested_keys_are_strict(where,kind):
    data=document().to_dict();d=data['design']
    target={'root':data,'design':d,'panel':d['panel'],'study':d['study'],
            'sampling':d['study']['sampling'],'conductor':d['conductor'],
            'coating':d['conductor']['reference']['coatings'][0]}[where]
    if kind=='missing':target.pop(next(iter(target)))
    else:target['unexpected']=1
    with pytest.raises(ValueError):ShapePanelForwardPairDesignDocument.from_dict(data)


@pytest.mark.parametrize('value',[True,None,0.,1e-6,.02,np.inf])
def test_shape_step_admission(value):
    data=document().to_dict();data['step_fraction']=value
    with pytest.raises((ValueError,TypeError)):ShapePanelForwardPairDesignDocument.from_dict(data)


@pytest.mark.parametrize('kind',['schema','duplicate','nan','wrong-nested','budget','refinement'])
def test_invalid_saved_contracts(kind):
    data=document().to_dict();text=json.dumps(data)
    if kind=='schema':data['schema']='sipi.shape-panel-forward-pair-design/2'
    if kind=='duplicate':text=text.replace('"step_fraction": 0.001','"step_fraction": 0.001, "step_fraction": 0.001')
    if kind=='nan':text=text.replace('"step_fraction": 0.001','"step_fraction": NaN')
    if kind=='wrong-nested':data['design']=data['design']['study']
    if kind=='budget':data['design']['max_evaluations']=3
    if kind=='refinement':data['design']['panel']['panels_per_edge']=129
    if kind not in ('duplicate','nan'):text=json.dumps(data)
    with pytest.raises(ValueError):ShapePanelForwardPairDesignDocument.loads(text)


def test_offset_collision_at_unsolved_corner_is_rejected_before_fields(monkeypatch):
    raw=PanelForwardPairDesignDocument(legacy_goal(physical=True)).to_dict()
    raw['design']['study']['sampling']['variables'][1]['lower']=1e-8
    nested=PanelForwardPairDesignDocument.from_dict(raw)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('corner validation solved'))
    with pytest.raises(ValueError,match='touch or overlap'):
        ShapePanelForwardPairDesignDocument(nested)


@pytest.mark.parametrize('coated',[False,True])
def test_dispatch_matches_direct_physical_factory_at_bounds_and_initial(monkeypatch,coated):
    import sipi.shape_panel_pair_goal_document as implementation
    doc=document(coated,physical=True);selected=[];sentinel=object()
    def inspect(make,bounds,targets,**controls):
        assert bounds==[[.4e-3,.9e-3],[.2e-3,.6e-3]] and targets==[110.,40.]
        assert controls==dict(tolerances=[.25,.125],initial=[.7e-3,.35e-3],max_evaluations=64)
        for w in (.4e-3,.9e-3):
            for g in (.2e-3,.6e-3):
                assert make(w,g).dumps()==factory(w,g,coated=coated).dumps();selected.append((w,g))
        assert make(.7e-3,.35e-3).dumps()==factory(.7e-3,.35e-3,coated=coated).dumps()
        return sentinel
    monkeypatch.setattr(PanelForwardPairDesignDocument,'solve',lambda *a,**k:pytest.fail('implicit old-method solve'))
    monkeypatch.setattr(implementation,'seek_shape_panel_forward_pair_impedances',inspect)
    assert doc.solve() is sentinel and len(selected)==4


def test_constructor_rejects_implicit_dict_conversion():
    with pytest.raises(TypeError):ShapePanelForwardPairDesignDocument({})


def synthetic_transport(monkeypatch,**options):
    # Deliberately synthetic current payload: these tests exercise serialization,
    # not extraction accuracy. Actual direct goal fields have separate tests.
    from types import SimpleNamespace
    from test_shape_panel_pair_goal import synthetic
    calls=synthetic(monkeypatch,**options)
    previous=ShapePanelTransmissionLineDocument.analyze
    def analyze(self):
        result=previous(self)
        parts=np.array([np.eye(2),2*np.eye(2),3*np.eye(2)])
        result.current_factors=SimpleNamespace(ground_trace_names=(),C0=np.eye(2)*1e-11,
            parts=parts,current_integrals=np.array([[1.,0.],[0.,1.],[-1.,-1.]]),
            diagnostics={'transport_stub':1.},step_m=1e-8,
            step_parts=np.array([parts,parts]),boundary_step_parts=np.array([parts,parts]),samples=())
        result.panel_settings=self.current_options
        return result
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',analyze)
    return calls


@pytest.mark.parametrize('coated',[False,True])
def test_modal_root_common_execution_and_record_roundtrip(monkeypatch,coated):
    from sipi.execution import execute_saved,normalize_saved
    from sipi.execution_request import SavedExecutionRequest
    from sipi.execution_record import SavedExecutionRecord
    from test_execution_record import ARTIFACTS
    from sipi.shape_panel_pair_goal import seek_shape_panel_forward_pair_impedances
    from test_panel_pair_goal import quantities
    synthetic_transport(monkeypatch);doc=document(coated);goal=doc.solve()
    direct=seek_shape_panel_forward_pair_impedances(lambda w,g:factory(w,g,coated=coated),
        [[.15e-3,.6e-3],[.1e-3,.3e-3]],quantities(1.35,.8),tolerances=[1e-6]*2)
    assert goal.to_dict()==direct.to_dict()
    np.testing.assert_allclose(goal.parameters,[1.35*.3e-3,.8*.2e-3],rtol=1e-6)
    assert normalize_saved(doc.dumps())==doc.dumps()
    output=execute_saved(doc.dumps(),max_evaluations=64)
    assert output['status']=='complete' and output['error'] is None and output['result']==goal.to_dict()
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=64);receipt=request.run()
    saved=SavedExecutionRecord(request,receipt,run_id='shape-goal:synthetic',artifacts=ARTIFACTS)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    restored=SavedExecutionRecord.loads(saved.dumps())
    assert restored.receipt==receipt and restored.prepare().to_dict()==request.to_dict()


@pytest.mark.parametrize('mode',['budget','diagnostics','input-bytes'])
def test_caller_limits_precede_fields(monkeypatch,mode):
    from sipi.execution import execute_saved
    doc=document();forbidden=lambda *a,**k:pytest.fail('rejected request solved')
    monkeypatch.setattr(ShapePanelForwardPairDesignDocument,'solve',forbidden)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',forbidden)
    kwargs=({'max_evaluations':63} if mode=='budget' else
            {'diagnostics':['characteristic']} if mode=='diagnostics' else {'max_input_bytes':16})
    with pytest.raises(ValueError):execute_saved(doc.dumps(),**kwargs)


@pytest.mark.parametrize('coated',[False,True])
@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_failed_receipt_retains_original_shape_cause_and_attempts(monkeypatch,coated,attempt):
    from sipi.execution_request import SavedExecutionRequest
    from sipi.execution_record import SavedExecutionRecord
    from test_execution_record import ARTIFACTS
    from test_panel_pair_goal import STAGES
    calls=synthetic_transport(monkeypatch,fail_at=attempt)
    data=document(coated).to_dict();goal=data['design'] if coated else data['design']['design']
    goal['initial']=[1.35*.3e-3,.8*.2e-3];goal['max_evaluations']=4
    doc=ShapePanelForwardPairDesignDocument.from_dict(data)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=4);receipt=request.run();out=receipt['execution']
    assert out['status']=='failed' and out['result'] is None
    error=out['error'];assert error['attempts']==len(calls)==attempt and len(error['history'])==attempt-1
    assert error['stage']==(['search']+STAGES)[attempt-1]+'/extraction'
    assert error['cause_type']=='ShapePanelLineError' and error['input']==json.loads(calls[-1])
    details=error['cause_details']
    assert details['input']==error['input'] and details['stage']=='current'
    assert details['message']=='original current refusal' and details['partial_current']['samples']==[]
    saved=SavedExecutionRecord(request,receipt,run_id='shape-goal:failed',artifacts=ARTIFACTS)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    restored=SavedExecutionRecord.loads(saved.dumps())
    assert restored.receipt==receipt and restored.prepare().to_dict()==request.to_dict()


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_interrupt_does_not_turn_into_a_saved_failure(monkeypatch,attempt):
    from sipi.execution_request import SavedExecutionRequest
    synthetic_transport(monkeypatch,fail_at=attempt,interrupt=True)
    data=document().to_dict();data['design']['initial']=[1.35*.3e-3,.8*.2e-3];data['design']['max_evaluations']=4
    doc=ShapePanelForwardPairDesignDocument.from_dict(data)
    with pytest.raises(KeyboardInterrupt):SavedExecutionRequest(doc.dumps(),max_evaluations=4).run()
