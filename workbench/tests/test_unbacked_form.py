"""Unbacked single-line adapter: finite side grounds and explicit open domain."""
from pathlib import Path
import sys
import numpy as np
import pytest
import sipi
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests/sipi'))
from engine import execute
from test_unbacked_coplanar import params, reference, COARSE, VAC_FINE
from sipi.template_document import TemplateSectionDocument
VACUUM=params(sipi.unbacked_coplanar)
PHYSICAL=params(sipi.unbacked_coplanar,True)

@pytest.mark.parametrize('lower',[None,.006000000000123456])
def test_open_domain_editable_roundtrip_without_solving(lower,monkeypatch):
    monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Document operation solved'))
    p={**PHYSICAL,'lower_air_height':lower}
    result=execute(dict(action='template-document',template='unbacked_coplanar',parameters=p,mesh=COARSE))
    assert execute(dict(action='template-open',text=result['document_text']))==result
    doc=result['document'];resolved=.005 if lower is None else lower
    assert doc['box']['bottom']==doc['box']['top']==doc['box']['sides']=='open'
    assert [x['name'] for x in doc['layers']]==['lower_air','substrate','air']
    assert doc['layers'][0]['thickness']==resolved
    assert all(t['y']==resolved+PHYSICAL['substrate_height'] for t in doc['traces'])
    edit=execute(dict(action='template-document',template='unbacked_coplanar',parameters={**p,'width':.55e-3},mesh=COARSE))
    assert edit['parameters']['lower_air_height']==lower
    assert edit['document']['mesh']==doc['mesh']


@pytest.mark.parametrize('explicit_mesh',[False,True],ids=['automatic','fixed'])
def test_width_goal_against_independent_free_space_reference(explicit_mesh):
    target=float(reference(sipi.unbacked_coplanar)[0])
    result=execute(dict(action='design',template='unbacked_coplanar',parameters=VACUUM,**({'mesh':VAC_FINE} if explicit_mesh else {}),
        design=dict(bounds=[.4e-3,.6e-3],target=target,tolerance=1.)))
    goal=result['design']
    assert abs(goal['residual'])<=1 and abs(goal['refined_residual'])<=1
    assert goal['width']==pytest.approx(.5e-3,rel=.04) and goal['history'][-1]['stage']=='refinement'
    assert result['line']['z0']==goal['impedance']
    mesh=VAC_FINE if explicit_mesh else sipi.unbacked_coplanar(**VACUUM).mesh_settings()
    if not explicit_mesh:mesh['far_size']/=4
    expected=TemplateSectionDocument('unbacked_coplanar',{**VACUUM,'width':goal['width']},mesh=mesh)
    assert result['document']==expected.cross_section.to_dict()
    if not explicit_mesh:
        assert abs(goal['refined_impedance']/target-1)<abs(goal['impedance']/target-1)<.02
        outer=sipi.unbacked_coplanar(**{**VACUUM,'width':goal['width'],
            'air_height':.024,'lower_air_height':.024,'box_width':.048}).analyze(**mesh)
        assert outer.z0==pytest.approx(goal['impedance'],rel=.01)


def test_automatic_mesh_and_existing_failure_are_forwarded_without_relaxing(monkeypatch):
    section=sipi.unbacked_coplanar(**VACUUM);expected=section.mesh_settings()
    expected['far_size']/=4
    sentinel=ValueError('unchanged numerical failure')
    def seek(factory,bounds,target,**kw):
        assert kw['mesh']==expected and kw['max_evaluations']==32 and kw['return_line'] is True
        assert kw['quantity']=='z0'
        assert factory(.5e-3).bottom=='open'
        raise sentinel
    monkeypatch.setattr(sipi,'seek_impedance',seek)
    with pytest.raises(ValueError) as caught:
        execute(dict(action='design',template='unbacked_coplanar',parameters=VACUUM,design=dict(bounds=[.4e-3,.6e-3],target=100,tolerance=1)))
    assert caught.value is sentinel

@pytest.mark.parametrize('mode',['sweep','corners','monte_carlo'])
def test_gap_ground_studies_freeze_mesh_and_keep_open_domain(mode):
    variables=[dict(parameter='gap',lower=.18e-3,upper=.22e-3)]
    if mode!='sweep':variables.append(dict(parameter='ground_width',lower=.9e-3,upper=1.1e-3))
    result=execute(dict(action='study',template='unbacked_coplanar',parameters=PHYSICAL,mesh=COARSE,
        study=dict(mode=mode,variables=variables,points=2,seed=42)))['study']
    assert result['failed']==0 and result['status']=='complete' and result['quantity']=='z0'
    assert len(result['rows'])==(4 if mode=='corners' else 2)
    for row in result['rows']:
        doc=TemplateSectionDocument('unbacked_coplanar',{**PHYSICAL,**row['parameters']},mesh=COARSE)
        assert row['document']==doc.cross_section.to_dict() and row['impedance']==row['line']['z0']
        signal,*grounds=doc.section.traces
        assert all(t.ground and not t.tapered for t in grounds)
        assert grounds[1].x0-signal.x1==pytest.approx(doc.parameters['gap'],rel=1e-12)
        assert doc.section.bottom=='open' and doc.section.layers[0].thickness==PHYSICAL['lower_air_height']

@pytest.mark.parametrize('parameter',['gap','ground_width','lower_air_height'])
def test_invalid_dimensions_rejected_before_any_mesh(parameter,monkeypatch):
    monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Invalid geometry solved'))
    with pytest.raises(ValueError):
        execute(dict(action='analyze',template='unbacked_coplanar',parameters={**PHYSICAL,parameter:0},mesh=COARSE))


def test_vacuum_network_reciprocity_power_and_tem_invariant():
    result=execute(dict(action='network',template='unbacked_coplanar',parameters=VACUUM,
        mesh=dict(edge_size=4e-6,far_size=.5e-3,grade=.2),
        network=dict(start_hz=1e6,stop_hz=1e9,points=3,length=.1,resistance=0,z_ref=50)))
    line,network=result['line'],result['network']
    np.testing.assert_allclose(line['C'],line['C0'],rtol=2e-12,atol=1e-23)
    np.testing.assert_allclose(np.array(line['L'])@line['C']*299792458.0**2,np.eye(1),rtol=2e-12,atol=2e-12)
    assert network['extension']=='s2p' and network['transmission']=='S21' and len(network['ports'])==2
    values=np.array(network['real'])+1j*np.array(network['imag'])
    np.testing.assert_allclose(values,values.transpose(0,2,1),rtol=0,atol=2e-12)
    for value in values:np.testing.assert_allclose(value.conj().T@value,np.eye(2),rtol=0,atol=2e-12)
