# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
import numpy as np
import pytest
from scipy import linalg
import sipi.panel_line as candidate
from sipi.panel_line import PanelTransmissionLineDocument
from sipi import CrossSection,Layer,Trace,CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.constants import epsilon_0,mu_0


def base(perfect=False):
    section=CrossSection([Layer('uniform',.002,4.2,tan_delta=.02)],
        [Trace('left',-.0003,.0005,.0002,thickness=35e-6),Trace('right',.0003,.0005,.0002,thickness=35e-6)],.004)
    metal=lambda sigma:dict(conductivity=sigma,relative_permeability=1.,roughness={'kind':'smooth'})
    conductor={'kind':'perfect'} if perfect else dict(kind='surface-boundaries',conductors={'left':metal(58e6),'right':metal(35e6)},reference=metal(45e6),ground_thickness=35e-6)
    return TransmissionLineDocument(CrossSectionDocument(section,mesh=dict(edge_size=10e-6,far_size=.2e-3,grade=.1)),[1e9,2e9],materials={},conductor=conductor,length=.02,schema='sipi.transmission-line/3')


def test_normalize_is_field_free_and_isolated(monkeypatch):
    def forbidden(*a,**k):raise AssertionError('normalization reached a field solve')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr(candidate,'panel_surface_current_factors',forbidden)
    monkeypatch.setattr(candidate,'panel_conductor_loss_by_boundary',forbidden)
    line=base();doc=PanelTransmissionLineDocument(line,panels_per_edge=16)
    text=doc.dumps();assert PanelTransmissionLineDocument.loads(text).dumps()==text
    d=doc.to_dict();d['panel']['panels_per_edge']=32;d['line']['length_m']=1.
    options=doc.panel_options;options['ground_modes']=64
    assert doc.dumps()==text and doc.line.dumps()==line.dumps()
    with pytest.raises(ValueError):TransmissionLineDocument.loads(text)


@pytest.mark.parametrize('key,bad',[('panels_per_edge',True),('panels_per_edge',0),('panels_per_edge',257),('panels_per_edge',2.),('ground_modes',63),('ground_modes',4097),('ground_modes',True),('interpolation_degree',11),('interpolation_degree',17),('interpolation_degree',12.),('interpolation_degree',True)])
def test_invalid_controls_before_field_solve(key,bad):
    data=PanelTransmissionLineDocument(base()).to_dict();data['panel'][key]=bad
    with pytest.raises(ValueError):PanelTransmissionLineDocument.from_dict(data)


@pytest.mark.parametrize('where',['root','panel','line'])
def test_unknown_or_missing_keys(where):
    data=PanelTransmissionLineDocument(base()).to_dict();target=data if where=='root' else data[where];target['unexpected']=1
    with pytest.raises(ValueError):PanelTransmissionLineDocument.from_dict(data)
    target.pop('unexpected');target.pop(next(iter(target)))
    with pytest.raises(ValueError):PanelTransmissionLineDocument.from_dict(data)


def test_duplicate_and_nonfinite_inputs():
    text=PanelTransmissionLineDocument(base()).dumps()
    with pytest.raises(ValueError):PanelTransmissionLineDocument.loads(text.replace('"ground_modes": 512','"ground_modes": 512, "ground_modes": 512'))
    with pytest.raises(ValueError):PanelTransmissionLineDocument.loads(text.replace('"ground_modes": 512','"ground_modes": NaN'))
    with pytest.raises(ValueError):PanelTransmissionLineDocument.loads(text.replace('sipi.panel-transmission-line/1','sipi.panel-transmission-line/2'))


@pytest.fixture(scope='module',params=[False,True])
def result(request):
    doc=PanelTransmissionLineDocument(base(request.param),panels_per_edge=16)
    return doc,doc.analyze()


def test_matching_panel_vacuum_and_uniform_material(result):
    doc,r=result;f=r.frequency
    np.testing.assert_allclose(r.C,4.2*np.broadcast_to(r.current_factors.C0,r.C.shape),rtol=1e-12,atol=0)
    np.testing.assert_allclose(r.G,2*np.pi*f[:,None,None]*.02*r.C,rtol=1e-12,atol=0)
    np.testing.assert_allclose(r.dielectric.C0,r.current_factors.C0,rtol=0,atol=0)
    np.testing.assert_allclose(r.dielectric.L@r.current_factors.C0,mu_0*epsilon_0*np.eye(2),rtol=1e-10,atol=1e-28)
    assert r.input_json==doc.dumps() and dict(r.panel_settings)==doc.panel_options
    with pytest.raises(TypeError):r.panel_settings['panels_per_edge']=32
    if r.conductor is None:assert np.all(r.R==0)
    else:
        np.testing.assert_array_equal(r.R,r.conductor.R)
        np.testing.assert_array_equal(r.L,r.current_factors.L_external[None]+r.conductor.L_internal)


def test_independent_two_n_characteristic_and_network_invariants(result):
    _,r=result;got=r.characteristic().z_characteristic
    for i,f in enumerate(r.frequency):
        Z=r.R[i]+2j*np.pi*f*r.L[i];Y=r.G[i]+2j*np.pi*f*r.C[i];scale=np.sqrt(abs(Z).max()/abs(Y).max())
        roots,vectors=linalg.eig(np.block([[np.zeros_like(Z),Z/scale],[scale*Y,np.zeros_like(Y)]]));mask=roots.imag>0
        assert np.count_nonzero(mask)==2 and np.all(roots[mask].real>=0)
        v=vectors[:,mask];expected=scale*v[:2]@np.linalg.inv(v[2:])
        np.testing.assert_allclose(got[i],expected,rtol=1e-10,atol=1e-10)
    np.testing.assert_allclose(r.network.s,r.network.s.swapaxes(1,2),rtol=0,atol=1e-10)
    assert np.linalg.svd(r.network.s,compute_uv=False).max()<=1+1e-10


def test_panel_refusal_happens_before_volume_mesh(monkeypatch):
    doc=PanelTransmissionLineDocument(base(),panels_per_edge=16)
    def fail(*a,**k):raise ValueError('explicit panel refusal')
    def forbidden(*a,**k):raise AssertionError('volume mesh before panel admission')
    monkeypatch.setattr(candidate,'panel_conductor_loss_by_boundary',fail);monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError,match='explicit panel refusal'):doc.analyze()


def test_exactly_one_volume_mesh(monkeypatch):
    doc=PanelTransmissionLineDocument(base(),panels_per_edge=16);original=CrossSection.mesh;calls=[]
    def mesh(self,**kwargs):calls.append(kwargs);return original(self,**kwargs)
    monkeypatch.setattr(CrossSection,'mesh',mesh);doc.analyze()
    assert calls==[doc.line.cross_section.mesh_options]

import pytest
from sipi.panel_line import PanelTransmissionLineDocument


def record():return PanelTransmissionLineDocument(base(perfect=True)).to_dict()


@pytest.mark.parametrize('boundary,value',[('bottom','open'),('top','ground'),('sides','ground')])
def test_unsupported_outer_conditions_are_explicit(boundary,value):
    data=record();data['line']['cross_section']['box'][boundary]=value
    message = 'no reference conductor' if boundary == 'bottom' else 'bottom ground and open top/sides'
    with pytest.raises(ValueError,match=message):
        PanelTransmissionLineDocument.from_dict(data)


def test_zero_thickness_perfect_strip_is_rejected():
    data=record();data['line']['cross_section']['traces'][0]['thickness']=0
    with pytest.raises(ValueError,match='positive conductor thickness'):
        PanelTransmissionLineDocument.from_dict(data)


def test_common_surface_law_is_not_silently_converted():
    data=record();data['line']['conductor']=dict(kind='surface',conductivity=58e6,
        ground_thickness=35e-6,relative_permeability=1.,roughness={'kind':'smooth'})
    with pytest.raises(ValueError,match='perfect or surface-boundaries'):
        PanelTransmissionLineDocument.from_dict(data)


def test_panel_count_resource_cap_precedes_solving():
    data=record();data['line']['cross_section']['traces'].append(dict(data['line']['cross_section']['traces'][0],name='third',x=.001))
    data['panel']['panels_per_edge']=256
    with pytest.raises(ValueError,match='panel count limit'):
        PanelTransmissionLineDocument.from_dict(data)
