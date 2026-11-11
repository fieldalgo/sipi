# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved two-variable forward goals: exact transport, preflight and references."""
import json
import numpy as np
import pytest

from sipi import CrossSection, CrossSectionDocument
from sipi.study import ImpedanceStudyDocument
from sipi.line_model import TransmissionLineDocument
from sipi.pair_line_goal import seek_forward_pair_impedances, ForwardPairGoalError
from sipi.pair_line_goal_document import ForwardPairDesignDocument
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from sipi.dielectric import ConstantDielectric, PrincipalAxisDielectric, dielectric_to_dict
from test_pair_line_goal import document as line, factory, quantities, synthetic, MESH, reference_record

SCHEMA='sipi.forward-pair-design/1'
Q=('differential_forward_impedance_real','common_forward_impedance_real')

def source(*,physical=False):
    return ImpedanceStudyDocument('asymmetric_coupled_microstrip',
        dict(left_width=.6e-3,right_width=.5e-3,gap=.4e-3,substrate_height=.5e-3,
             eps_r=4.,tan_delta=.02,left_thickness=35e-6,right_thickness=50e-6,
             air_height=10e-3,box_width=24e-3),
        quantity='z_diff_forward',frequency=1e9,materials={},mesh=MESH,
        sampling=dict(kind='corners',variables=[
            dict(name='left_width',lower=.4e-3 if physical else .15e-3,upper=.9e-3 if physical else .6e-3),
            dict(name='gap',lower=.2e-3 if physical else .1e-3,upper=.6e-3 if physical else .3e-3)]))

def document(*,physical=False):
    return ForwardPairDesignDocument(source(physical=physical),
        conductor=line(.6e-3,.4e-3).to_dict()['conductor'],
        targets=dict(zip(Q,[110.,40.] if physical else quantities(1.35,.8))),
        tolerances=dict(zip(Q,[.25,.125] if physical else [1e-6,1e-6])),
        initial=[.7e-3,.35e-3] if physical else None,max_evaluations=64)


def test_saved_direct_execution_roundtrip_known_root_and_snapshot(monkeypatch):
    synthetic(monkeypatch)
    doc=document();result=doc.solve()
    direct=seek_forward_pair_impedances(line,[[.15e-3,.6e-3],[.1e-3,.3e-3]],
        quantities(1.35,.8),tolerances=[1e-6,1e-6])
    assert result.to_dict()==direct.to_dict()
    np.testing.assert_allclose(result.parameters,[1.35*.3e-3,.8*.2e-3],rtol=1e-6)
    report=execute_saved(doc.dumps(),max_evaluations=64)
    assert report['status']=='complete' and report['input']==doc.to_dict()
    assert report['result']==result.to_dict()
    assert normalize_saved(doc.dumps())==doc.dumps() and SCHEMA in saved_schemas()
    raw=doc.to_dict();raw['study']['parameters']['left_width']=1.
    assert ForwardPairDesignDocument.loads(doc.dumps()).dumps()==doc.dumps()
    json.dumps(report,allow_nan=False)


def test_variable_order_and_explicit_target_keys_preserve_meaning(monkeypatch):
    synthetic(monkeypatch)
    raw=document().to_dict();raw['study']['sampling']['variables'].reverse()
    raw['initial']=[.2e-3,.375e-3]
    doc=ForwardPairDesignDocument.from_dict(raw);result=doc.solve()
    np.testing.assert_allclose(result.parameters,[.8*.2e-3,1.35*.3e-3],rtol=1e-6)
    assert result.to_dict()['quantities']==list(Q)
    assert max(abs(np.array(result.refined_residuals)))<=1e-6


@pytest.mark.parametrize('mode',['budget','diagnostics','input_bytes'])
def test_execution_limits_reject_before_goal_or_field(monkeypatch,mode):
    doc=document()
    def forbidden(*a,**k):pytest.fail('rejected controls invoked solver')
    monkeypatch.setattr(ForwardPairDesignDocument,'solve',forbidden)
    monkeypatch.setattr(TransmissionLineDocument,'analyze',forbidden)
    kwargs={'max_evaluations':63} if mode=='budget' else ({'diagnostics':['characteristic']} if mode=='diagnostics' else {'max_input_bytes':16})
    with pytest.raises(ValueError):execute_saved(doc.dumps(),**kwargs)


@pytest.mark.parametrize('mode',['budget','extraction'])
def test_execution_preserves_failed_attempts_and_original_inputs(monkeypatch,mode):
    calls=synthetic(monkeypatch,fail_at=2 if mode=='extraction' else None)
    raw=document().to_dict()
    if mode=='budget':raw['max_evaluations']=2
    doc=ForwardPairDesignDocument.from_dict(raw)
    report=execute_saved(doc.dumps())
    assert report['status']=='failed' and report['error']['quantities']==list(Q)
    error=report['error'];assert error['unit']=='ohm' and len(error['history'])==1
    if mode=='budget':
        assert error['stage']=='budget' and error['attempts']==len(calls)==1
    else:
        assert error['stage']=='search/extraction' and error['attempts']==len(calls)==2
        assert error['cause_type']=='ArithmeticError' and error['input']==json.loads(calls[-1])
        assert 'retained physical failure' in error['message']
    assert error['failed_parameters'] is not None
    json.dumps(report,allow_nan=False)


@pytest.mark.parametrize('stage',['search/factory','search/diagnostic','optimizer','convergence','refinement/target'])
def test_transport_preserves_other_direct_goal_error_stages(monkeypatch,stage):
    import sipi.pair_line_goal_document as implementation
    synthetic(monkeypatch);doc=document();result=doc.solve()
    row=result.history[0]
    def fail(*args,**kwargs):
        raise ForwardPairGoalError('original retained error',[row],attempts=2,stage=stage,
            failed_parameters=row.parameters,cause_type='ArithmeticError',input_json=row.input_json)
    monkeypatch.setattr(implementation,'seek_forward_pair_impedances',fail)
    report=execute_saved(doc.dumps());error=report['error']
    assert report['status']=='failed' and error['stage']==stage and error['attempts']==2
    assert error['input']==json.loads(row.input_json) and error['history']==[row.to_dict()]
    assert error['cause_type']=='ArithmeticError' and error['message']=='original retained error'


@pytest.mark.parametrize('field',['schema','study','conductor','targets_ohm','tolerances_ohm','initial','max_evaluations'])
def test_every_root_field_is_required(field):
    raw=document().to_dict();del raw[field]
    with pytest.raises(ValueError):ForwardPairDesignDocument.from_dict(raw)


@pytest.mark.parametrize('kind',['extra','schema','target_missing','target_extra','target_zero','target_bool',
    'tolerance_negative','tolerance_nan','initial_short','initial_outside','initial_bool',
    'budget_bool','budget_low','budget_high','sweep','one_variable','negative_bound','source_quantity',
    'source_frequency','source_version','conductor','nominal_geometry','corner_geometry'])
def test_strict_inputs_reject_without_meshing(monkeypatch,kind):
    raw=document().to_dict()
    if kind=='extra':raw['extra']=1
    elif kind=='schema':raw['schema']='sipi.forward-pair-design/2'
    elif kind=='target_missing':del raw['targets_ohm'][Q[1]]
    elif kind=='target_extra':raw['targets_ohm']['z_diff']=100.
    elif kind=='target_zero':raw['targets_ohm'][Q[0]]=0.
    elif kind=='target_bool':raw['targets_ohm'][Q[0]]=True
    elif kind=='tolerance_negative':raw['tolerances_ohm'][Q[1]]=-1.
    elif kind=='tolerance_nan':raw['tolerances_ohm'][Q[1]]=np.nan
    elif kind=='initial_short':raw['initial']=[.3e-3]
    elif kind=='initial_outside':raw['initial']=[2.,.2e-3]
    elif kind=='initial_bool':raw['initial']=[True,.2e-3]
    elif kind=='budget_bool':raw['max_evaluations']=True
    elif kind=='budget_low':raw['max_evaluations']=1
    elif kind=='budget_high':raw['max_evaluations']=10001
    elif kind=='sweep':raw['study']['sampling'].update(kind='sweep',count=2)
    elif kind=='one_variable':raw['study']['sampling']['variables'].pop()
    elif kind=='negative_bound':raw['study']['sampling']['variables'][0]['lower']=-1.
    elif kind=='source_quantity':raw['study']['quantity']='z0'
    elif kind=='source_frequency':raw['study']['material_evaluation']['frequency_hz']=0.
    elif kind=='source_version':raw['study']['schema']='sipi.impedance-study/2'
    elif kind=='conductor':raw['conductor']['conductors']['positive']['conductivity']=0.
    elif kind=='nominal_geometry':raw['study']['parameters']['left_width']=-1.
    elif kind=='corner_geometry':raw['study']['sampling']['variables'][0]['upper']=1.
    def forbidden(*a,**k):pytest.fail('invalid saved input reached mesh')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises((ValueError,TypeError)):ForwardPairDesignDocument.from_dict(raw)


@pytest.mark.parametrize('text',['{"schema":"x","schema":"x"}','{"x":NaN}','{"x":Infinity}','[]'])
def test_duplicate_nonfinite_and_nonobject_json_reject(text):
    with pytest.raises((ValueError,TypeError)):ForwardPairDesignDocument.loads(text)


def test_fixed_pitch_and_material_leaf_factory_without_preliminary_solve(monkeypatch):
    import sipi.pair_line_goal_document as implementation
    raw=source().to_dict();raw['fixed_pitch_m']=.95e-3
    raw['schema']='sipi.impedance-study/4'
    raw['material_evaluation']['materials']={'substrate':dielectric_to_dict(ConstantDielectric(4.,.02))}
    raw['material_variables']={'dk':dict(region='substrate',path=['eps_r'])}
    raw['sampling']['variables']=[dict(name='left_width',lower=.4e-3,upper=.8e-3),dict(name='dk',lower=3.,upper=5.)]
    study=ImpedanceStudyDocument.from_dict(raw)
    def forbidden(*a,**k):pytest.fail('input adapter ran a preliminary solve')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(ImpedanceStudyDocument,'analyze',forbidden)
    doc=ForwardPairDesignDocument(study,conductor=dict(kind='perfect'),targets=dict(zip(Q,[110.,40.])),tolerances=dict(zip(Q,[1.,1.])),initial=[.65e-3,3.7])
    def inspect(factory,bounds,targets,**options):
        assert bounds==[[.4e-3,.8e-3],[3.,5.]] and options['initial']==[.65e-3,3.7]
        for width,eps in [(.4e-3,3.),(.65e-3,3.7),(.8e-3,5.)]:
            item=factory(width,eps);d=item.to_dict();t=d['cross_section']['traces']
            assert t[1]['x']-t[0]['x']==pytest.approx(.95e-3,rel=1e-12)
            assert d['materials']['substrate']['parameters']['eps_r']==eps
            assert d['length_m']==0. and d['frequency_hz']==[1e9]
        return 'inspected'
    monkeypatch.setattr(implementation,'seek_forward_pair_impedances',inspect)
    assert doc.solve()=='inspected'


def test_fixed_stack_and_tilted_material_without_preliminary_solve(monkeypatch):
    import sipi.pair_line_goal_document as implementation
    material=PrincipalAxisDielectric(ConstantDielectric(3.,.01),ConstantDielectric(5.,.02),.2)
    study=ImpedanceStudyDocument('coupled_layered_stripline',
        dict(width=.3e-3,gap=.2e-3,lower_height=.4e-3,upper_height=.6e-3,
             lower_eps_r=3.,upper_eps_r=5.,thickness=35e-6,box_width=4e-3),
        quantity='z_diff_forward',frequency=1e9,materials={'lower':material},mesh=MESH,
        fixed_plane_spacing_m=1e-3,sampling=dict(kind='corners',variables=[
            dict(name='lower_height',lower=.3e-3,upper=.5e-3),dict(name='width',lower=.2e-3,upper=.4e-3)]))
    def forbidden(*a,**k):pytest.fail('input adapter ran a preliminary solve')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(ImpedanceStudyDocument,'analyze',forbidden)
    doc=ForwardPairDesignDocument(study,conductor=dict(kind='perfect'),targets=dict(zip(Q,[100.,40.])),tolerances=dict(zip(Q,[1.,1.])))
    def inspect(factory,bounds,targets,**options):
        for height,width in [(.3e-3,.2e-3),(.45e-3,.35e-3),(.5e-3,.4e-3)]:
            d=factory(height,width).to_dict();layers=d['cross_section']['layers']
            assert d['materials']==study.to_dict()['material_evaluation']['materials']
            expected=study.to_dict();expected['parameters'].update(lower_height=height,upper_height=1e-3-height,width=width)
            from sipi.line_input import _line_from_values
            assert d==_line_from_values(expected,dict(kind='perfect')).to_dict()
        return 'inspected'
    monkeypatch.setattr(implementation,'seek_forward_pair_impedances',inspect)
    assert doc.solve()=='inspected'


@pytest.fixture(scope='module')
def solved():
    doc=document(physical=True)
    return doc,doc.solve()


def test_actual_saved_search_matches_direct_full_history_and_rlgc(solved):
    doc,result=solved
    direct=seek_forward_pair_impedances(line,[[.4e-3,.9e-3],[.2e-3,.6e-3]],
        [110.,40.],tolerances=[.25,.125],initial=[.7e-3,.35e-3],max_evaluations=64)
    assert result.to_dict()==direct.to_dict() and result.history==direct.history
    assert np.all(abs(np.array(result.residuals))<=[.25,.125])
    assert np.all(abs(np.array(result.refined_residuals))<=[.25,.125])
    assert np.all(abs(np.array(result.refined_impedances)/result.impedances-1)<=.005)
    for a,b in [(result.result,direct.result),(result.refined_result,direct.refined_result)]:
        for key in ['R','L','G','C']:np.testing.assert_allclose(getattr(a,key),getattr(b,key),rtol=1e-10)
    raw=result.document.to_dict();fine=result.refined_document.to_dict()
    for key in ['edge_size','far_size','grade']:raw['cross_section']['mesh'][key]/=2
    assert raw==fine and raw['conductor']==doc.to_dict()['conductor']


def test_saved_goal_finite_outer_gates_and_independent_eigenspaces(solved):
    from crosscheck import require_tool,Stopwatch
    scipy=require_tool('scipy');clock=Stopwatch();result=solved[1]
    base=np.array(result.refined_impedances);previous=base.copy();changes=[]
    lines=[result.result,result.refined_result]
    for box,air in [(36e-3,15e-3),(48e-3,20e-3)]:
        raw=line(*result.parameters,box=box,air=air).to_dict()
        raw['cross_section']['mesh']=result.refined_document.to_dict()['cross_section']['mesh']
        current=TransmissionLineDocument.from_dict(raw).analyze();lines.append(current)
        values=np.diag(current.characteristic().mixed_mode().z_characteristic[0]).real
        assert np.all(abs(values-result.targets)<=result.tolerances)
        assert np.all(abs(values/base-1)<=.005)
        changes.append(abs(values-previous));previous=values
    # This finite-domain criterion is specific to the fixed 1 GHz fixture.
    np.testing.assert_array_equal(result.refined_result.frequency, [1e9])
    assert changes[1][1] < changes[0][1]
    assert np.all(np.asarray(changes)[:, 0] / abs(base[0]) <= 1e-4)
    errors=dict(Zc=0.,Zdd=0.,Zcc=0.);a=np.array([[1.,-1.],[.5,.5]])
    for current in lines:
        with clock('openphysics'):actual=current.characteristic().z_characteristic[0]
        with clock('reference'):
            omega=2*np.pi*current.frequency[0];z=current.R[0]+1j*omega*current.L[0];y=current.G[0]+1j*omega*current.C[0]
            scale=np.sqrt(abs(z).max()/abs(y).max())
            roots,vectors=scipy.linalg.eig(np.block([[np.zeros_like(z),z/scale],[scale*y,np.zeros_like(y)]]))
            selected=roots.imag>0;assert np.count_nonzero(selected)==2 and np.all(roots[selected].real>=0)
            v=vectors[:,selected];expected=scale*v[:2]@np.linalg.inv(v[2:]);mixed=a@expected@a.T
        errors['Zc']=max(errors['Zc'],float(abs(actual-expected).max()/abs(expected).max()))
        for i,key in enumerate(['Zdd','Zcc']):errors[key]=max(errors[key],float(abs((a@actual@a.T)[i,i]/mixed[i,i]-1)))
    reference_record('saved-two-variable-forward-goal-2n','scipy',
        'balanced 2N voltage/current positive-phase eigenspaces on requested/refined/larger domains',errors,clock)


def test_uniform_two_material_variables_obey_complex_scaling_without_unique_claim():
    from sipi.templates import coupled_stripline
    from crosscheck import require_tool,Stopwatch
    scipy=require_tool('scipy');clock=Stopwatch();a=np.array([[1.,-1.],[.5,.5]])
    parameters=dict(width=.3e-3,gap=.2e-3,plane_spacing=1e-3,eps_r=1.,thickness=50e-6,box_width=6e-3)
    def vacuum(mesh):
        field=CrossSectionDocument(coupled_stripline(**parameters),mesh=mesh).analyze()
        ls=np.max(abs(field.L));cs=np.max(abs(field.C))
        values,vectors=scipy.linalg.eigh(field.L/ls);half=(vectors*np.sqrt(values))@vectors.T
        values,vectors=scipy.linalg.eigh(half@(field.C/cs)@half)
        return np.sqrt(ls/cs)*half@(vectors*(1/np.sqrt(values)))@vectors.T@half
    expected=vacuum(MESH)/np.sqrt(3.7*(1-1j*.02))
    targets=np.diag(a@expected@a.T).real
    study=ImpedanceStudyDocument('coupled_stripline',parameters,quantity='z_diff_forward',
        frequency=1e9,materials={'dielectric':ConstantDielectric(4.,.03)},mesh=MESH,
        material_variables={'dk':dict(region='dielectric',path=['eps_r']),
                            'df':dict(region='dielectric',path=['tan_delta'])},
        sampling=dict(kind='corners',variables=[dict(name='dk',lower=3.,upper=5.),dict(name='df',lower=.01,upper=.04)]))
    doc=ForwardPairDesignDocument(study,conductor=dict(kind='perfect'),targets=dict(zip(Q,targets)),
        tolerances=dict(zip(Q,targets*.005)),initial=[3.7,.02],max_evaluations=2)
    result=doc.solve();assert result.parameters==(3.7,.02) and len(result.history)==2
    errors=dict(Zc=0.,Zdd=0.,Zcc=0.)
    for item,physical in [(result.document,result.result),(result.refined_document,result.refined_result)]:
        with clock('openphysics'):actual=physical.characteristic().z_characteristic[0]
        with clock('reference'):reference=vacuum(item.to_dict()['cross_section']['mesh'])/np.sqrt(3.7*(1-1j*.02))
        errors['Zc']=max(errors['Zc'],float(abs(actual-reference).max()/abs(reference).max()))
        for i,key in enumerate(['Zdd','Zcc']):errors[key]=max(errors[key],float(abs((a@actual@a.T)[i,i]/(a@reference@a.T)[i,i]-1)))
        material=item.to_dict()['materials']['dielectric']['parameters']
        assert material['eps_r']==3.7 and material['tan_delta']==.02
    reference_record('saved-pair-two-material-complex-scaling','scipy',
        'independent SPD vacuum characteristic scaled by sqrt complex uniform dielectric',errors,clock)
