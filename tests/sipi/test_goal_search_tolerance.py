# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""A tighter search residual leaves the final physical acceptance gate intact."""
import json
import numpy as np
import pytest
import sipi
import sipi.design as design
from sipi.dielectric import ConstantDielectric
from sipi.templates import stripline,coupled_stripline

MESH=dict(edge_size=.01,far_size=1.,grade=.2)

def instrument(monkeypatch,quantity='z0',mode='none',refined_offset=.6):
    """Controlled reciprocal matrices isolate search policy, not field accuracy."""
    calls=[];models=[];count=1 if quantity=='z0' else 2
    def factory(width):
        return (stripline(width=width,plane_spacing=10,eps_r=4) if count==1 else
                coupled_stripline(width=width,gap=1,plane_spacing=10,eps_r=4))
    def analyze(section,**mesh):
        width=section.traces[0].width;calls.append((width,dict(mesh)))
        offset=refined_offset if mesh['grade']==MESH['grade']/2 else .45
        value=100+10*(width-1.5)+offset;factor=1 if count==1 else 2
        return sipi.LineParameters(tuple('s'+str(i) for i in range(count)),
            C=np.eye(count),C0=np.eye(count)*2,L=np.eye(count)*(value/factor)**2,C_loss=np.eye(count)*.01)
    def material(doc,value,selected_quantity,*,mesh_reuse=None):
        assert selected_quantity==quantity
        return analyze(doc.section,**doc.mesh_options)
    def material_factory(width):
        models.append(width);return {'dielectric':ConstantDielectric(4+width)}
    monkeypatch.setattr(sipi.CrossSection,'analyze',analyze)
    monkeypatch.setattr(design,'_analyze_material',material)
    options={} if mode=='none' else dict(frequency=1e8)
    if mode=='fixed':options['materials']={'dielectric':ConstantDielectric(4)}
    if mode=='factory':options['material_factory']=material_factory
    return factory,options,calls,models

@pytest.mark.parametrize('quantity',['z0','z_diff','z_diff_forward'])
@pytest.mark.parametrize('mode',['none','fixed','factory'])
@pytest.mark.parametrize('return_line',[False,True])
def test_tighter_search_accepts_final_drift_within_original_tolerance(quantity,mode,return_line,monkeypatch):
    factory,options,calls,models=instrument(monkeypatch,quantity,mode)
    with pytest.raises(sipi.GoalSeekError,match='refined mesh misses'):
        sipi.seek_impedance(factory,[1,2],100,quantity=quantity,tolerance=.5,mesh=MESH,**options)
    calls.clear();models.clear()
    output=sipi.seek_impedance(factory,[1,2],100,quantity=quantity,tolerance=.5,
        search_tolerance=.1,mesh=MESH,max_evaluations=12,return_line=return_line,**options)
    result,line=output if return_line else (output,None)
    assert abs(result.residual)<=.1 and .1<abs(result.refined_residual)<=.5
    assert result.parameter==1.453125 and result.history[-1].stage=='refinement'
    assert len(result.history)==len(calls)<=12 and all(row.stage=='search' for row in result.history[:-1])
    assert models==([w for w,_ in calls[:-1]] if mode=='factory' else [])
    if mode=='factory':assert json.loads(result.material_evaluation_json)['materials']['dielectric']['parameters']['eps_r']==4+result.parameter
    if line is not None:
        value=line.even_odd()['z_diff'] if quantity=='z_diff' else getattr(line,quantity)
        assert value==result.impedance
        assert all(not getattr(line,k).flags.writeable for k in ['C','C0','L','C_loss'])
    assert calls[-1][1]['edge_size']==MESH['edge_size']/2
    assert calls[-1][1]['far_size']==MESH['far_size']/2 and calls[-1][1]['grade']==MESH['grade']/2

@pytest.mark.parametrize('target',[95.45,105.45,100.45])
def test_omitted_none_and_equal_threshold_have_identical_default_results(target,monkeypatch):
    factory,options,calls,_=instrument(monkeypatch)
    results=[]
    for keyword in [{},{'search_tolerance':None},{'search_tolerance':.5}]:
        calls.clear();r=sipi.seek_impedance(factory,[1,2],target,tolerance=.5,mesh=MESH,**keyword)
        results.append((r.parameter,r.impedance,r.refined_impedance,r.document.dumps(),r.history,list(calls)))
    assert results[0]==results[1]==results[2]

@pytest.mark.parametrize('value',[0,-1,True,np.bool_(True),float('nan'),float('inf'),'0.1',[],.50000001])
def test_invalid_search_threshold_rejected_before_factory(value):
    def forbidden(width):pytest.fail('Invalid threshold reached factory')
    with pytest.raises(ValueError,match='search_tolerance'):
        sipi.seek_impedance(forbidden,[1,2],100,tolerance=.5,search_tolerance=value)

def test_stricter_endpoint_requires_a_real_bracket(monkeypatch):
    factory,_,calls,_=instrument(monkeypatch)
    result=sipi.seek_impedance(factory,[1,1.005],95.2,tolerance=.5,mesh=MESH)
    assert result.parameter==1
    calls.clear()
    with pytest.raises(sipi.GoalSeekError,match='not bracketed') as caught:
        sipi.seek_impedance(factory,[1,1.005],95.2,tolerance=.5,search_tolerance=.1,mesh=MESH)
    assert len(caught.value.history)==len(calls)==2

def test_tighter_search_reserves_refinement_without_increasing_budget(monkeypatch):
    factory,_,calls,_=instrument(monkeypatch)
    with pytest.raises(sipi.GoalSeekError,match='evaluation limit') as caught:
        sipi.seek_impedance(factory,[1,2],100,tolerance=.5,search_tolerance=.1,mesh=MESH,max_evaluations=4)
    assert len(caught.value.history)==len(calls)==3
    assert all(row.stage=='search' for row in caught.value.history)

def test_final_original_tolerance_still_rejects_large_refinement_drift(monkeypatch):
    factory,_,calls,_=instrument(monkeypatch,refined_offset=1.05)
    with pytest.raises(sipi.GoalSeekError,match='refined mesh misses') as caught:
        sipi.seek_impedance(factory,[1,2],100,tolerance=.5,search_tolerance=.1,mesh=MESH)
    assert caught.value.history[-1].stage=='refinement'
    assert abs(caught.value.history[-1].impedance-100)>.5 and len(calls)==len(caught.value.history)

@pytest.mark.parametrize('stage',['search','refinement'])
def test_mesh_failure_retains_history_and_original_cause_with_tighter_threshold(stage,monkeypatch):
    from meshine import MeshSizeLimitError
    factory,_,calls,_=instrument(monkeypatch)
    original=sipi.CrossSection.analyze;cause=MeshSizeLimitError('injected point cap')
    def limited(section,**options):
        refined=options['grade']==MESH['grade']/2
        if (stage=='refinement' and refined) or (stage=='search' and len(calls)==2):raise cause
        return original(section,**options)
    monkeypatch.setattr(sipi.CrossSection,'analyze',limited)
    with pytest.raises(sipi.GoalMeshSizeLimitError) as caught:
        sipi.seek_impedance(factory,[1,2],100,tolerance=.5,search_tolerance=.1,mesh=MESH,return_line=True)
    error=caught.value
    assert error.__cause__ is cause and error.stage==stage
    assert error.attempts==len(error.history)+1 and len(error.history)==len(calls)
    assert all(row.stage=='search' for row in error.history)
    assert sipi.CrossSectionDocument.loads(error.input_json).section.traces[0].width==error.parameter


def test_saved_schemas_keep_default_contract_and_reject_direct_only_option():
    from sipi.design_document import ImpedanceDesignDocument
    from sipi.execution_request import SavedExecutionRequest
    plan=ImpedanceDesignDocument('stripline',dict(width=.0003,plane_spacing=.001,eps_r=4),variable='width',bounds=[.0002,.0006],target=50)
    text=plan.dumps();data=json.loads(text);assert 'search_tolerance' not in data
    assert ImpedanceDesignDocument.loads(text).dumps()==text
    request=SavedExecutionRequest(text)
    assert json.loads(request.input_json)==data and 'search_tolerance' not in request.controls
    invalid=json.dumps({**data,'search_tolerance':.05})
    for loader in [ImpedanceDesignDocument.loads,SavedExecutionRequest]:
        with pytest.raises(ValueError):loader(invalid)
