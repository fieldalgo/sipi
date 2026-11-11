"""Explicit domain bounds reuse the template contract without solving fields."""
from pathlib import Path
import sys

import pytest
import sipi

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from engine import execute, TEMPLATES
from test_editable import parameters


@pytest.fixture(autouse=True)
def forbid_field_solve(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Inspecting and saving domain bounds must not solve fields')
    monkeypatch.setattr(sipi.CrossSection, 'mesh', forbidden)
    monkeypatch.setattr(sipi.CrossSection, 'analyze', forbidden)


@pytest.mark.parametrize('template', TEMPLATES)
@pytest.mark.parametrize('mode', ['omitted', 'null', 'fixed'])
def test_domain_inspect_and_editable_roundtrip_preserve_parameters_and_mesh(template, mode):
    p=parameters(template)
    keys=['box_width']+([] if template in ('layered_coplanar_stripline','coupled_layered_coplanar_stripline','layered_stripline','coupled_layered_stripline','broadside_stripline','stripline','coupled_stripline','offset_stripline','coplanar_stripline','coupled_coplanar_stripline') else ['air_height'])
    if template in ('unbacked_coplanar', 'coupled_unbacked_coplanar', 'coated_unbacked_coplanar', 'coupled_coated_unbacked_coplanar'): keys.append('lower_air_height')
    for key in keys:
        if mode=='omitted': p.pop(key)
        elif mode=='null': p[key]=None
        else: p[key]=.02400000000012345 if key=='box_width' else .00800000000012345
    mesh=dict(edge_size=7e-6,far_size=.00031,grade=.17,min_angle=28)
    request=dict(template=template,parameters=p,mesh=mesh)
    doc=execute(dict(action='document',**request))['document']
    saved=execute(dict(action='template-document',**request))
    canonical={**p,**({key:None for key in keys} if mode=='omitted' else {})}
    assert saved['parameters']==canonical and saved['document']==doc
    if mode=='omitted': assert all(key not in p for key in keys)
    assert execute(dict(action='template-open',text=saved['document_text']))==saved
    assert doc['mesh']==mesh
    direct=sipi.CrossSectionDocument(TEMPLATES[template](**p),mesh=mesh).to_dict()
    assert doc==direct
    if mode=='fixed':
        assert doc['box']['width']==p['box_width']
        if 'air_height' in keys:
            expected = p['thickness']+p['coating_thickness']+p['air_height'] if 'coating_thickness' in p else p['air_height']
            assert doc['layers'][-1]['thickness']==expected
        if 'lower_air_height' in keys: assert doc['layers'][0]['thickness']==p['lower_air_height']
    else:
        omitted={k:v for k,v in p.items() if k not in keys}
        assert execute(dict(action='document',template=template,parameters=omitted,mesh=mesh))['document']==doc
    changed={**p,'box_width':.028}
    if 'air_height' in keys: changed['air_height']=.009
    if 'lower_air_height' in keys: changed['lower_air_height']=.011
    assert execute(dict(action='document',template=template,parameters=changed,mesh=mesh))['document']['mesh']==mesh


@pytest.mark.parametrize('template', TEMPLATES)
def test_domain_rejects_box_that_cannot_contain_copper_before_solve(template):
    p={**parameters(template),'box_width':.0001}
    with pytest.raises(ValueError):
        execute(dict(action='document',template=template,parameters=p))


@pytest.mark.parametrize('template', [n for n in TEMPLATES if n not in ('layered_coplanar_stripline','coupled_layered_coplanar_stripline','layered_stripline','coupled_layered_stripline','broadside_stripline','stripline','coupled_stripline','offset_stripline','coplanar_stripline','coupled_coplanar_stripline')])
def test_surface_domain_rejects_nonpositive_air_before_solve(template):
    with pytest.raises(ValueError):
        execute(dict(action='document',template=template,parameters={**parameters(template),'air_height':0}))


@pytest.mark.parametrize('template', ['layered_coplanar_stripline', 'coupled_layered_coplanar_stripline', 'layered_stripline', 'coupled_layered_stripline', 'broadside_stripline', 'stripline', 'coupled_stripline', 'offset_stripline', 'coplanar_stripline', 'coupled_coplanar_stripline'])
def test_buried_templates_reject_an_air_height_argument_before_solve(template):
    with pytest.raises(TypeError, match="unexpected keyword argument 'air_height'"):
        execute(dict(action='document', template=template,
                     parameters={**parameters(template), 'air_height': .006}))
