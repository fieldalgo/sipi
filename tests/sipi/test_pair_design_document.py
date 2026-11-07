# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Named two-target JSON, constraint replay and execution failure context."""
import json

import numpy as np
import pytest

from sipi import (CrossSection, CrossSectionDocument, PairImpedanceDesignDocument,
                  PairImpedanceGoalError, PairImpedanceEvaluation, coupled_grounded_coplanar)
from sipi.dielectric import ConstantDielectric, PrincipalAxisDielectric
from sipi.execution import normalize_saved, execute_saved, saved_schemas
import sipi.pair_design_document as module

PARAMETERS=dict(width=.5e-3,gap=.3e-3,ground_gap=.2e-3,ground_width=1e-3,
    substrate_height=.5e-3,eps_r=1.,box_width=12e-3,air_height=6e-3)
MESH=dict(edge_size=2e-6,far_size=.125e-3,grade=.15)
TARGETS=dict(z_diff=172.45677879183611,z_common=65.9597000672247)
TOLERANCES=dict(z_diff=1.5,z_common=.5)


def document(**changes):
    args=dict(template='coupled_grounded_coplanar',parameters=PARAMETERS,
        variables=['width','gap'],bounds=[[.3e-3,.7e-3],[.1e-3,.5e-3]],targets=TARGETS,
        tolerances=TOLERANCES,mesh=MESH,max_evaluations=64)
    args.update(changes)
    return PairImpedanceDesignDocument(**args)


def test_canonical_replay_isolation_and_no_fields_or_optimizer(monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('normalization performed computation')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr(module,'seek_pair_impedances',forbidden)
    parameters=dict(PARAMETERS);targets=dict(TARGETS);bounds=[[.3e-3,.7e-3],[.1e-3,.5e-3]]
    d=document(parameters=parameters,targets=targets,bounds=bounds,initial=[.4e-3,.4e-3])
    text=d.dumps();assert normalize_saved(text)==text
    assert PairImpedanceDesignDocument.loads(text).dumps()==text
    parameters['width']=1;targets['z_diff']=1;bounds[0][0]=1
    data=d.to_dict();data['variables'][0]['bounds'][0]=1
    assert d.dumps()==text and d.to_dict()['schema'] in saved_schemas()


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.pair-impedance-design/2'),
    lambda d:d.update(extra=1),lambda d:d.pop('initial'),
    lambda d:d.update(variables=[]),lambda d:d['variables'][1].update(name='width'),
    lambda d:d['variables'][0].update(name=''),lambda d:d['variables'][0].update(name='unknown'),
    lambda d:d['variables'][0].update(bounds=[0,.7e-3]),
    lambda d:d['variables'][0].update(bounds=[.7e-3,.3e-3]),
    lambda d:d['variables'][0].update(bounds=[True,.7e-3]),
    lambda d:d['variables'][0].update(bounds=[.3e-3]),
    lambda d:d['variables'][0].update(extra=1),
    lambda d:d['targets_ohm'].update(z_diff=0),lambda d:d['targets_ohm'].update(z_common=True),
    lambda d:d['targets_ohm'].update(z0=50),lambda d:d['targets_ohm'].pop('z_common'),
    lambda d:d.update(targets_ohm=[100,40]),lambda d:d['tolerances_ohm'].update(z_diff=-1),
    lambda d:d.update(initial=[.2e-3,.3e-3]),lambda d:d.update(initial=[.5e-3]),
    lambda d:d.update(initial=[False,.3e-3]),lambda d:d.update(max_evaluations=1),
    lambda d:d.update(max_evaluations=True),lambda d:d.update(max_evaluations=10001),
    lambda d:d.update(mesh={'invalid':1}),lambda d:d.update(fixed_pitch_m=.8e-3),
    lambda d:d.update(fixed_plane_spacing_m=1e-3),lambda d:d.update(material_evaluation={}),
    lambda d:d.update(material_evaluation={'frequency_hz':1e9,'materials':[]}),
    lambda d:d['parameters'].update(box_width=.1e-3),
    lambda d:d['variables'][1].update(bounds=[.1e-3,50e-3]),
])
def test_invalid_saved_controls_before_fields(mutate,monkeypatch):
    data=document().to_dict();mutate(data)
    def forbidden(*args,**kwargs):pytest.fail('invalid saved input meshed')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises((ValueError,TypeError)):PairImpedanceDesignDocument.from_dict(data)


@pytest.mark.parametrize('text',['{"schema":"x","schema":"y"}',
    '{"schema":"sipi.pair-impedance-design/1","targets_ohm":{"z_diff":1,"z_diff":2}}',
    '{"schema":"sipi.pair-impedance-design/1","initial":[NaN,1]}',
    '{"schema":"sipi.pair-impedance-design/1","initial":[1e999,1]}'])
def test_duplicate_and_nonfinite_json_rejected(text):
    with pytest.raises(ValueError):PairImpedanceDesignDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


@pytest.mark.parametrize('variables,bounds',[(['width'],[[1,2]]),(['width','gap'],[[1,2]]),
    ('width',[[1,2],[3,4]])])
def test_constructor_requires_exactly_two_variables_and_bounds(variables,bounds):
    with pytest.raises(ValueError):document(variables=variables,bounds=bounds)


def test_explicit_quantity_keys_and_variable_order_are_preserved(monkeypatch):
    sentinel=object()
    def solve(factory,bounds,targets,**kw):
        assert bounds==[[.1e-3,.5e-3],[.3e-3,.7e-3]]
        assert targets==[TARGETS['z_diff'],TARGETS['z_common']]
        assert kw['tolerances']==[1.5,.5] and kw['initial']==[.2e-3,.6e-3]
        s=factory(.2e-3,.6e-3);a,b=s.traces[:2]
        assert a.width==.6e-3 and b.x0-a.x1==pytest.approx(.2e-3,rel=1e-12)
        return sentinel
    monkeypatch.setattr(module,'seek_pair_impedances',solve)
    out=document(variables=['gap','width'],bounds=[[.1e-3,.5e-3],[.3e-3,.7e-3]],
        targets={'z_common':TARGETS['z_common'],'z_diff':TARGETS['z_diff']},initial=[.2e-3,.6e-3]).solve()
    assert out is sentinel


def test_pitch_and_total_plane_spacing_compose_without_independent_derived_variables(monkeypatch):
    p=dict(width=.5e-3,gap=.3e-3,lower_height=.4e-3,upper_height=.6e-3,
        lower_eps_r=3.,upper_eps_r=5.,box_width=10e-3)
    d=document(template='coupled_layered_stripline',parameters=p,variables=['width','lower_height'],
        bounds=[[.4e-3,.6e-3],[.3e-3,.5e-3]],fixed_pitch_m=.8e-3,fixed_plane_spacing_m=1e-3)
    def solve(factory,bounds,targets,**kw):
        s=factory(.45e-3,.35e-3);a,b=s.traces[:2]
        assert a.width==.45e-3
        assert b.x-a.x==pytest.approx(.8e-3,rel=1e-12)
        assert s.layers[0].thickness==.35e-3
        assert s.layers[1].thickness==pytest.approx(.65e-3,rel=1e-12)
        return 'verified'
    monkeypatch.setattr(module,'seek_pair_impedances',solve)
    assert PairImpedanceDesignDocument.loads(d.dumps()).solve()=='verified'


def test_fixed_material_snapshot_and_tilted_override_preflight(monkeypatch):
    d=document(frequency=1e9,materials={'substrate':ConstantDielectric(4.,.02)})
    def solve(factory,bounds,targets,**kw):
        assert kw['frequency']==1e9
        assert kw['materials']['substrate'].permittivity(1e9)==4*(1-.02j)
        return 'verified'
    monkeypatch.setattr(module,'seek_pair_impedances',solve)
    assert PairImpedanceDesignDocument.loads(d.dumps()).solve()=='verified'
    with pytest.raises(ValueError,match='diagonal'):
        document(frequency=1e9,materials={'substrate':PrincipalAxisDielectric(
            ConstantDielectric(2),ConstantDielectric(4),30.)})


def test_execution_budget_and_diagnostics_fail_before_solving(monkeypatch):
    d=document()
    def forbidden(*args,**kwargs):pytest.fail('invalid execution controls solved')
    monkeypatch.setattr(PairImpedanceDesignDocument,'solve',forbidden)
    with pytest.raises(ValueError,match='budget'):execute_saved(d.dumps(),max_evaluations=63)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])


def test_execution_failure_retains_history_geometry_and_material(monkeypatch):
    d=document(frequency=1e9,materials={'substrate':ConstantDielectric(4.,.02)})
    text=CrossSectionDocument(coupled_grounded_coplanar(**PARAMETERS),mesh=MESH).dumps()
    row=PairImpedanceEvaluation((.5e-3,.3e-3),(100.,40.),'search',text)
    material=json.dumps(d.to_dict()['material_evaluation'])
    def fail(self):
        raise PairImpedanceGoalError('refinement failed',[row],attempts=2,
            stage='refinement/extraction',failed_parameters=(.5e-3,.3e-3),cause_type='ArithmeticError',
            input_json=text,material_evaluation_json=material)
    monkeypatch.setattr(PairImpedanceDesignDocument,'solve',fail)
    out=execute_saved(d.dumps());error=out['error']
    assert out['status']=='failed' and out['result'] is None
    assert error['attempts']==2 and error['stage']=='refinement/extraction'
    assert error['history']==[row.to_dict()] and error['input']==json.loads(text)
    assert error['material_evaluation']==json.loads(material)
    assert error['quantities']==['z_diff','z_common'] and error['unit']=='ohm'
    json.dumps(out,allow_nan=False)


def test_real_saved_execution_matches_direct_api_and_independent_panels():
    from scipy.constants import c
    from test_coupled_coplanar import panel_reference
    d=document(max_evaluations=2)
    direct=d.solve();out=execute_saved(d.dumps(),max_evaluations=2)
    assert out['status']=='complete' and out['result']==direct.to_dict()
    assert len(direct.history)==2 and direct.history[-1].stage=='refinement'
    w,g=direct.parameters;gg=.2e-3;gw=1e-3
    intervals=[(-g/2-w,-g/2),(g/2,g/2+w),(-g/2-w-gg-gw,-g/2-w-gg),(g/2+w+gg,g/2+w+gg+gw)]
    cap=panel_reference(intervals,.5e-3,160)[:2,:2]
    independent=[2/(c*(cap[0,0]-cap[0,1])),.5/(c*(cap[0,0]+cap[0,1]))]
    for values in (direct.impedances,direct.refined_impedances,independent):
        assert np.all(abs(np.array(values)-[TARGETS['z_diff'],TARGETS['z_common']])<=[1.5,.5])
    print('saved pair requested/refined/reference',direct.impedances,direct.refined_impedances,independent)
