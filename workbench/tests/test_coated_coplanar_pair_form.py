"""Planar-coated coplanar pair transport retains qualified geometry and numerical gates."""
from pathlib import Path
import sys
import numpy as np
import pytest
import sipi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'desktop'))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'tests/sipi'))
from engine import execute
from test_coated_coplanar import params, reference, COARSE, VAC_FINE
VACUUM=params(sipi.coupled_coated_grounded_coplanar)
PHYSICAL=params(sipi.coupled_coated_grounded_coplanar,True)
VACUUM_FINE=VAC_FINE
from sipi.template_document import TemplateSectionDocument


@pytest.mark.parametrize('taper', [None, .4e-3])
def test_coating_parameters_mesh_and_editable_roundtrip_without_solving(taper, monkeypatch):
    monkeypatch.setattr(sipi.CrossSection, 'mesh', lambda *a, **kw: pytest.fail('Document operation solved'))
    parameters={**PHYSICAL, 'top_width':taper, 'coating_height':.0001000000000123456}
    result=execute(dict(action='template-document',template='coupled_coated_grounded_coplanar',parameters=parameters,mesh=COARSE))
    assert execute(dict(action='template-open',text=result['document_text']))==result
    assert result['parameters']==TemplateSectionDocument('coupled_coated_grounded_coplanar',parameters,mesh=COARSE).parameters
    edited=execute(dict(action='template-document',template='coupled_coated_grounded_coplanar',parameters={**parameters,'width':.55e-3},mesh=COARSE))
    assert edited['document']['mesh']==result['document']['mesh']
    assert edited['parameters']['coating_height']==parameters['coating_height']
    assert edited['document']['layers'][1]['thickness']==parameters['coating_height']


@pytest.mark.parametrize('explicit_mesh',[False,True],ids=['automatic','fixed'])
def test_independent_width_target_preserves_coating_and_both_residuals(explicit_mesh):
    target=2*reference(sipi.coupled_coated_grounded_coplanar,160)[1]
    result=execute(dict(action='design',template='coupled_coated_grounded_coplanar',parameters=VACUUM,
        **({'mesh':VACUUM_FINE} if explicit_mesh else {}),design=dict(bounds=[.4e-3,.6e-3],target=target,tolerance=1.)))
    goal=result['design']
    assert abs(goal['residual'])<=1 and abs(goal['refined_residual'])<=1
    assert goal['width']==pytest.approx(.5e-3,rel=.04) and goal['history'][-1]['stage']=='refinement'
    assert result['line']['z_diff']==goal['impedance']
    expected=TemplateSectionDocument('coupled_coated_grounded_coplanar',{**VACUUM,'width':goal['width']},mesh=result['document']['mesh'])
    assert result['document']==expected.cross_section.to_dict()
    if explicit_mesh:assert result['document']['mesh']==sipi.coupled_coated_grounded_coplanar(**VACUUM).mesh_settings(**VACUUM_FINE)


@pytest.mark.parametrize('mode',['sweep','corners','monte_carlo'])
def test_coating_study_preserves_geometry_and_frozen_nominal_mesh(mode):
    variables=[dict(parameter='coating_height',lower=.09e-3,upper=.11e-3)]
    if mode!='sweep':variables.append(dict(parameter='coating_eps_r',lower=3.2,upper=3.8))
    result=execute(dict(action='study',template='coupled_coated_grounded_coplanar',parameters=PHYSICAL,mesh=COARSE,
        study=dict(mode=mode,variables=variables,points=3,seed=42)))['study']
    assert result['failed']==0 and result['status']=='complete' and result['quantity']=='z_diff'
    assert len(result['rows'])==(4 if mode=='corners' else 3)
    for row in result['rows']:
        expected=TemplateSectionDocument('coupled_coated_grounded_coplanar',{**PHYSICAL,**row['parameters']},mesh=COARSE)
        assert row['document']==expected.cross_section.to_dict()
        assert row['impedance']==row['line']['z_diff']
        assert row['document']['layers'][1]['tan_delta']==PHYSICAL['coating_tan_delta']


@pytest.mark.parametrize('lower,upper',[(0.,.1e-3),(.035e-3,.1e-3),(.03e-3,.04e-3)])
def test_coating_clearance_bounds_rejected_before_fields(lower,upper,monkeypatch):
    monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Invalid bounds solved'))
    with pytest.raises(ValueError):
        execute(dict(action='study',template='coupled_coated_grounded_coplanar',parameters=PHYSICAL,mesh=COARSE,
            study=dict(mode='sweep',variables=[dict(parameter='coating_height',lower=lower,upper=upper)],points=2,seed=42)))


def test_four_port_lossless_reciprocity_power_and_uniform_vacuum_tem():
    settings=dict(start_hz=1e6,stop_hz=1e9,points=5,length=.1,resistance=0,z_ref=50)
    result=execute(dict(action='network',template='coupled_coated_grounded_coplanar',parameters=VACUUM,
        mesh=dict(edge_size=4e-6,far_size=.5e-3,grade=.2),network=settings))
    line,network=result['line'],result['network']
    np.testing.assert_allclose(line['C'],line['C0'],rtol=2e-12,atol=1e-23)
    np.testing.assert_allclose(np.array(line['L'])@line['C']*299792458.0**2,np.eye(2),rtol=2e-12,atol=2e-12)
    assert network['extension']=='s4p' and network['transmission']=='Sdd21' and len(network['ports'])==4
    assert 'mixed' in network and 'crosstalk' in network
    values=np.array(network['real'])+1j*np.array(network['imag'])
    np.testing.assert_allclose(values,values.transpose(0,2,1),rtol=0,atol=2e-12)
    for value in values:np.testing.assert_allclose(value.conj().T@value,np.eye(4),rtol=0,atol=2e-12)


@pytest.mark.parametrize('parameter,lower,upper',[('gap',.25e-3,.35e-3),('ground_gap',.15e-3,.25e-3),('ground_width',.8e-3,1.2e-3)])
def test_finite_ground_studies_retain_rectangular_ground_geometry(parameter,lower,upper):
    result=execute(dict(action='study',template='coupled_coated_grounded_coplanar',parameters=PHYSICAL,mesh=COARSE,
        study=dict(mode='sweep',variables=[dict(parameter=parameter,lower=lower,upper=upper)],points=2,seed=42)))['study']
    assert result['failed']==0 and result['quantity']=='z_diff'
    for row in result['rows']:
        doc=TemplateSectionDocument('coupled_coated_grounded_coplanar',{**PHYSICAL,**row['parameters']},mesh=COARSE)
        assert row['document']==doc.cross_section.to_dict()
        signals=[t for t in doc.section.traces if not t.ground]
        grounds=[t for t in doc.section.traces if t.ground]
        assert len(signals)==len(grounds)==2
        assert signals[1].x0-signals[0].x1==pytest.approx(doc.parameters['gap'],rel=1e-12)
        assert all(t.ground and not t.tapered and t.top_width == t.width for t in grounds)
        assert grounds[1].x0-signals[1].x1==pytest.approx(doc.parameters['ground_gap'],rel=1e-12)
        assert all(t.width==doc.parameters['ground_width'] for t in grounds)


@pytest.mark.parametrize('parameter,lower',[('gap',0.),('ground_gap',0.),('ground_width',0.)])
def test_invalid_ground_bounds_reject_before_any_field(parameter,lower,monkeypatch):
    monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Invalid ground bounds solved'))
    with pytest.raises(ValueError):
        execute(dict(action='study',template='coupled_coated_grounded_coplanar',parameters=PHYSICAL,mesh=COARSE,
            study=dict(mode='sweep',variables=[dict(parameter=parameter,lower=lower,upper=.3e-3)],points=2,seed=42)))
