"""Planar films over finite-ground unbacked single and equal-pair sections."""
from pathlib import Path
import sys
import numpy as np
import pytest
import sipi
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests/sipi'))
from engine import execute
from test_coated_unbacked import FACTORIES, params, reference, COARSE, VAC_FINE
from sipi.template_document import TemplateSectionDocument

pytestmark=pytest.mark.parametrize('factory',FACTORIES,ids=[f.__name__ for f in FACTORIES])

def quantity(factory):
    return 'z_diff' if factory is sipi.coupled_coated_unbacked_coplanar else 'z0'

@pytest.mark.parametrize('lower',[None,.006000000000123456])
def test_precise_film_and_open_domain_roundtrip_without_solving(factory,lower,monkeypatch):
    monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Document operation solved'))
    p={**params(factory,True),'lower_air_height':lower}
    out=execute(dict(action='template-document',template=factory.__name__,parameters=p,mesh=COARSE))
    assert execute(dict(action='template-open',text=out['document_text']))==out
    doc=out['document'];resolved=.005 if lower is None else lower
    assert doc['box']['bottom']==doc['box']['top']==doc['box']['sides']=='open'
    assert [x['name'] for x in doc['layers']]==['lower_air','substrate','coating','air']
    assert doc['layers'][0]['thickness']==resolved
    assert doc['layers'][2]['thickness']==p['coating_height']
    assert doc['layers'][-1]['thickness']==p['air_height']
    assert all(t['y']==resolved+p['substrate_height'] for t in doc['traces'])
    edit=execute(dict(action='template-document',template=factory.__name__,parameters={**p,'width':.55e-3},mesh=COARSE))
    for key in ['lower_air_height','coating_height','coating_eps_r','coating_tan_delta']:
        assert edit['parameters'][key]==p[key]
    assert edit['document']['mesh']==doc['mesh']


def test_automatic_width_goal_against_independent_free_space_reference(factory):
    p=params(factory);paired=quantity(factory)=='z_diff'
    target=float(2*reference(factory)[1] if paired else reference(factory)[0])
    result=execute(dict(action='design',template=factory.__name__,parameters=p,
        design=dict(bounds=[.4e-3,.6e-3],target=target,tolerance=1.)))
    goal=result['design']
    assert abs(goal['residual'])<=1 and abs(goal['refined_residual'])<=1
    assert goal['width']==pytest.approx(.5e-3,rel=.04) and goal['history'][-1]['stage']=='refinement'
    assert result['line'][quantity(factory)]==goal['impedance']
    mesh=factory(**p).mesh_settings();mesh['far_size']/=4
    expected=TemplateSectionDocument(factory.__name__,{**p,'width':goal['width']},mesh=mesh)
    assert result['document']==expected.cross_section.to_dict()
    assert abs(goal['refined_impedance']/target-1)<abs(goal['impedance']/target-1)<.02
    outer=factory(**{**p,'width':goal['width'],'air_height':.024,
        'lower_air_height':.024,'box_width':.048}).analyze(**mesh)
    value=2*outer.even_odd()['z_odd'] if paired else outer.z0
    assert value==pytest.approx(goal['impedance'],rel=.01)


@pytest.mark.parametrize('explicit',[False,True])
def test_explicit_and_automatic_mesh_transport_preserves_existing_failure(factory,explicit,monkeypatch):
    p=params(factory);expected=dict(VAC_FINE) if explicit else factory(**p).mesh_settings()
    if not explicit:expected['far_size']/=4
    sentinel=ValueError('unchanged numerical failure')
    def seek(make,bounds,target,**kw):
        assert kw['mesh']==expected and kw['max_evaluations']==32 and kw['return_line'] is True
        assert kw['quantity']==quantity(factory)
        assert make(.5e-3).bottom=='open'
        raise sentinel
    monkeypatch.setattr(sipi,'seek_impedance',seek)
    with pytest.raises(ValueError) as caught:
        execute(dict(action='design',template=factory.__name__,parameters=p,
            **({'mesh':VAC_FINE} if explicit else {}),design=dict(bounds=[.4e-3,.6e-3],target=100,tolerance=1)))
    assert caught.value is sentinel


@pytest.mark.parametrize('mode',['sweep','corners','monte_carlo'])
def test_coating_studies_keep_domain_grounds_and_nominal_mesh(factory,mode):
    p=params(factory,True)
    variables=[dict(parameter='coating_height',lower=.09e-3,upper=.11e-3)]
    if mode!='sweep':variables.append(dict(parameter='coating_eps_r',lower=3.2,upper=3.8))
    result=execute(dict(action='study',template=factory.__name__,parameters=p,mesh=COARSE,
        study=dict(mode=mode,variables=variables,points=2,seed=42)))['study']
    assert result['failed']==0 and result['status']=='complete' and result['quantity']==quantity(factory)
    assert len(result['rows'])==(4 if mode=='corners' else 2)
    for row in result['rows']:
        direct=TemplateSectionDocument(factory.__name__,{**p,**row['parameters']},mesh=COARSE)
        assert row['document']==direct.cross_section.to_dict() and row['impedance']==row['line'][quantity(factory)]
        signals=[t for t in direct.section.traces if not t.ground];grounds=[t for t in direct.section.traces if t.ground]
        assert len(grounds)==2 and all(not t.tapered for t in grounds)
        clearance=p['ground_gap'] if len(signals)==2 else p['gap']
        assert grounds[1].x0-signals[-1].x1==pytest.approx(clearance,rel=1e-12)
        assert direct.section.bottom=='open' and direct.section.layers[0].thickness==p['lower_air_height']


@pytest.mark.parametrize('parameter',['gap','ground_width','lower_air_height','coating_height','coating_eps_r'])
def test_invalid_dimensions_rejected_before_mesh(factory,parameter,monkeypatch):
    monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Invalid geometry solved'))
    with pytest.raises(ValueError):execute(dict(action='analyze',template=factory.__name__,
        parameters={**params(factory,True),parameter:0},mesh=COARSE))


def test_coating_corner_touching_copper_is_rejected_before_mesh(factory,monkeypatch):
    monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Invalid bound solved'))
    p=params(factory,True)
    with pytest.raises(ValueError):execute(dict(action='study',template=factory.__name__,parameters=p,mesh=COARSE,
        study=dict(mode='corners',variables=[dict(parameter='coating_height',lower=p['thickness'],upper=.12e-3)],points=2,seed=42)))


def test_vacuum_network_reciprocity_power_and_tem_invariant(factory):
    result=execute(dict(action='network',template=factory.__name__,parameters=params(factory),
        mesh=dict(edge_size=4e-6,far_size=.5e-3,grade=.2),
        network=dict(start_hz=1e6,stop_hz=1e9,points=3,length=.1,resistance=0,z_ref=50)))
    line,network=result['line'],result['network'];n=2 if quantity(factory)=='z_diff' else 1
    np.testing.assert_allclose(line['C'],line['C0'],rtol=2e-12,atol=1e-23)
    np.testing.assert_allclose(np.array(line['L'])@line['C']*299792458.0**2,np.eye(n),rtol=2e-12,atol=2e-12)
    assert network['extension']==('s4p' if n==2 else 's2p')
    assert network['transmission']==('Sdd21' if n==2 else 'S21') and len(network['ports'])==2*n
    values=np.array(network['real'])+1j*np.array(network['imag'])
    np.testing.assert_allclose(values,values.transpose(0,2,1),rtol=0,atol=2e-12)
    for value in values:np.testing.assert_allclose(value.conj().T@value,np.eye(2*n),rtol=0,atol=2e-12)
