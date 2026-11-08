# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved finite-frequency goals: strict inputs, preflight and actual replay."""
import json
import math
from types import SimpleNamespace

import numpy as np
import pytest

from sipi import CrossSection, SampledImpedanceDesignDocument, seek_sampled_impedance
from sipi.templates import coupled_stripline
from sipi.dielectric import DebyeDielectric,ConstantDielectric,PrincipalAxisDielectric
from sipi.execution import normalize_saved,execute_saved,saved_schemas
import sipi.sampled_design as api
import sipi.sampled_design_document as module

P=dict(width=.5e-3,gap=.1e-3,plane_spacing=1e-3,eps_r=1.,box_width=8e-3)
F=[1e8,1e10];TARGET=[57.23463009022641,97.84159316427296]
MESH=dict(edge_size=1e-6,far_size=.125e-3,grade=.1)
BINDING={'strength':dict(region='dielectric',path=['strengths',0])}


def document(**changes):
    args=dict(template='coupled_stripline',parameters=P,variables=['width','strength'],
        bounds=[[.3e-3,.7e-3],[2.,6.]],frequencies=F,targets=TARGET,tolerances=[.5,.5],
        quantity='z_diff',mesh=MESH,materials={'dielectric':DebyeDielectric(2.,[4.],[1e9])},
        material_variables=BINDING,max_evaluations=64)
    args.update(changes);return SampledImpedanceDesignDocument(**args)


def forbidden(*args,**kwargs):pytest.fail('preflight performed field or optimization')


def test_canonical_input_copies_and_registry_without_fields(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr(module,'seek_sampled_impedance',forbidden)
    parameters=dict(P);binding=json.loads(json.dumps(BINDING));frequencies=np.array(F)
    d=document(parameters=parameters,material_variables=binding,frequencies=frequencies)
    text=d.dumps();assert normalize_saved(text)==text
    assert SampledImpedanceDesignDocument.loads(text).dumps()==text
    assert d.to_dict()['schema']=='sipi.sampled-impedance-design/1' in saved_schemas()
    parameters['width']=1;binding.clear();frequencies[:]=0
    data=d.to_dict();data['materials'].clear();data['variables'].clear()
    assert d.dumps()==text


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.sampled-impedance-design/999'),
    lambda d:d.pop('material_variables'),lambda d:d.update(material_variables=None),
    lambda d:d.update(materials=None),lambda d:d.update(extra=1),
    lambda d:d.update(quantity='alpha'),lambda d:d.update(quantity=[]),
    lambda d:d.update(frequencies_hz=[1e9]),lambda d:d.update(frequencies_hz=list(range(65))),
    lambda d:d.update(frequencies_hz=[1e9,1e9]),lambda d:d.update(frequencies_hz=[2e9,1e9]),
    lambda d:d.update(frequencies_hz=[0,True]),lambda d:d.update(frequencies_hz=[-1,1]),
    lambda d:d.update(targets_ohm=[100]),lambda d:d.update(targets_ohm=[0,100]),
    lambda d:d.update(tolerances_ohm=[1,False]),lambda d:d.update(tolerances_ohm=1),
    lambda d:d['variables'][1].update(name='width'),lambda d:d['variables'][0].update(name='eps_r'),
    lambda d:d['variables'][0].update(bounds=[.7e-3,.3e-3]),
    lambda d:d['variables'][1].update(bounds=[0,6]),lambda d:d['variables'][0].update(extra=1),
    lambda d:d.update(initial=[.2e-3,4]),lambda d:d.update(initial=[True,4]),
    lambda d:d.update(max_evaluations=True),lambda d:d.update(mesh={'unknown':1}),
    lambda d:d['material_variables']['strength'].update(path=['strengths',True]),
    lambda d:d['material_variables']['strength'].update(path=['strengths']),
    lambda d:d['material_variables']['strength'].update(region='unknown'),
    lambda d:d['material_variables'].update(unused=dict(region='dielectric',path=['eps_inf'])),
])
def test_invalid_saved_inputs_fail_before_fields(monkeypatch,mutate):
    data=document().to_dict();mutate(data);monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises((ValueError,TypeError)):SampledImpedanceDesignDocument.from_dict(data)


@pytest.mark.parametrize('text',['{"schema":"x","schema":"y"}',
    '{"schema":"sipi.sampled-impedance-design/1","materials":{"a":1,"a":2}}',
    '{"schema":"sipi.sampled-impedance-design/1","frequencies_hz":[NaN,1]}',
    '{"schema":"sipi.sampled-impedance-design/1","targets_ohm":[1e999,1]}'])
def test_duplicate_and_nonfinite_json_rejected(text):
    with pytest.raises(ValueError):SampledImpedanceDesignDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


@pytest.mark.parametrize('quantity',['z_diff','z_common'])
def test_later_frequency_model_is_checked_when_first_frequency_is_valid(monkeypatch,quantity):
    model=PrincipalAxisDielectric(ConstantDielectric(4.,.5),DebyeDielectric(2.,[4.],[1e9]),.3)
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr(module,'seek_sampled_impedance',forbidden)
    with pytest.raises(ValueError,match='diagonal'):
        document(quantity=quantity,frequencies=[1e9,1e10],materials={'dielectric':model},
            variables=['width','gap'],bounds=[[.3e-3,.7e-3],[.05e-3,.2e-3]],material_variables={})


@pytest.mark.parametrize('initial',[None,[.5e-3,3*math.pi/4]])
def test_initial_material_is_checked_beyond_valid_corners(monkeypatch,initial):
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError,match='diagonal'):
        document(variables=['width','angle'],bounds=[[.3e-3,.7e-3],[math.pi/2,math.pi]],initial=initial,
            materials={'dielectric':PrincipalAxisDielectric(ConstantDielectric(2),ConstantDielectric(4),math.pi/2)},
            material_variables={'angle':dict(region='dielectric',path=['angle_rad'])})


def test_invalid_corner_material_rejected_before_mesh(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError):
        document(variables=['width','base'],bounds=[[.3e-3,.7e-3],[.5,2]],
                 material_variables={'base':dict(region='dielectric',path=['eps_inf'])})


def test_variable_order_fixed_pitch_and_model_factory_replay(monkeypatch):
    def solve(factory,bounds,frequencies,targets,**kw):
        assert bounds==[[2.,6.],[.3e-3,.7e-3]] and frequencies==F and targets==TARGET
        assert kw['quantity']=='z_common' and kw['initial']==[3.,.45e-3]
        assert 'materials' not in kw
        s=factory(3.,.45e-3);a,b=s.traces[:2]
        assert a.width==.45e-3 and b.x-a.x==pytest.approx(.8e-3,rel=1e-12)
        assert kw['material_factory'](3.,.45e-3)['dielectric'].strengths==(3.,)
        return 'checked'
    monkeypatch.setattr(module,'seek_sampled_impedance',solve)
    d=document(quantity='z_common',parameters=dict(P,gap=.3e-3),variables=['strength','width'],
        bounds=[[2.,6.],[.3e-3,.7e-3]],initial=[3.,.45e-3],fixed_pitch_m=.8e-3)
    assert SampledImpedanceDesignDocument.loads(d.dumps()).solve()=='checked'


@pytest.mark.parametrize('quantity,template',[('z0','stripline'),('z_diff','coupled_stripline')])
def test_empty_material_mapping_preserves_geometry_dielectric_variables(monkeypatch,quantity,template):
    p=dict(P,eps_r=4.)
    if template=='stripline':p.pop('gap')
    def solve(factory,bounds,frequencies,targets,**kw):
        assert kw['materials']=={} and 'material_factory' not in kw and kw['quantity']==quantity
        s=factory(.45e-3,3.);assert s.layers[0].eps_r==3. and s.traces[0].width==.45e-3
        return 'checked'
    monkeypatch.setattr(module,'seek_sampled_impedance',solve)
    d=document(template=template,quantity=quantity,parameters=p,variables=['width','eps_r'],
        bounds=[[.3e-3,.7e-3],[2.,6.]],materials={},material_variables={})
    assert d.to_dict()['materials']=={} and d.to_dict()['material_variables']=={}
    assert d.solve()=='checked'


def test_two_material_aliases_and_stack_constraint_use_existing_rules(monkeypatch):
    def solve(factory,bounds,frequencies,targets,**kw):
        assert factory(3.,2.).traces[0].width==P['width']
        m=kw['material_factory'](3.,2.)['dielectric'];assert m.eps_inf==3. and m.strengths==(2.,)
        return 'checked'
    monkeypatch.setattr(module,'seek_sampled_impedance',solve)
    d=document(variables=['base','strength'],bounds=[[1.,3.],[2.,6.]],
        material_variables=dict(BINDING,base=dict(region='dielectric',path=['eps_inf'])))
    assert d.solve()=='checked'
    p=dict(width=.5e-3,gap=.1e-3,lower_height=.4e-3,upper_height=.6e-3,
           lower_eps_r=3.,upper_eps_r=5.,box_width=8e-3)
    d=document(template='coupled_layered_stripline',parameters=p,variables=['width','lower_height'],
        bounds=[[.3e-3,.7e-3],[.3e-3,.5e-3]],materials={},material_variables={},fixed_plane_spacing_m=1e-3)
    study=module.SampledImpedanceDesignDocument._study(d.to_dict()).to_dict()
    sampled=module._parameters(study,[.45e-3,.35e-3])
    assert sampled['upper_height']==pytest.approx(.65e-3,rel=1e-12)


def test_execution_budget_diagnostics_and_batch_frequency_distinction(monkeypatch):
    d=document();monkeypatch.setattr(module,'seek_sampled_impedance',forbidden)
    with pytest.raises(ValueError,match='budget'):execute_saved(d.dumps(),max_evaluations=63)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])
    def solve(factory,bounds,frequencies,targets,**kw):
        assert len(frequencies)==64 and kw['max_evaluations']==2
        return SimpleNamespace(to_dict=lambda:dict(evaluations=2,frequency_samples=64))
    monkeypatch.setattr(module,'seek_sampled_impedance',solve)
    many=document(frequencies=list(range(64)),targets=[100.]*64,tolerances=[1.]*64,max_evaluations=2)
    assert execute_saved(many.dumps(),max_evaluations=2)['result']==dict(evaluations=2,frequency_samples=64)


def test_execution_failure_retains_frequency_quantity_and_distinct_models(monkeypatch):
    calls=[]
    def analyze(doc,value,quantity):
        calls.append(json.loads(json.dumps(value)))
        if len(calls)==2:raise ArithmeticError('failed frequency batch')
        return ('positive','negative'),[100.,100.]
    monkeypatch.setattr(api,'_analyze_sweep',analyze)
    d=document(variables=['strength','width'],bounds=[[2.,6.],[.3e-3,.7e-3]])
    out=execute_saved(d.dumps());error=out['error']
    assert out['status']=='failed' and out['result'] is None
    assert error['stage']=='search/extraction' and error['attempts']==2
    assert error['quantity']=='z_diff' and error['frequencies_hz']==F
    assert error['material_sweep']==calls[1]!=calls[0]
    assert error['history'][0]['material_sweep']==calls[0]
    assert error['history'][0]['quantity']=='z_diff' and error['input']
    json.dumps(out,allow_nan=False)


def test_real_saved_execution_matches_raw_api_and_independent_cohn():
    from test_sipi_references import coupled_stripline_z
    d=document(max_evaluations=2);data=d.to_dict()
    def geometry(w,s):return coupled_stripline(**dict(data['parameters'],width=w))
    def material(w,s):return {'dielectric':DebyeDielectric(2.,[s],[1e9])}
    direct=seek_sampled_impedance(geometry,[v['bounds'] for v in data['variables']],F,TARGET,
        tolerances=[.5,.5],quantity='z_diff',mesh=data['mesh'],material_factory=material,max_evaluations=2)
    out=execute_saved(d.dumps(),max_evaluations=2)
    assert out['status']=='complete' and out['result']==direct.to_dict()
    w,s=direct.parameters
    independent=np.array([2*coupled_stripline_z(w,.1e-3,1e-3,2+s/(1+(f/1e9)**2))[1] for f in F])
    for values in [direct.impedances,direct.refined_impedances,independent]:
        assert np.all(abs(np.array(values)-TARGET)<=.5)
    assert len(direct.history)==2
    assert all(r.quantity=='z_diff' for r in direct.history)
    print('saved frequency goal requested/refined/cohn',direct.impedances,direct.refined_impedances,independent)
