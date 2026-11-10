"""Normal film transport retains polygon geometry, references and refinement."""
from pathlib import Path
import sys
import numpy as np
import pytest
import sipi
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'desktop'),
               str(Path(__file__).resolve().parents[2]/'tests/sipi')]
from engine import execute
from normal_coplanar_cases import NAMES, COARSE, parameters
from sipi.template_document import TemplateSectionDocument
from test_conformal_coplanar import panel_modes

pytestmark = pytest.mark.parametrize('name', NAMES)


def quantity(name):
    return 'z_diff' if name == NAMES[1] else 'z0'


def reference(name, count=160):
    modes = panel_modes(name, count)
    return 2*modes[1] if name == NAMES[1] else modes[0]


@pytest.mark.parametrize('top', [None, .0004])
def test_geometry_roundtrip_keeps_normal_film_and_upper_clearance(name, top, monkeypatch):
    monkeypatch.setattr(sipi.CrossSection, 'mesh', lambda *a, **kw: pytest.fail('Document operation solved'))
    p = {**parameters(name), 'top_width': top}
    result = execute(dict(action='template-document', template=name, parameters=p, mesh=COARSE))
    assert execute(dict(action='template-open', text=result['document_text'])) == result
    doc = result['document']
    assert doc == TemplateSectionDocument(name, p, mesh=COARSE).cross_section.to_dict()
    assert doc['schema'] == 'sipi.cross-section/3'
    assert doc['box']['bottom'] == 'ground'
    grounds = [t for t in doc['traces'] if t['ground']]
    assert len(grounds) == 2 and all(t['top_width'] == t['width'] for t in grounds)
    assert len([t for t in doc['traces'] if not t['ground']]) == (2 if name == NAMES[1] else 1)
    assert 'coating_height' not in result['parameters']
    assert doc['layers'][-1]['thickness'] == p['thickness']+p['coating_thickness']+p['air_height']
    region = doc['dielectric_regions'][0]
    assert max(y for _,y in region['vertices']) == p['substrate_height']+p['thickness']+p['coating_thickness']
    assert region['eps_r'] == p['coating_eps_r'] and region['tan_delta'] == p['coating_tan_delta']


def test_auto_width_against_independent_vacuum_panels_and_outer_domain(name):
    target = reference(name)
    assert reference(name, 80) == pytest.approx(target, rel=.003)
    p = parameters(name, vacuum=True)
    out = execute(dict(action='design', template=name, parameters=p,
        design=dict(bounds=[.0004,.0006], target=float(target), tolerance=1.)))
    d = out['design']
    assert abs(d['residual']) <= 1 and abs(d['refined_residual']) <= 1
    assert d['width'] == pytest.approx(.0005, rel=.04)
    assert d['history'][-1]['stage'] == 'refinement' and out['line'][quantity(name)] == d['impedance']
    mesh = getattr(sipi,name)(**p).mesh_settings(); mesh['edge_size'] *= 10; mesh['far_size'] /= 4
    expected = TemplateSectionDocument(name, {**p, 'width':d['width']}, mesh=mesh)
    assert out['document'] == expected.cross_section.to_dict()
    outer = getattr(sipi,name)(**{**p,'width':d['width'],'box_width':.048,'air_height':.024}).analyze(**mesh)
    value = outer.even_odd()['z_diff'] if name == NAMES[1] else outer.z0
    assert value == pytest.approx(d['impedance'], rel=.01)


@pytest.mark.parametrize('explicit', [False, True])
def test_goal_policy_and_numerical_failure_preserved(name, explicit, monkeypatch):
    p = parameters(name); expected = dict(COARSE) if explicit else getattr(sipi,name)(**p).mesh_settings()
    if not explicit: expected['edge_size'] *= 10; expected['far_size'] /= 4
    sentinel = ValueError('unchanged numerical failure')
    def seek(factory, bounds, target, **kw):
        assert kw['mesh'] == expected and kw['quantity'] == quantity(name)
        assert kw['max_evaluations'] == 32 and kw['return_line'] is True
        assert len(factory(.0005).dielectric_regions) == 1
        raise sentinel
    monkeypatch.setattr(sipi, 'seek_impedance', seek)
    with pytest.raises(ValueError) as caught:
        execute(dict(action='design', template=name, parameters=p,
            **({'mesh':COARSE} if explicit else {}), design=dict(bounds=[.0004,.0006],target=100,tolerance=1)))
    assert caught.value is sentinel


@pytest.mark.parametrize('mode', ['sweep','corners','monte_carlo'])
def test_normal_thickness_studies_preserve_material_and_fixed_mesh(name, mode):
    p=parameters(name);variables=[dict(parameter='coating_thickness',lower=.000018,upper=.000022)]
    if mode != 'sweep': variables.append(dict(parameter='coating_eps_r',lower=3.2,upper=3.8))
    study=execute(dict(action='study',template=name,parameters=p,mesh=COARSE,
        study=dict(mode=mode,variables=variables,points=2,seed=42)))['study']
    assert study['failed']==0 and study['status']=='complete' and study['quantity']==quantity(name)
    assert len(study['rows'])==(4 if mode=='corners' else 2)
    for row in study['rows']:
        direct=TemplateSectionDocument(name,{**p,**row['parameters']},mesh=COARSE)
        assert row['document']==direct.cross_section.to_dict() and row['impedance']==row['line'][quantity(name)]


@pytest.mark.parametrize('change', [{'coating_thickness':0}, {'coating_eps_r':0},
    {'coating_tan_delta':-1}, {'top_width':.0006}, {'box_width':.00051}])
def test_invalid_film_refused_before_solve(name, change, monkeypatch):
    monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Invalid geometry solved'))
    with pytest.raises(ValueError): execute(dict(action='analyze',template=name,parameters={**parameters(name),**change}))


def test_invalid_film_study_bound_refused_before_solve(name, monkeypatch):
    monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Invalid bound solved'))
    with pytest.raises(ValueError): execute(dict(action='study',template=name,parameters=parameters(name),mesh=COARSE,
        study=dict(mode='sweep',variables=[dict(parameter='coating_thickness',lower=0,upper=.000022)],points=2,seed=42)))


def test_vacuum_network_tem_reciprocity_and_power(name):
    out=execute(dict(action='network',template=name,parameters=parameters(name,vacuum=True),mesh=COARSE,
        network=dict(start_hz=1e6,stop_hz=1e9,points=3,length=.1,resistance=0,z_ref=50)))
    line,net=out['line'],out['network'];n=2 if name==NAMES[1] else 1
    np.testing.assert_allclose(line['C'],line['C0'],rtol=2e-12,atol=1e-23)
    np.testing.assert_allclose(np.array(line['L'])@line['C']*299792458.**2,np.eye(n),rtol=2e-12,atol=2e-12)
    assert net['extension']==f's{2*n}p'
    values=np.array(net['real'])+1j*np.array(net['imag'])
    np.testing.assert_allclose(values,values.transpose(0,2,1),rtol=0,atol=2e-12)
    for s in values: np.testing.assert_allclose(s.conj().T@s,np.eye(2*n),rtol=0,atol=2e-12)


def test_finite_film_auto_goal_retains_reference_mesh_and_outer_gates(name):
    p = {**parameters(name), 'top_width': None}
    target = 100 if name == NAMES[1] else 60
    out = execute(dict(action='design', template=name, parameters=p,
        design=dict(bounds=[.0002,.0012], target=target, tolerance=1.)))
    goal = out['design']
    assert abs(goal['residual']) <= 1 and abs(goal['refined_residual']) <= 1
    assert abs(goal['mesh_change']/goal['impedance']) < .01
    factory = getattr(sipi, name)
    selected = {**p, 'width': goal['width']}
    # Separately specified mesh from the existing normal-film convergence suite.
    fine = dict(edge_size=1e-6, far_size=.000125, grade=.1)
    reference_line = factory(**selected).analyze(**fine)
    reference_value = reference_line.even_odd()['z_diff'] if name == NAMES[1] else reference_line.z0
    assert reference_value == pytest.approx(goal['impedance'], rel=.01)
    outer = factory(**{**selected, 'box_width': .024, 'air_height': .012}).analyze(**out['document']['mesh'])
    outer_value = outer.even_odd()['z_diff'] if name == NAMES[1] else outer.z0
    assert outer_value == pytest.approx(goal['impedance'], rel=.01)
