# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit current method storage, matched fields and finite-domain checks."""
import json
import numpy as np
import pytest
from scipy.linalg import expm

from sipi import (CrossSection, CrossSectionDocument, coupled_microstrip,
                  asymmetric_coupled_microstrip)
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.execution import normalize_saved, execute_saved
from sipi.constants import mu_0, epsilon_0
from test_layered_study import material
from test_layered_metal import transfer
from test_execution import line as inexpensive_line, network_equal
from test_panel_line import base as admitted_panel_line

MESH = dict(edge_size=5e-6, far_size=.2e-3, grade=.1)


def document(asymmetric=False, *, perfect=False):
    if asymmetric:
        section = asymmetric_coupled_microstrip(left_width=.0006049313913923509,
            right_width=.5e-3, gap=.0004095299364073505, substrate_height=.5e-3,
            eps_r=4., tan_delta=.02, left_thickness=35e-6, right_thickness=50e-6,
            box_width=.024, air_height=.010)
    else:
        section = coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=1e-3,
            thickness=.05e-3, eps_r=4., tan_delta=.02)
    metal = material() if asymmetric else dict(conductivity=58e6,
        relative_permeability=1., roughness={'kind':'smooth'})
    conductor = {'kind':'perfect'} if perfect else dict(kind='surface-boundaries',
        conductors={t.name:metal for t in section.traces}, reference=metal, ground_thickness=35e-6)
    line = TransmissionLineDocument(CrossSectionDocument(section, mesh=MESH), [1e9,2e9,4e9],
        materials={}, conductor=conductor, length=.02, schema='sipi.transmission-line/7')
    return PanelTransmissionLineDocument(line, panels_per_edge=128, ground_modes=1024,
        interpolation_degree=16, schema="sipi.panel-transmission-line/2")


def test_field_free_normalization_copies_inputs_and_keeps_method(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    doc = document(True); text = doc.dumps()
    assert normalize_saved(text) == text == PanelTransmissionLineDocument.loads(text).dumps()
    data = doc.to_dict(); data['line']['conductor']['reference']['coatings'][0]['thickness_m'] = 0
    assert doc.dumps() == text and doc.line.to_dict() == doc.to_dict()['line']
    with pytest.raises(ValueError): TransmissionLineDocument.loads(text)


@pytest.mark.parametrize('where', ['root','line','conductor','coating'])
@pytest.mark.parametrize('mutation', ['unknown','missing'])
def test_strict_nested_keys(where, mutation):
    data = document(True).to_dict()
    target = {'root':data,'line':data['line'],'conductor':data['line']['conductor'],
              'coating':data['line']['conductor']['reference']['coatings'][0]}[where]
    if mutation == 'unknown': target['unexpected'] = 1
    else: target.pop(next(iter(target)))
    with pytest.raises(ValueError): PanelTransmissionLineDocument.from_dict(data)


@pytest.mark.parametrize('change', ['schema','nested-schema','duplicate','nonfinite','zero-thickness'])
def test_unsupported_inputs_remain_explicit(change):
    doc = document(perfect=True); text = doc.dumps()
    if change=='schema': text=text.replace('sipi.panel-transmission-line/2','sipi.panel-transmission-line/3')
    if change=='nested-schema': text=text.replace('sipi.transmission-line/7','sipi.transmission-line/8')
    if change=='duplicate': text=text.replace('"length_m": 0.02','"length_m": 0.02, "length_m": 0.02')
    if change=='nonfinite': text=text.replace('"length_m": 0.02','"length_m": NaN')
    if change=='zero-thickness':
        data=doc.to_dict();data['line']['cross_section']['traces'][0]['thickness']=0
        text=json.dumps(data)
    with pytest.raises(ValueError): PanelTransmissionLineDocument.loads(text)


def test_budget_and_real_core_admission_precede_mesh(monkeypatch):
    doc = document(True)
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preflight meshed'))
    with pytest.raises(ValueError,match='before any field solve'):
        execute_saved(doc.dumps(),max_evaluations=2)
    data = doc.to_dict();data['line']['conductor']['ground_thickness']=10e-6
    with pytest.raises(ValueError,match='reference: .*skin depth'):
        PanelTransmissionLineDocument.from_dict(data)


def test_legacy_uniform_surface_choice_is_not_silently_converted():
    data=document().to_dict();data['line']['conductor']=dict(kind='surface',conductivity=58e6,
        ground_thickness=35e-6,relative_permeability=1.,roughness={'kind':'smooth'})
    with pytest.raises(ValueError,match='perfect or surface-boundaries'):
        PanelTransmissionLineDocument.from_dict(data)


def test_perfect_v7_keeps_prior_panel_arrays_exact():
    line=admitted_panel_line(perfect=True);legacy=PanelTransmissionLineDocument(line).analyze()
    raw=line.to_dict();raw['schema']='sipi.transmission-line/7'
    candidate=PanelTransmissionLineDocument(TransmissionLineDocument.from_dict(raw),
        schema='sipi.panel-transmission-line/2').analyze()
    for key in ('C','G','R','L'): np.testing.assert_array_equal(getattr(candidate,key),getattr(legacy,key))
    np.testing.assert_array_equal(candidate.network.s,legacy.network.s)
    np.testing.assert_array_equal(candidate.current_factors.parts,legacy.current_factors.parts)
    assert candidate.conductor is None


def test_both_versions_keep_panel_clearance_refusal():
    line=inexpensive_line()
    for version in (1,2):
        raw=line.to_dict()
        if version==2:raw['schema']='sipi.transmission-line/7'
        doc=PanelTransmissionLineDocument(TransmissionLineDocument.from_dict(raw),
            schema=f'sipi.panel-transmission-line/{version}')
        with pytest.raises(ValueError,match='cluster extent'):
            doc.analyze()


def test_versions_keep_nested_contracts_separate():
    raw=document().to_dict();raw['schema']='sipi.panel-transmission-line/1'
    with pytest.raises(ValueError):PanelTransmissionLineDocument.from_dict(raw)
    raw=document().to_dict();raw['line']['schema']='sipi.transmission-line/6'
    with pytest.raises(ValueError):PanelTransmissionLineDocument.from_dict(raw)


@pytest.fixture(scope='module',params=[False,True],ids=['symmetric','asymmetric-coated'])
def extracted(request):
    doc=document(request.param)
    return doc,doc.analyze()


def test_surface_laws_and_full_transfer_are_independent(extracted,record_property):
    doc,result=extracted;f=result.frequency;factors=result.current_factors
    coated=doc.to_dict()['line']['conductor']['reference'].get('kind')=='layered'
    zs=np.array([transfer(x) if coated else np.sqrt(2j*np.pi*x*mu_0/58e6) for x in f])
    np.testing.assert_allclose(result.R+2j*np.pi*f[:,None,None]*result.conductor.L_internal,
                               zs[:,None,None]*factors.total,rtol=1e-10)
    errors=[]
    for i,frequency in enumerate(f):
        z=result.R[i]+2j*np.pi*frequency*result.L[i]
        y=result.G[i]+2j*np.pi*frequency*result.C[i]
        matrix=expm(np.block([[np.zeros((2,2)),z],[y,np.zeros((2,2))]])*.003)
        roots,vectors=np.linalg.eig(matrix);v=vectors[:,abs(roots)>1]
        assert v.shape==(4,2)
        expected=np.linalg.solve(v[2:].T,v[:2].T).T
        errors.append(float(abs(result.characteristic().z_characteristic[i]-expected).max()/abs(expected).max()))
    record_property('independent_transfer_errors',json.dumps(errors))
    assert max(errors)<1e-10
    np.testing.assert_allclose(result.dielectric.L@factors.C0,
                               mu_0*epsilon_0*np.eye(2),rtol=1e-10,atol=1e-28)
    np.testing.assert_allclose(result.network.s,result.network.s.swapaxes(1,2),rtol=0,atol=1e-10)
    assert np.linalg.svd(result.network.s,compute_uv=False).max()<=1+1e-10


def test_common_execution_keeps_actual_method_and_one_mesh(extracted,monkeypatch):
    doc,result=extracted;calls=[];original=CrossSection.mesh
    def mesh(self,**options): calls.append(options);return original(self,**options)
    monkeypatch.setattr(CrossSection,'mesh',mesh)
    output=execute_saved(doc.dumps(),diagnostics=['characteristic','modes'])
    assert calls==[doc.line.cross_section.mesh_options] and output['status']=='complete'
    network_equal(output['result']['network'],result.network)
    saved=output['result']['current_solver']
    assert saved['kind']=='grounded-rectangle-panels' and saved['diagnostics']['current_error']<1e-10
    np.testing.assert_array_equal(saved['surface_current_factors_per_m'],result.current_factors.parts)
    assert output['input']==doc.to_dict()


def test_panel_volume_and_outer_changes_remain_separate(extracted,record_property):
    doc,coarse=extracted
    def quantities(r):return {'R':r.R,'L_internal':r.conductor.L_internal,'C':r.C,'G':r.G,
                              'C0':r.current_factors.C0,'parts':r.current_factors.parts}
    def changes(a,b):return {key:float(abs(value-quantities(b)[key]).max()/abs(quantities(b)[key]).max())
                             for key,value in quantities(a).items()}
    def snapshot(r):return dict(input=json.loads(r.input_json),
        quantities={k:v.tolist() for k,v in quantities(r).items()})
    data=doc.to_dict();data['panel']['panels_per_edge']=256
    panel=PanelTransmissionLineDocument.from_dict(data).analyze()
    rows=[dict(kind='panel',changes=changes(panel,coarse))]
    snapshots=[snapshot(coarse),snapshot(panel)]
    for key in ('edge_size','far_size','grade'):data['line']['cross_section']['mesh'][key]/=2
    refined=PanelTransmissionLineDocument.from_dict(data).analyze()
    rows.append(dict(kind='volume',changes=changes(refined,panel)))
    snapshots.append(snapshot(refined))
    # Changing volume resolution must not change the selected vacuum-current method.
    np.testing.assert_array_equal(refined.current_factors.parts,panel.current_factors.parts)
    np.testing.assert_array_equal(refined.R,panel.R)
    for factor in (1.5,2.):
        larger=json.loads(json.dumps(data));cross=larger['line']['cross_section']
        cross['box']['width']*=factor;cross['layers'][-1]['thickness']*=factor
        larger['panel']['ground_modes']=int(1024*factor)
        result=PanelTransmissionLineDocument.from_dict(larger).analyze()
        rows.append(dict(kind='outer',factor=factor,changes=changes(result,refined)))
        snapshots.append(snapshot(result))
    record_property('layered_panel_refinement',json.dumps(dict(rows=rows,snapshots=snapshots)))
    # These maximum-matrix-norm bounds do not certify relative error of small entries.
    assert all(max(row['changes'].values())<=.005 for row in rows)
    for group in range(3):
        relative=float(abs(panel.current_factors.parts[group]-coarse.current_factors.parts[group]).max()
                       /abs(coarse.current_factors.parts[group]).max())
        assert relative<=.005
