"""Finite side-ground pair forms preserve geometry and independent vacuum checks."""
from pathlib import Path
import sys

import numpy as np
import pytest
import sipi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'desktop'))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'tests/sipi'))
from engine import execute
from test_coupled_coplanar import PARAMS, COARSE, FINE, reference_modes
from sipi.template_document import TemplateSectionDocument


@pytest.fixture(scope='module')
def nominal():
    return execute(dict(action='analyze', template='coupled_grounded_coplanar', parameters=PARAMS, mesh=COARSE))


def test_factory_positions_and_vacuum_invariants(nominal):
    direct=TemplateSectionDocument('coupled_grounded_coplanar',PARAMS,mesh=COARSE)
    assert nominal['document']==direct.cross_section.to_dict()
    traces=nominal['document']['traces']
    assert [t['ground'] for t in traces]==[False,False,True,True]
    np.testing.assert_allclose([t['x'] for t in traces],[-.4e-3,.4e-3,-1.35e-3,1.35e-3],rtol=1e-15)
    line=nominal['line'];c,c0,l=[np.asarray(line[k]) for k in ['C','C0','L']]
    assert line['names']==['positive','negative'] and line['z_diff']>0 and 'z0' not in line
    np.testing.assert_allclose(c,c0,rtol=2e-12,atol=1e-23)
    np.testing.assert_allclose(l@c*299792458.0**2,np.eye(2),rtol=2e-12,atol=2e-12)
    np.testing.assert_allclose(c,c[::-1,::-1],rtol=2e-3,atol=1e-15)
    assert np.linalg.eigvalsh(c).min()>0 and c[0,1]<0


def test_independent_image_panels_mesh_and_domain_convergence(nominal):
    exact=reference_modes(160)
    fine=execute(dict(action='analyze',template='coupled_grounded_coplanar',parameters=PARAMS,mesh=FINE))['line']
    values=lambda row: np.array([row['z_even'],row['z_odd']])
    coarse_error=abs(values(nominal['line'])/exact-1);fine_error=abs(values(fine)/exact-1)
    assert np.all(fine_error<.02) and np.all(fine_error<coarse_error)
    wide=execute(dict(action='analyze',template='coupled_grounded_coplanar',
        parameters={**PARAMS,'box_width':.024,'air_height':.012},mesh=FINE))['line']
    np.testing.assert_allclose(values(wide),values(fine),rtol=.01)
    print('independent',exact,'coarse',values(nominal['line']),'fine',values(fine),'wide',values(wide))


def test_independent_target_requires_both_meshes_and_preserves_requested_mesh():
    target=2*reference_modes(160)[1]
    result=execute(dict(action='design',template='coupled_grounded_coplanar',parameters=PARAMS,mesh=FINE,
        design=dict(bounds=[.0004,.0006],target=target,tolerance=1.0)))
    goal=result['design']
    assert abs(goal['residual'])<=1.0 and abs(goal['refined_residual'])<=1.0
    assert goal['history'][-1]['stage']=='refinement' and goal['width']==pytest.approx(.0005,rel=.04)
    assert result['document']['mesh']==sipi.coupled_grounded_coplanar(**PARAMS).mesh_settings(**FINE)
    assert result['line']['z_diff']==goal['impedance']
    print('panel-derived target',target,'design',goal)


def test_four_port_lossless_power_and_reciprocity():
    result=execute(dict(action='network',template='coupled_grounded_coplanar',parameters=PARAMS,mesh=COARSE,
        network=dict(start_hz=1e6,stop_hz=1e9,points=3,length=.1,resistance=0,z_ref=50)))['network']
    assert result['ports']==['near:positive','near:negative','far:positive','far:negative']
    assert result['transmission']=='Sdd21' and result['extension']=='s4p'
    assert result['crosstalk']['next_ports']==[2,1] and result['crosstalk']['fext_ports']==[4,1]
    s=np.array(result['real'])+1j*np.array(result['imag'])
    np.testing.assert_allclose(s,s.transpose(0,2,1),rtol=0,atol=2e-12)
    for row in s:np.testing.assert_allclose(row.conj().T@row,np.eye(4),rtol=0,atol=2e-12)


@pytest.mark.parametrize('mode',['sweep','corners','monte_carlo'])
def test_ground_dimensions_in_studies_preserve_nominal_mesh(mode):
    variables=[dict(parameter='ground_gap',lower=.00018,upper=.00022)]
    if mode!='sweep':variables.append(dict(parameter='ground_width',lower=.0009,upper=.0011))
    result=execute(dict(action='study',template='coupled_grounded_coplanar',parameters=PARAMS,mesh=COARSE,
        study=dict(mode=mode,variables=variables,points=3,seed=42)))['study']
    assert result['quantity']=='z_diff' and result['failed']==0 and result['status']=='complete'
    assert len(result['rows'])==(4 if mode=='corners' else 3)
    for row in result['rows']:
        direct=TemplateSectionDocument('coupled_grounded_coplanar',{**PARAMS,**row['parameters']},mesh=COARSE)
        assert row['document']==direct.cross_section.to_dict()
        assert row['impedance']==row['line']['z_diff']


@pytest.mark.parametrize('name',['ground_gap','ground_width'])
def test_invalid_ground_study_box_is_refused_before_fields(name,monkeypatch):
    monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**k: pytest.fail('invalid box must not solve'))
    with pytest.raises(ValueError):
        execute(dict(action='study',template='coupled_grounded_coplanar',parameters=PARAMS,mesh=COARSE,
            study=dict(mode='sweep',variables=[dict(parameter=name,lower=-.0001,upper=.0002)],points=2,seed=42)))


def test_ground_fields_are_not_invented_for_other_templates(monkeypatch):
    monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**k: pytest.fail('unsupported variable must not solve'))
    with pytest.raises(ValueError,match='supported template inputs'):
        execute(dict(action='study',template='microstrip',parameters=dict(width=.0005,substrate_height=.001,eps_r=4),
            study=dict(mode='sweep',variables=[dict(parameter='ground_gap',lower=.0001,upper=.0002)],points=2,seed=42)))


def test_single_coplanar_ground_width_study_retains_single_ended_quantity():
    result=execute(dict(action='study',template='grounded_coplanar',
        parameters=dict(width=.0005,gap=.0002,ground_width=.001,substrate_height=.0005,eps_r=1),mesh=COARSE,
        study=dict(mode='sweep',variables=[dict(parameter='ground_width',lower=.0009,upper=.0011)],points=2,seed=42)))['study']
    assert result['quantity']=='z0' and result['failed']==0


@pytest.mark.parametrize('template', ['microstrip','stripline','coupled_microstrip','coupled_stripline',
    'grounded_coplanar','coated_microstrip','coupled_grounded_coplanar','offset_stripline',
    'coupled_coated_microstrip','coated_grounded_coplanar','coupled_coated_grounded_coplanar','unbacked_coplanar'])
def test_automatic_goal_mesh_policy_preserves_existing_forms(template, monkeypatch):
    from test_editable import parameters
    request=dict(action='design',template=template,parameters=parameters(template),
        design=dict(bounds=[.0004,.0006],target=100,tolerance=1))
    resolved=execute({**request,'action':'document'})['document']['mesh']
    expected=dict(resolved);expected['far_size']/=4
    if template not in ('coupled_grounded_coplanar','coupled_coated_microstrip','coated_grounded_coplanar','coupled_coated_grounded_coplanar','unbacked_coplanar'):
        expected['edge_size']/=4;expected['grade']/=2
    class StopBeforeSolve(Exception): pass
    def capture(*args, **kwargs):
        assert kwargs['mesh']==expected
        assert kwargs['tolerance']==1 and kwargs['max_evaluations']==32
        raise StopBeforeSolve
    monkeypatch.setattr(sipi,'seek_impedance',capture)
    with pytest.raises(StopBeforeSolve): execute(request)


def test_default_pair_goal_stays_within_mesh_budget_and_independent_tolerance():
    parameters={k:v for k,v in PARAMS.items() if k not in ('box_width','air_height')}
    target=2*reference_modes(160)[1]
    result=execute(dict(action='design',template='coupled_grounded_coplanar',parameters=parameters,
        design=dict(bounds=[.0004,.0006],target=target,tolerance=1)))
    goal=result['design']
    assert abs(goal['residual'])<=1 and abs(goal['refined_residual'])<=1
    assert goal['width']==pytest.approx(.0005,rel=.04) and goal['history'][-1]['stage']=='refinement'
    expected=sipi.coupled_grounded_coplanar(**parameters).mesh_settings()
    expected['far_size']/=4
    assert result['document']['mesh']==expected and result['line']['z_diff']==goal['impedance']
    print('default-domain automatic goal',goal)
