# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved frequency inputs against independent voltage/current boundary waves."""
import json
import numpy as np
import pytest
from scipy.linalg import expm
from sipi import CrossSection, CrossSectionDocument, quasistatic_network
from sipi.template_document import TemplateSectionDocument
from sipi.quasistatic_line_document import QuasistaticLineDocument
from sipi.execution import execute_saved, normalize_saved

MESH=dict(edge_size=8e-6,far_size=.3e-3,grade=.25)


def section(pair=False):
    p=dict(width=.4e-3,plane_spacing=1e-3,eps_r=4.,tan_delta=.01,box_width=6e-3)
    if pair: p['gap']=.3e-3
    return TemplateSectionDocument('coupled_stripline' if pair else 'stripline',p,mesh=MESH)


def document(pair=False,**kw):
    options=dict(resistance=5.3,length=.075,z_ref=47.)
    options.update(kw)
    return QuasistaticLineDocument(section(pair),[0.,1e8,2e8],**options)


@pytest.mark.parametrize('pair',[False,True])
@pytest.mark.parametrize('editable',[False,True])
def test_exact_input_roundtrip_no_calculation_and_detached_mutations(pair,editable,monkeypatch):
    sec=section(pair);sec=sec if editable else sec.cross_section
    def forbidden(*a,**k): pytest.fail('Input operation meshed')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    original=QuasistaticLineDocument(sec,[0.,1e8,2e8],resistance=5.3,length=.075,z_ref=47.)
    raw=original.to_dict();restored=QuasistaticLineDocument.loads(original.dumps())
    assert normalize_saved(restored.dumps())==original.dumps()
    assert restored.section.dumps()==sec.dumps()
    raw['frequency_hz'][0]=12;raw['resistance_ohm_per_m']=0
    assert original.to_dict()!=raw


@pytest.mark.parametrize('field,value',[
    ('schema','sipi.quasistatic-line/2'),('frequency_hz',[]),('frequency_hz',[1,1]),
    ('frequency_hz',[True,1e8]),('frequency_hz',[-1,1]),('frequency_hz',[2,1]),
    ('frequency_hz',[float('inf')]),('frequency_hz',[[1,2]]),
    ('resistance_ohm_per_m',True),('resistance_ohm_per_m',-1),
    ('length_m',True),('length_m',-1),('length_m','1'),('reference_ohms',0),
    ('reference_ohms',[50,50]),('reference_ohms',float('nan')),('section',{}),('extra',1)])
def test_bad_inputs_reject_without_meshing(field,value,monkeypatch):
    raw=document().to_dict();raw[field]=value
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('Invalid input meshed'))
    with pytest.raises(ValueError): QuasistaticLineDocument.from_dict(raw)


@pytest.mark.parametrize('field',['frequency_hz','section','resistance_ohm_per_m','length_m','reference_ohms'])
def test_missing_inputs_reject(field):
    raw=document().to_dict();raw.pop(field)
    with pytest.raises(ValueError): QuasistaticLineDocument.from_dict(raw)


@pytest.mark.parametrize('frequency',[[True,1e8],[1.,False],[float('nan')]])
def test_constructor_preserves_boolean_and_nonfinite_rejection(frequency):
    with pytest.raises(ValueError): QuasistaticLineDocument(section(),frequency,resistance=0.,length=.1)


@pytest.mark.parametrize('text',['{"schema":1,"schema":2}','{"a":NaN}','{"a":Infinity}'])
def test_ambiguous_json_rejects(text):
    with pytest.raises(ValueError): QuasistaticLineDocument.loads(text)


@pytest.mark.parametrize('pair',[False,True])
def test_saved_network_matches_independent_boundary_solution_and_one_field_extraction(pair,monkeypatch):
    doc=document(pair);calls=[];original=CrossSection.analyze
    def observed(self,**kw): calls.append(kw);return original(self,**kw)
    monkeypatch.setattr(CrossSection,'analyze',observed)
    result=QuasistaticLineDocument.loads(doc.dumps()).analyze();assert len(calls)==1
    line,net=result.line,result.network;n=len(line.names);eye=np.eye(n);zero=np.zeros((n,n));zref=47.
    expected=[]
    # Integrate telegrapher V/I equations directly with current in +z at both
    # ends; solve boundary incident/reflected power-wave equations, not the
    # network engine's propagation or conversion helpers.
    for f in net.frequency:
        z=5.3*eye+2j*np.pi*f*line.L;y=line.G(f)+2j*np.pi*f*line.C
        transfer=expm(-.075*np.block([[zero,z],[y,zero]]))
        av=np.block([[eye,zero],[eye/zref,zero]])
        bv=np.block([[eye,zero],[-eye/zref,zero]])
        af=np.block([[zero,eye],[zero,-eye/zref]])
        bf=np.block([[zero,eye],[zero,eye/zref]])
        expected.append(np.linalg.solve(bf-transfer@bv,transfer@av-af))
    np.testing.assert_allclose(net.s,expected,rtol=1e-10,atol=1e-11)
    np.testing.assert_allclose(net.s,net.s.transpose(0,2,1),rtol=1e-10,atol=1e-11)
    assert all(np.linalg.svd(s,compute_uv=False)[0]<=1+1e-11 for s in net.s)
    direct=quasistatic_network(line,net.frequency,R=5.3*eye,length=.075,z_ref=47.)
    np.testing.assert_array_equal(net.s,direct.s)
    out=execute_saved(doc.dumps());assert out['status']=='complete'
    saved=out['result']['network']['s']
    np.testing.assert_array_equal(np.array(saved['real'])+1j*np.array(saved['imag']),net.s)
    assert result.input_json==doc.dumps()


@pytest.mark.parametrize('pair',[False,True])
def test_zero_length_is_exact_through_and_dc_resistor_contract(pair):
    doc=document(pair,length=0.);out=doc.analyze();n=len(out.line.names)
    through=np.block([[np.zeros((n,n)),np.eye(n)],[np.eye(n),np.zeros((n,n))]])
    np.testing.assert_allclose(out.network.s,np.broadcast_to(through,out.network.s.shape),atol=1e-12,rtol=0)
    result=document(pair).analyze();r=5.3*.075;reflection=r/(2*47+r);transmission=2*47/(2*47+r)
    expected=np.block([[np.eye(n)*reflection,np.eye(n)*transmission],[np.eye(n)*transmission,np.eye(n)*reflection]])
    np.testing.assert_allclose(result.network.s[0],expected,rtol=1e-12,atol=1e-12)


@pytest.mark.parametrize('name',list(__import__('test_template_document').CASES))
def test_all_registered_manufacturing_inputs_are_retained_without_field_solve(name,monkeypatch):
    from test_template_document import CASES
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('Input meshed'))
    sec=TemplateSectionDocument(name,CASES[name]['supplied_parameters'],mesh=MESH)
    saved=QuasistaticLineDocument(sec,[0.,1e8],resistance=1.,length=.1)
    assert QuasistaticLineDocument.loads(saved.dumps()).section.dumps()==sec.dumps()
    assert normalize_saved(saved.dumps())==saved.dumps()
