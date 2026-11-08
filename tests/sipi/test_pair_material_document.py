# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict named pair material bindings, preflight and independently checked replay."""
import json
import math
from types import SimpleNamespace

import numpy as np
import pytest

from sipi import CrossSection, CrossSectionDocument, PairImpedanceDesignDocument, seek_pair_impedances
from sipi.dielectric import DebyeDielectric, ConstantDielectric, PrincipalAxisDielectric
from sipi.templates import coupled_stripline
from sipi.execution import normalize_saved, execute_saved, saved_schemas
import sipi.pair_design as api
import sipi.pair_design_document as module

P=dict(width=.5e-3,gap=.1e-3,plane_spacing=1e-3,eps_r=1.,box_width=8e-3)
MESH=dict(edge_size=1e-6,far_size=.125e-3,grade=.1)
TARGETS=dict(z_diff=69.86609070536932,z_common=30.721416289368904)
TOLERANCES=dict(z_diff=.5,z_common=.2)
BINDING={'strength':dict(region='dielectric',path=['strengths',0])}


def document(**changes):
    args=dict(template='coupled_stripline',parameters=P,variables=['width','strength'],
        bounds=[[.3e-3,.7e-3],[2.,6.]],targets=TARGETS,tolerances=TOLERANCES,
        mesh=MESH,frequency=1e9,materials={'dielectric':DebyeDielectric(2.,[4.],[1e9])},
        material_variables=BINDING,max_evaluations=64)
    args.update(changes);return PairImpedanceDesignDocument(**args)


def forbidden(*args,**kwargs):pytest.fail('preflight reached field or optimizer')


def test_canonical_saved_v2_isolation_and_no_field_or_optimizer(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr(module,'seek_pair_impedances',forbidden)
    bindings=json.loads(json.dumps(BINDING));parameters=dict(P)
    d=document(material_variables=bindings,parameters=parameters);text=d.dumps()
    assert d.to_dict()['schema']=='sipi.pair-impedance-design/2'
    assert normalize_saved(text)==text and PairImpedanceDesignDocument.loads(text).dumps()==text
    assert d.to_dict()['schema'] in saved_schemas()
    bindings['strength']['path'][0]='bad';parameters['width']=2
    data=d.to_dict();data['material_variables'].clear()
    assert d.dumps()==text


@pytest.mark.parametrize('mutate',[
    lambda d:d.pop('material_variables'),lambda d:d.update(material_variables={}),
    lambda d:d.update(material_variables=None),lambda d:d.update(material_evaluation=None),
    lambda d:d.update(schema='sipi.pair-impedance-design/1'),
    lambda d:d.update(schema='sipi.pair-impedance-design/999'),lambda d:d.update(extra=1),
    lambda d:d['material_variables']['strength'].update(region='unknown'),
    lambda d:d['material_variables']['strength'].update(path=[]),
    lambda d:d['material_variables']['strength'].update(path=['strengths']),
    lambda d:d['material_variables']['strength'].update(path=['strengths',True]),
    lambda d:d['material_variables']['strength'].update(path=['strengths',-1]),
    lambda d:d['material_variables']['strength'].update(path=['strengths',2]),
    lambda d:d['material_variables']['strength'].update(path=['strengths','0']),
    lambda d:d['material_variables']['strength'].update(path=['missing']),
    lambda d:d['material_variables']['strength'].update(extra=1),
    lambda d:d['material_variables'].update(width=dict(region='dielectric',path=['eps_inf'])),
    lambda d:d['material_variables'].update(unused=dict(region='dielectric',path=['eps_inf'])),
    lambda d:d['variables'][0].update(name='strength'),
    lambda d:d['variables'][0].update(name='eps_r'),
    lambda d:d['variables'][1].update(bounds=[0,6]),
    lambda d:d['material_evaluation'].update(frequency_hz=True),
])
def test_invalid_binding_documents_rejected_without_fields(monkeypatch,mutate):
    data=document().to_dict();mutate(data)
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises((ValueError,TypeError)):PairImpedanceDesignDocument.from_dict(data)


@pytest.mark.parametrize('text',['{"schema":"sipi.pair-impedance-design/2","schema":"x"}',
    '{"schema":"sipi.pair-impedance-design/2","material_variables":{"a":1,"a":2}}',
    '{"schema":"sipi.pair-impedance-design/2","initial":[NaN,1]}',
    '{"schema":"sipi.pair-impedance-design/2","initial":[1e999,1]}'])
def test_duplicate_and_nonfinite_json_rejected(text):
    with pytest.raises(ValueError):PairImpedanceDesignDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


def test_binding_requires_fixed_material_input_and_distinct_targets():
    with pytest.raises(ValueError):document(frequency=None,materials=None)
    with pytest.raises(ValueError):document(variables=['a','b'],bounds=[[2,3],[4,5]],
        material_variables={n:dict(region='dielectric',path=['strengths',0]) for n in ['a','b']})


@pytest.mark.parametrize('initial',[None,[.5e-3,3*math.pi/4]])
def test_initial_model_is_checked_even_when_nominal_and_all_corners_are_valid(monkeypatch,initial):
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError,match='diagonal'):
        document(variables=['width','angle'],bounds=[[.3e-3,.7e-3],[math.pi/2,math.pi]],
            materials={'dielectric':PrincipalAxisDielectric(ConstantDielectric(2.),
                ConstantDielectric(4.),math.pi/2)},
            material_variables={'angle':dict(region='dielectric',path=['angle_rad'])},initial=initial)


def test_corner_material_model_is_checked_before_fields(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError):
        document(variables=['width','epsilon'],bounds=[[.3e-3,.7e-3],[.5,2]],
            material_variables={'epsilon':dict(region='dielectric',path=['eps_inf'])})


def test_variable_order_fixed_pitch_and_geometry_model_callbacks(monkeypatch):
    def solve(factory,bounds,targets,**kw):
        assert bounds==[[2.,6.],[.3e-3,.7e-3]]
        assert kw['frequency']==1e9 and 'materials' not in kw
        assert kw['initial']==[3.,.45e-3]
        s=factory(3.,.45e-3);a,b=s.traces[:2]
        assert a.width==.45e-3 and b.x-a.x==pytest.approx(.8e-3,rel=1e-12)
        m=kw['material_factory'](3.,.45e-3)
        assert m['dielectric'].strengths==(3.,)
        return 'checked'
    monkeypatch.setattr(module,'seek_pair_impedances',solve)
    d=document(parameters=dict(P,gap=.3e-3),variables=['strength','width'],
        bounds=[[2.,6.],[.3e-3,.7e-3]],fixed_pitch_m=.8e-3,initial=[3.,.45e-3])
    assert PairImpedanceDesignDocument.loads(d.dumps()).solve()=='checked'


def test_two_material_leaves_are_allowed_without_geometry_or_uniqueness_claim(monkeypatch):
    def solve(factory,bounds,targets,**kw):
        assert factory(2.,4.).traces[0].width==P['width']
        model=kw['material_factory'](3.,2.)['dielectric']
        assert model.permittivity(1e9).real==4.
        return 'checked'
    monkeypatch.setattr(module,'seek_pair_impedances',solve)
    d=document(variables=['base','strength'],bounds=[[1.,3.],[2.,6.]],
        material_variables=dict(BINDING,base=dict(region='dielectric',path=['eps_inf'])))
    assert d.solve()=='checked'


def test_execution_budget_is_checked_before_factories(monkeypatch):
    d=document();monkeypatch.setattr(module,'seek_pair_impedances',forbidden)
    with pytest.raises(ValueError,match='budget'):execute_saved(d.dumps(),max_evaluations=63)


def test_execution_retains_distinct_completed_and_current_failed_materials(monkeypatch):
    calls=[]
    def analyze(doc,value,quantity):
        calls.append(json.loads(json.dumps(value)))
        if len(calls)==2:raise ArithmeticError('field failure with changed strength')
        return SimpleNamespace(names=('positive','negative'),even_odd=lambda:dict(z_diff=100.,z_common=40.))
    monkeypatch.setattr(api,'_analyze_material',analyze)
    d=document(variables=['strength','width'],bounds=[[2.,6.],[.3e-3,.7e-3]])
    out=execute_saved(d.dumps());error=out['error']
    assert out['status']=='failed' and out['result'] is None
    assert error['stage']=='search/extraction' and error['attempts']==2
    assert error['material_evaluation']==calls[1]!=calls[0]
    assert error['history'][0]['material_evaluation']==calls[0]
    assert error['input'] and error['cause_type']=='ArithmeticError'
    json.dumps(out,allow_nan=False)


def test_real_saved_execution_matches_raw_api_and_independent_cohn():
    from test_sipi_references import coupled_stripline_z
    d=document(max_evaluations=2);data=d.to_dict()
    def geometry(w,s):return coupled_stripline(**dict(data['parameters'],width=w))
    def material(w,s):return {'dielectric':DebyeDielectric(2.,[s],[1e9])}
    direct=seek_pair_impedances(geometry,[v['bounds'] for v in data['variables']],
        [TARGETS[q] for q in ['z_diff','z_common']],tolerances=[.5,.2],max_evaluations=2,
        mesh=data['mesh'],frequency=1e9,material_factory=material)
    out=execute_saved(d.dumps(),max_evaluations=2)
    assert out['status']=='complete' and out['result']==direct.to_dict()
    w,s=direct.parameters;even,odd=coupled_stripline_z(w,P['gap'],P['plane_spacing'],2+s/2)
    independent=np.array([2*odd,even/2]);target=np.array([TARGETS['z_diff'],TARGETS['z_common']])
    for values in [direct.impedances,direct.refined_impedances,independent]:
        assert np.all(abs(np.array(values)-target)<=np.array([.5,.2]))
    assert len(direct.history)==2 and direct.history[-1].stage=='refinement'
    for row in direct.history:
        assert json.loads(row.material_evaluation_json)['materials']['dielectric']['parameters']['strengths']==[s]
    print('saved material pair requested/refined/cohn',direct.impedances,direct.refined_impedances,independent)
