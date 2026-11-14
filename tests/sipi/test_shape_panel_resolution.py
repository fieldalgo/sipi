# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import itertools
import json
from types import SimpleNamespace
import numpy as np
import pytest
from scipy.linalg import expm

from sipi import CrossSection
from sipi.constants import epsilon_0, mu_0
from sipi.line_resolution import ResolutionTolerance
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument, ShapePanelLineError
from sipi.panel_shape_conductor import PanelShapeCurrentError
from sipi.shape_panel_resolution import assess_shape_panel_line_resolution
from test_shape_panel_line import document
from test_layered_metal import transfer

FINE=dict(panels_per_edge=32,ground_modes=1024,interpolation_degree=16)
TOLERANCES={'C0':ResolutionTolerance(.1,0.)}  # Control example, not accuracy qualification.


def inputs(coated=False):
    doc=document(coated);raw=doc.to_dict();raw['line']['panel']=dict(FINE,ground_modes=2048)
    cross=raw['line']['line']['cross_section'];cross['box']['width']*=2;cross['layers'][-1]['thickness']*=2
    for key in ('edge_size','far_size','grade'):cross['mesh'][key]*=.5
    return doc,[ShapePanelTransmissionLineDocument.from_dict(raw)]


def assess(doc,outers,**kwargs):
    return assess_shape_panel_line_resolution(doc,refined_panel_options=FINE,outer_documents=outers,
        tolerances=kwargs.pop('tolerances',TOLERANCES),**kwargs)


@pytest.fixture(scope='module',params=[False,True],ids=['legacy','coated'])
def observed(request):
    doc,outers=inputs(request.param)
    return doc,outers,assess(doc,outers)


def test_actual_axes_preserve_inputs_and_independent_physics(observed,record_property):
    doc,outers,result=observed;assert result.completed and result.accepted and result.failure is None
    assert [r.stage for r in result.evaluations]==['base','volume','panel','joint','outer:0']
    assert [(r.reference_index,r.evaluation_index) for r in result.comparisons]==[(0,1),(0,2),(1,3),(2,3),(3,4)]
    assert result.evaluations[0].input_json==doc.dumps() and result.evaluations[-1].input_json==outers[0].dumps()
    coated=doc.line.to_dict()['schema'].endswith('/2');independent=[]
    for row in result.evaluations:
        r=row.result;factors=r.current_factors;f=r.frequency
        assert json.loads(row.input_json)['step_fraction']==doc.to_dict()['step_fraction']
        np.testing.assert_allclose(r.C,4.2*np.broadcast_to(factors.C0,r.C.shape),atol=0,rtol=1e-12)
        np.testing.assert_allclose(r.G,2*np.pi*f[:,None,None]*.02*r.C,atol=0,rtol=1e-12)
        np.testing.assert_allclose(r.dielectric.L@factors.C0,epsilon_0*mu_0*np.eye(2),atol=1e-28,rtol=1e-10)
        expected=np.zeros_like(r.R,dtype=complex)
        for b,sigma in enumerate((58e6,35e6,45e6)):
            z=np.array([transfer(x) for x in f]) if coated else np.sqrt(2j*np.pi*f*mu_0/sigma)
            expected+=z[:,None,None]*factors.parts[b]
        np.testing.assert_allclose(r.R+2j*np.pi*f[:,None,None]*r.conductor.L_internal,expected,rtol=1e-10,atol=0)
        errors=[]
        for i,frequency in enumerate(f):
            z=r.R[i]+2j*np.pi*frequency*r.L[i];y=r.G[i]+2j*np.pi*frequency*r.C[i]
            t=expm(np.block([[np.zeros((2,2)),z],[y,np.zeros((2,2))]])*.02)
            a,b,c,d=t[:2,:2],t[:2,2:],t[2:,:2],t[2:,2:];eye=np.eye(2)
            s=np.linalg.solve(np.block([[eye,-a-b/50],[-eye,-50*c-d]]),np.block([[-eye,a-b/50],[-eye,50*c-d]]))
            errors.append(float(np.max(abs(s-r.network.s[i]))))
        assert max(errors)<1e-10;independent.append(errors)
    for first,second in ((0,1),(2,3)):
        a,b=result.evaluations[first].result,result.evaluations[second].result
        np.testing.assert_array_equal(a.current_factors.parts,b.current_factors.parts)
        np.testing.assert_array_equal(a.R,b.R)
    record=result.to_dict()
    assert json.loads(json.dumps(record,allow_nan=False))==record
    for saved,row in zip(record['evaluations'],result.evaluations):
        assert len(saved['current_solver']['samples'])==13
        assert saved['current_solver']['step_m']==row.result.current_factors.step_m
    record_property('shape_resolution',json.dumps(record,sort_keys=True))
    record_property('shape_resolution_independent',json.dumps(independent))


def replay(monkeypatch,result,failed=None,error=None):
    values={row.input_json:row.result for row in result.evaluations};calls=[]
    def analyze(self):
        text=self.dumps();calls.append(text)
        if text==failed:raise error or ValueError('original resolution refusal')
        return values[text]
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',analyze)
    return calls


def test_actual_small_mutual_disagreement_is_not_hidden(observed,monkeypatch,record_property):
    doc,outers,previous=observed;calls=replay(monkeypatch,previous)
    result=assess(doc,outers,tolerances={'R':ResolutionTolerance(.005,0.)})
    record_property('shape_resolution_rejection',json.dumps(result.to_dict(),sort_keys=True))
    assert result.completed and not result.accepted and len(calls)==5
    for comparison in result.comparisons:
        a=previous.evaluations[comparison.reference_index].result.R
        b=previous.evaluations[comparison.evaluation_index].result.R
        np.testing.assert_array_equal(comparison.differences['R'],abs(a-b))
        np.testing.assert_array_equal(comparison.allowances['R'],.005*np.maximum(abs(a),abs(b)))
    outer=result.comparisons[-1]
    assert np.any(outer.differences['R'][:,0,1]>outer.allowances['R'][:,0,1])


def test_exact_observation_request_stays_unaccepted(observed,monkeypatch):
    doc,outers,previous=observed;replay(monkeypatch,previous)
    result=assess(doc,outers,tolerances={'C0':ResolutionTolerance(0.,0.)})
    assert result.completed and not result.accepted
    assert result.comparisons[0].accepted and not result.comparisons[1].accepted


@pytest.mark.parametrize('stage',['base','volume','panel','joint','outer:0'])
def test_each_stage_failure_keeps_prior_work(observed,monkeypatch,stage):
    doc,outers,previous=observed;index=[r.stage for r in previous.evaluations].index(stage)
    failed=previous.evaluations[index].input_json;calls=replay(monkeypatch,previous,failed)
    result=assess(doc,outers)
    assert not result.completed and not result.accepted and len(calls)==index+1
    assert len(result.evaluations)==index and result.failure.stage==stage
    assert result.failure.input_json==failed and result.failure.kind=='ValueError'
    saved=result.to_dict();assert saved['failure']['details'] is None
    assert saved['evaluations']==previous.to_dict()['evaluations'][:index]


@pytest.mark.parametrize('partial',[False,True])
def test_staged_line_error_keeps_detailed_current_history(observed,monkeypatch,partial):
    doc,outers,previous=observed;row=previous.evaluations[3];r=row.result
    cause=ValueError('original downstream failure');factors=r.current_factors;stage='mesh'
    if partial:
        cause=PanelShapeCurrentError('shared current failure',samples=factors.samples[:3],request=factors.samples[3].request)
        cause.__cause__=ValueError('original kernel failure');factors=None;stage='current'
    error=ShapePanelLineError(cause,stage=stage,input_json=row.input_json,factors=factors,settings=r.panel_settings)
    calls=replay(monkeypatch,previous,row.input_json,error)
    result=assess(doc,outers);assert len(calls)==4 and len(result.evaluations)==3
    assert result.failure.details==error.to_dict()
    saved=result.to_dict();assert saved['failure']['details']==error.to_dict()
    saved['failure']['details']['stage']='changed'
    assert result.failure.details['stage']==stage
    if partial:
        record=result.failure.details['partial_current']
        assert record['cause_type']=='ValueError' and len(record['samples'])==3
        assert record['failed_request']['request']==r.current_factors.samples[3].request.arguments()


@pytest.mark.parametrize('index',range(5))
def test_interrupt_propagates_from_every_stage(observed,monkeypatch,index):
    doc,outers,previous=observed
    calls=replay(monkeypatch,previous,previous.evaluations[index].input_json,KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):assess(doc,outers)
    assert len(calls)==index+1


@pytest.mark.parametrize('change',['step','width','trace','material','port','frequency','mesh','panel','schema','budget','empty','type'])
def test_complete_plan_admission_precedes_all_fields(monkeypatch,change):
    doc,outers=inputs();raw=outers[0].to_dict();kwargs={};line=raw['line']['line']
    if change=='step':raw['step_fraction']*=.5
    if change=='width':line['cross_section']['box']['width']=.003
    if change=='trace':line['cross_section']['traces'][0]['width']*=.99
    if change=='material':line['cross_section']['layers'][0]['eps_r']=5.
    if change=='port':line['reference_ohms']=75.
    if change=='frequency':line['frequency_hz']=[1e9,3e9]
    if change=='mesh':line['cross_section']['mesh']['edge_size']*=2
    if change=='panel':raw['line']['panel']['panels_per_edge']=16
    if change=='schema':raw['line']['line']['schema']='sipi.transmission-line/7';raw['line']['schema']='sipi.panel-transmission-line/2'
    if change=='budget':kwargs['max_solves']=4
    if change=='empty':outers=[]
    elif change=='type':doc=doc.line
    else:outers=[ShapePanelTransmissionLineDocument.from_dict(raw)]
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('invalid plan reached fields'))
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid plan meshed'))
    with pytest.raises((ValueError,TypeError)):assess(doc,outers,**kwargs)


@pytest.mark.parametrize('v,p,j',list(itertools.product((0.,.4,1.7,2.2),repeat=3)))
def test_four_axis_and_truth_table(monkeypatch,v,p,j):
    doc,outers=inputs();values=[0.,v,p,j,j];calls=[]
    def analyze(self):
        value=values[len(calls)];calls.append(self.dumps())
        matrix=np.ones((2,2,2));matrix[-1,0,1]=matrix[-1,1,0]=1e-9*(1+value)
        return SimpleNamespace(names=('left','right'),frequency=np.array([1e9,2e9]),R=matrix)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',analyze)
    result=assess(doc,outers,tolerances={'R':ResolutionTolerance(0.,1e-9)},max_solves=5)
    expected=[abs(v)<=1,abs(p)<=1,abs(j-v)<=1,abs(j-p)<=1,True]
    assert [c.accepted for c in result.comparisons]==expected
    assert result.completed and result.accepted==all(expected) and len(calls)==5


def test_last_frequency_tiny_mutual_is_checked(monkeypatch):
    doc,outers=inputs();calls=[]
    def analyze(self):
        index=len(calls);calls.append(self.dumps());r=np.full((2,2,2),1e6)
        r[:,0,1]=r[:,1,0]=1e-12
        if index>=2:r[-1,0,1]=r[-1,1,0]=2e-12
        return SimpleNamespace(names=('left','right'),frequency=np.array([1e9,2e9]),R=r)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',analyze)
    result=assess(doc,outers,tolerances={'R':ResolutionTolerance(.005,0.)})
    assert result.completed and not result.accepted
    assert result.comparisons[1].differences['R'][-1,0,1]>result.comparisons[1].allowances['R'][-1,0,1]
