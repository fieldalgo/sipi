# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
import numpy as np
import pytest
from sipi.panel_pair_goal_document import PanelForwardPairDesignDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_pair_goal import seek_panel_forward_pair_impedances
from sipi.pair_line_goal import ForwardPairGoalError
from sipi.pair_line_goal_document import ForwardPairDesignDocument
from sipi import CrossSection
from test_pair_line_goal_document import document as saved
from test_panel_pair_goal import synthetic, quantities, document as line


def document():return PanelForwardPairDesignDocument(saved())


def test_saved_direct_modal_root_and_snapshot(monkeypatch):
    synthetic(monkeypatch);doc=document();result=doc.solve()
    direct=seek_panel_forward_pair_impedances(lambda w,g:PanelTransmissionLineDocument(line(w,g)),
        [[.15e-3,.6e-3],[.1e-3,.3e-3]],quantities(1.35,.8),tolerances=[1e-6,1e-6])
    assert result.to_dict()==direct.to_dict()
    np.testing.assert_allclose(result.parameters,[1.35*.3e-3,.8*.2e-3],rtol=1e-6)
    assert PanelForwardPairDesignDocument.loads(doc.dumps()).dumps()==doc.dumps()
    changed=doc.to_dict();changed['panel']['panels_per_edge']=64;changed['design']['study']['parameters']['left_width']=1
    assert doc.panel_options['panels_per_edge']==32
    assert doc.design.dumps()==saved().dumps()
    json.dumps(result.to_dict(),allow_nan=False)


def test_field_free_preflight(monkeypatch):
    def forbidden(*a,**k):pytest.fail('normalization ran fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    doc=document();assert PanelForwardPairDesignDocument.loads(doc.dumps()).dumps()==doc.dumps()


@pytest.mark.parametrize('where',['root','design','panel'])
@pytest.mark.parametrize('change',['extra','missing'])
def test_exact_keys(where,change):
    data=document().to_dict();target=data if where=='root' else data[where]
    if change=='extra':target['unexpected']=1
    else:target.pop(next(iter(target)))
    with pytest.raises(ValueError):PanelForwardPairDesignDocument.from_dict(data)


@pytest.mark.parametrize('value',[0,1,2,3,True,4.,10001])
def test_saved_minimum_budget(value):
    data=document().to_dict();data['design']['max_evaluations']=value
    with pytest.raises(ValueError):PanelForwardPairDesignDocument.from_dict(data)


@pytest.mark.parametrize('key,value',[('panels_per_edge',129),('panels_per_edge',True),('ground_modes',63),('interpolation_degree',11)])
def test_panel_controls_and_future_refinement(key,value):
    data=document().to_dict();data['panel'][key]=value
    with pytest.raises(ValueError):PanelForwardPairDesignDocument.from_dict(data)


def test_duplicate_and_nonfinite_keys():
    text=document().dumps()
    with pytest.raises(ValueError):PanelForwardPairDesignDocument.loads(text.replace('"ground_modes": 512','"ground_modes": 512, "ground_modes": 512'))
    with pytest.raises(ValueError):PanelForwardPairDesignDocument.loads(text.replace('"ground_modes": 512','"ground_modes": NaN'))
    with pytest.raises(ValueError):PanelForwardPairDesignDocument.loads(text.replace('sipi.panel-forward-pair-design/1','sipi.panel-forward-pair-design/2'))


def test_swapped_parameters_preserve_physical_meaning(monkeypatch):
    synthetic(monkeypatch);raw=document().to_dict();raw['design']['study']['sampling']['variables'].reverse();raw['design']['initial']=[.2e-3,.375e-3]
    result=PanelForwardPairDesignDocument.from_dict(raw).solve()
    np.testing.assert_allclose(result.parameters,[.8*.2e-3,1.35*.3e-3],rtol=1e-6)
    assert result.to_dict()['quantities']==['differential_forward_impedance_real','common_forward_impedance_real']


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_original_error_from_each_stage(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt);data=document().to_dict();data['design']['initial']=[1.35*.3e-3,.8*.2e-3];data['design']['max_evaluations']=4
    with pytest.raises(ForwardPairGoalError) as caught:PanelForwardPairDesignDocument.from_dict(data).solve()
    e=caught.value
    assert e.attempts==attempt and len(e.history)==attempt-1
    assert isinstance(e.__cause__,ArithmeticError) and e.input_json==calls[-1]


def test_wrong_nested_schema_and_constructor_type():
    with pytest.raises(TypeError):PanelForwardPairDesignDocument({})
    data=document().to_dict();data['design']['schema']='sipi.forward-pair-design/2'
    with pytest.raises(ValueError):PanelForwardPairDesignDocument.from_dict(data)


def test_fixed_pitch_and_material_leaf_factory_preserved(monkeypatch):
    import sipi.panel_pair_goal_document as implementation
    from test_pair_line_goal_document import source,Q
    from sipi.study import ImpedanceStudyDocument
    from sipi.dielectric import ConstantDielectric,dielectric_to_dict
    raw=source().to_dict();raw['fixed_pitch_m']=.95e-3;raw['schema']='sipi.impedance-study/4'
    raw['material_evaluation']['materials']={'substrate':dielectric_to_dict(ConstantDielectric(4.,.02))}
    raw['material_variables']={'dk':dict(region='substrate',path=['eps_r'])}
    raw['sampling']['variables']=[dict(name='left_width',lower=.4e-3,upper=.8e-3),dict(name='dk',lower=3.,upper=5.)]
    study=ImpedanceStudyDocument.from_dict(raw)
    def forbidden(*a,**k):pytest.fail('preliminary solve')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(ImpedanceStudyDocument,'analyze',forbidden)
    design=ForwardPairDesignDocument(study,conductor={'kind':'perfect'},targets=dict(zip(Q,[110.,40.])),tolerances=dict(zip(Q,[1.,1.])),initial=[.65e-3,3.7])
    doc=PanelForwardPairDesignDocument(design,panels_per_edge=16,ground_modes=1024,interpolation_degree=12)
    def inspect(factory,bounds,targets,**options):
        assert bounds==[[.4e-3,.8e-3],[3.,5.]] and options['initial']==[.65e-3,3.7]
        for width,eps in [(.4e-3,3.),(.65e-3,3.7),(.8e-3,5.)]:
            item=factory(width,eps);d=item.to_dict()['line'];t=d['cross_section']['traces']
            assert t[1]['x']-t[0]['x']==pytest.approx(.95e-3,rel=1e-12)
            assert d['materials']['substrate']['parameters']['eps_r']==eps
            assert d['length_m']==0. and d['frequency_hz']==[1e9]
            assert item.panel_options==doc.panel_options
        return 'inspected'
    monkeypatch.setattr(implementation,'seek_panel_forward_pair_impedances',inspect)
    assert doc.solve()=='inspected'


def test_unsupported_reference_boundaries_do_not_fall_back(monkeypatch):
    from sipi.study import ImpedanceStudyDocument
    from test_pair_line_goal_document import Q,MESH
    study=ImpedanceStudyDocument('coupled_layered_stripline',dict(width=.3e-3,gap=.2e-3,lower_height=.4e-3,upper_height=.6e-3,lower_eps_r=3.,upper_eps_r=5.,thickness=35e-6,box_width=4e-3),quantity='z_diff_forward',frequency=1e9,materials={},mesh=MESH,fixed_plane_spacing_m=1e-3,sampling=dict(kind='corners',variables=[dict(name='lower_height',lower=.3e-3,upper=.5e-3),dict(name='width',lower=.2e-3,upper=.4e-3)]))
    design=ForwardPairDesignDocument(study,conductor={'kind':'perfect'},targets=dict(zip(Q,[100.,40.])),tolerances=dict(zip(Q,[1.,1.])))
    def forbidden(*a,**k):pytest.fail('unsupported saved input reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError,match='bottom ground and open top/sides'):PanelForwardPairDesignDocument(design)


def test_common_execution_matches_direct_and_retains_whole_input(monkeypatch):
    from sipi.execution import execute_saved,normalize_saved,saved_schemas
    synthetic(monkeypatch);doc=document();direct=doc.solve().to_dict()
    out=execute_saved(doc.dumps(),max_evaluations=64)
    assert out['status']=='complete' and out['input']==doc.to_dict() and out['result']==direct
    assert out['error'] is None and normalize_saved(doc.dumps())==doc.dumps()
    assert 'sipi.panel-forward-pair-design/1' in saved_schemas()
    assert len(out['result']['refinements'])==3
    json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('mode',['budget','diagnostics','input_bytes'])
def test_transport_limits_reject_before_solver(monkeypatch,mode):
    from sipi.execution import execute_saved
    doc=document()
    def forbidden(*a,**k):pytest.fail('refused request reached solver')
    monkeypatch.setattr(PanelForwardPairDesignDocument,'solve',forbidden)
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    options={'max_evaluations':63} if mode=='budget' else ({'diagnostics':['characteristic']} if mode=='diagnostics' else {'max_input_bytes':16})
    with pytest.raises(ValueError):execute_saved(doc.dumps(),**options)


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_common_execution_keeps_real_failures_from_every_stage(monkeypatch,attempt):
    from sipi.execution import execute_saved
    calls=synthetic(monkeypatch,fail_at=attempt);data=document().to_dict();data['design'].update(initial=[1.35*.3e-3,.8*.2e-3],max_evaluations=4)
    doc=PanelForwardPairDesignDocument.from_dict(data)
    out=execute_saved(doc.dumps(),max_evaluations=4);error=out['error']
    assert out['status']=='failed' and out['result'] is None and out['input']==doc.to_dict()
    assert error['attempts']==attempt and len(error['history'])==attempt-1
    assert error['stage']==['search/extraction','volume-refinement/extraction','panel-refinement/extraction','joint-refinement/extraction'][attempt-1]
    assert error['input']==json.loads(calls[-1]) and error['cause_type']=='ArithmeticError'
    assert error['unit']=='ohm' and error['quantities']==['differential_forward_impedance_real','common_forward_impedance_real']
    json.dumps(out,allow_nan=False)


def test_common_execution_does_not_spend_reserved_refinement_budget(monkeypatch):
    from sipi.execution import execute_saved
    calls=synthetic(monkeypatch);data=document().to_dict();data['design']['max_evaluations']=4
    out=execute_saved(PanelForwardPairDesignDocument.from_dict(data).dumps(),max_evaluations=4)
    assert out['status']=='failed' and out['error']['stage']=='budget'
    assert out['error']['attempts']==len(calls)==len(out['error']['history'])==1


@pytest.mark.parametrize('stage',['search/factory','search/diagnostic','optimizer','convergence',
                                 'volume-refinement/target','panel-refinement/convergence','joint-refinement/target'])
def test_transport_preserves_other_goal_failures(monkeypatch,stage):
    from sipi.execution import execute_saved
    import sipi.panel_pair_goal_document as implementation
    synthetic(monkeypatch);doc=document();row=doc.solve().history[0]
    def fail(*args,**kwargs):
        raise ForwardPairGoalError('original error',[row],attempts=2,stage=stage,
            failed_parameters=row.parameters,cause_type='ArithmeticError',input_json=row.input_json)
    monkeypatch.setattr(implementation,'seek_panel_forward_pair_impedances',fail)
    out=execute_saved(doc.dumps());error=out['error']
    assert out['status']=='failed' and error['stage']==stage and error['attempts']==2
    assert error['input']==json.loads(row.input_json) and error['history']==[row.to_dict()]
    assert error['cause_type']=='ArithmeticError' and error['failed_parameters']==list(row.parameters)
