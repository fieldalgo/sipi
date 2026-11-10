"""Editable forms reuse canonical engine inputs without a geometry inference."""
import json
from pathlib import Path
import sys

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from engine import execute, TEMPLATES
from sipi import CrossSection
from sipi.template_document import TemplateSectionDocument


def parameters(name):
    p = dict(width=.5e-3, thickness=.035e-3, eps_r=4.1, tan_delta=.01,
             box_width=.03, top_width=None)
    p['plane_spacing' if name in ('stripline', 'coupled_stripline', 'offset_stripline') else 'substrate_height'] = 1e-3
    if name not in ('stripline', 'coupled_stripline', 'offset_stripline'): p['air_height'] = .0067
    if name in ('coated_unbacked_coplanar', 'coupled_coated_unbacked_coplanar', 'coupled_unbacked_coplanar', 'unbacked_coplanar', 'coupled_microstrip', 'coupled_stripline', 'grounded_coplanar', 'coupled_grounded_coplanar', 'coupled_coated_microstrip', 'coated_grounded_coplanar', 'coupled_coated_grounded_coplanar'): p['gap'] = .2e-3
    if name in ('coupled_stripline', 'offset_stripline'): p['trace_height'] = .0003
    if name in ('coated_unbacked_coplanar', 'coupled_coated_unbacked_coplanar', 'coupled_unbacked_coplanar', 'unbacked_coplanar', 'grounded_coplanar', 'coupled_grounded_coplanar', 'coated_grounded_coplanar', 'coupled_coated_grounded_coplanar'): p.update(ground_width=.003)
    if name in ('coupled_coated_unbacked_coplanar', 'coupled_unbacked_coplanar', 'coupled_grounded_coplanar', 'coupled_coated_grounded_coplanar'): p['ground_gap'] = .0002500000000123456
    if name in ('coated_unbacked_coplanar', 'coupled_coated_unbacked_coplanar', 'coated_microstrip', 'coupled_coated_microstrip', 'coated_grounded_coplanar', 'coupled_coated_grounded_coplanar'): p.update(coating_height=.2e-3, coating_eps_r=3, coating_tan_delta=.02, top_width=.4e-3)
    if name in ('unbacked_coplanar', 'coupled_unbacked_coplanar', 'coated_unbacked_coplanar', 'coupled_coated_unbacked_coplanar'): p['lower_air_height'] = .006700000000123456
    if name in ('conformal_coated_microstrip', 'coupled_conformal_coated_microstrip'):
        p.update(coating_thickness=.000020000000000123456, coating_eps_r=3.5, coating_tan_delta=.02, top_width=.4e-3)
        if name.startswith('coupled_'): p['gap'] = .3e-3
    return p


@pytest.mark.parametrize('name', TEMPLATES)
def test_editable_roundtrip_preserves_direct_geometry_and_hidden_arguments(name, monkeypatch):
    def no_mesh(*a, **k): raise AssertionError('Saving/opening must not solve fields')
    monkeypatch.setattr(CrossSection, 'mesh', no_mesh)
    p = parameters(name)
    mesh = dict(edge_size=1e-5, far_size=.001, grade=.2, min_angle=28)
    direct = TemplateSectionDocument(name, p, mesh=mesh)
    saved = execute(dict(action='template-document', template=name, parameters=p, mesh=mesh))
    opened = execute(dict(action='template-open', text=saved['document_text']))
    assert opened == saved
    assert saved['document_text'] == direct.dumps()
    assert saved['document'] == direct.cross_section.to_dict()
    assert saved['parameters'] == direct.parameters
    assert execute(dict(action='document', template=name, parameters=opened['parameters'], mesh=opened['document']['mesh']))['document'] == saved['document']


@pytest.mark.parametrize('bad', [None, 1, True, '{}', '{"schema":1,"schema":2}', '{"a":NaN}', ' '*204801],
                         ids=['null', 'number', 'boolean', 'empty-object', 'duplicate-key', 'nonfinite', 'oversized'])
def test_open_rejects_bad_or_oversized_text(bad):
    with pytest.raises((ValueError, TypeError)):
        execute(dict(action='template-open', text=bad))


def test_open_rejects_mismatch_and_unknown_options():
    doc = TemplateSectionDocument('stripline', parameters('stripline')).to_dict()
    doc['parameters']['width'] *= 2
    with pytest.raises(ValueError, match='do not match'):
        execute(dict(action='template-open', text=json.dumps(doc)))
    for request in [dict(action='template-open', text='{}', path='a'), dict(action='template-document'),
                    dict(action='template-document', template='stripline', parameters=parameters('stripline'), ignored=True)]:
        with pytest.raises(ValueError): execute(request)


def test_no_form_for_valid_unsupported_template():
    # Engine support does not imply a matching editable UI form.
    doc = TemplateSectionDocument('broadside_stripline', dict(width=.0005, gap=.0002, thickness=.000035, plane_spacing=.001, eps_r=4))
    with pytest.raises(ValueError, match='no editable form'):
        execute(dict(action='template-open', text=doc.dumps()))


def test_reopened_analysis_exact_and_edited_parameters_change_geometry():
    p = dict(width=.0005, plane_spacing=.001, eps_r=4)
    saved = execute(dict(action='template-document', template='stripline', parameters=p,
                         mesh=dict(edge_size=8e-6, far_size=.00025, grade=.3)))
    opened = execute(dict(action='template-open', text=saved['document_text']))
    common = dict(template=opened['template'], parameters=opened['parameters'], mesh=opened['document']['mesh'])
    result = execute(dict(action='analyze', **common))
    direct = execute(dict(action='analyze', document=opened['document']))
    assert result['line'] == direct['line'] and result['document'] == direct['document']
    common['parameters']['width'] = .0006
    edited = execute(dict(action='template-document', **common))
    assert edited['document']['traces'][0]['width'] == .0006
    assert edited['document']['mesh'] == opened['document']['mesh']
    assert json.loads(saved['document_text'])['parameters']['width'] == .0005
