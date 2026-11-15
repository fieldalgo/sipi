# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Ordered single quantities, retained failures and independent lossy scalar fields."""
from types import SimpleNamespace
from dataclasses import FrozenInstanceError
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_face_line_study import TwoGroundFaceLineQuantityStudyDocument as Document
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line,TwoGroundFacePanelLineError
from sipi.execution import normalize_saved,execute_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_fem_shape_study import source as original_source
from test_two_ground_face_panel_line import metal,faces
from test_execution_record import ARTIFACTS

QUANTITIES=('impedance_real','attenuation','differential_forward_impedance_real','common_forward_impedance_real')


def document(quantity='impedance_real',physical=False,material=False,sampling=None):
    pair=quantity in QUANTITIES[2:]
    if physical:
        study=ImpedanceStudyDocument('offset_stripline',dict(width=.0006,plane_spacing=.002,
            trace_height=.0007,eps_r=4.,thickness=.00005,tan_delta=.003,box_width=.008),
            quantity='z0',frequency=2e9,materials={},mesh=dict(edge_size=5e-6,far_size=.0001,grade=.05),
            sampling=dict(kind='sweep',count=3,variables=[dict(name='width',lower=.00055,upper=.00065)]))
    else:study=original_source(pair,material=material,sampling=sampling)
    return Document(study,quantity=quantity,conductors=(dict(positive=faces(),negative=dict(zip(faces(),reversed(list(faces().values()))))) if pair else dict(signal=faces())),
        reference=dict(kind='surfaces',bottom=metal(58e6),top=metal(21e6),sides=None,conductors={}),
        ground_thickness=35e-6,panels_per_edge=64,ground_modes=128,interpolation_degree=16)


def synthetic(monkeypatch,fail_at=None,interrupt=False):
    calls=[]
    def analyze(doc):
        calls.append(doc.dumps())
        if len(calls)==fail_at:
            if interrupt:raise KeyboardInterrupt()
            cause=ArithmeticError('original current refusal')
            raise TwoGroundFacePanelLineError(cause,stage='current',input_json=doc.dumps(),factors=None,
                settings=doc.current_options,mesh_observation=None) from cause
        names=tuple(t.name for t in doc.cross_section.section.traces if not t.ground)
        frequency=np.array(doc.to_dict()['frequency_hz']);value=doc.cross_section.section.traces[0].width*1e5
        return SimpleNamespace(input_json=doc.dumps(),names=names,frequency=frequency,
            current_record=lambda:dict(kind='test-only-synthetic'),mesh_record=lambda:dict(kind='test-only-synthetic'),
            propagation=lambda:SimpleNamespace(modes=('single',),frequency=frequency,
                z_characteristic=np.array([[value+1j]]),gamma=np.array([[value/100+2j]])),
            characteristic=lambda:SimpleNamespace(basis='single-ended',names=names,frequency=frequency,
                mixed_mode=lambda:SimpleNamespace(z_characteristic=np.array([[[value+1j,2j],[2j,value/4+1j]]]))))
    monkeypatch.setattr(Line,'analyze',analyze);return calls


@pytest.mark.parametrize('quantity',QUANTITIES)
def test_fieldfree_snapshot_and_source_samples(monkeypatch,quantity):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preparation meshed'))
    doc=document(quantity);text=doc.dumps();assert Document.loads(text).dumps()==normalize_saved(text)==text
    np.testing.assert_array_equal(doc.samples(),original_source(quantity in QUANTITIES[2:]).samples())
    raw=doc.to_dict();raw['reference']['top']['conductivity']=1;assert doc.dumps()==text
    request=SavedExecutionRequest(text);project=SavedProject(request,project_id='line-study',design_id='a',title='Line',label='Source')
    assert SavedProject.loads(project.dumps()).prepare('a').request_id==request.request_id


@pytest.mark.parametrize('quantity',QUANTITIES)
def test_all_quantities_ordered_with_metal_and_mesh_evidence(monkeypatch,quantity):
    calls=synthetic(monkeypatch);doc=document(quantity);result=doc.analyze(max_evaluations=2)
    assert not result.failed and len(result.rows)==len(calls)==2
    ratio=.01 if quantity=='attenuation' else .25 if quantity=='common_forward_impedance_real' else 1.
    for index,(row,text) in enumerate(zip(result.rows,calls)):
        assert row.index==index and row.sample_values==tuple(doc.samples()[index])
        assert row.value==pytest.approx(row.sample_values[0]*1e5*ratio)
        raw=json.loads(text);assert raw['conductors']==doc.to_dict()['conductors'] and raw['reference']==doc.to_dict()['reference']
        assert raw['length_m']==0 and raw['reference_ohms']==50
        assert row.to_dict()['current_solver']['kind']==row.to_dict()['dielectric_mesh']['kind']=='test-only-synthetic'
    assert result.summary['mean']==pytest.approx(np.mean([r.value for r in result.rows]))
    with pytest.raises(TypeError):result.summary['mean']=0
    with pytest.raises(FrozenInstanceError):result.rows[0].value=0


@pytest.mark.parametrize('kind',['schema','missing','extra','quantity','wrong-source','missing-panel','duplicate','nan','missing-top','skin'])
def test_invalid_saved_contract_never_solves(monkeypatch,kind):
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('invalid input solved'))
    raw=document().to_dict();text=None
    if kind=='schema':raw['schema']+='/unknown'
    if kind=='missing':raw.pop('quantity')
    if kind=='extra':raw['extra']=1
    if kind=='quantity':raw['quantity']='insertion_loss'
    if kind=='wrong-source':raw['quantity']='differential_forward_impedance_real'
    if kind=='missing-panel':raw['panel'].pop('ground_modes')
    if kind=='duplicate':text=json.dumps(raw).replace('"ground_modes": 128','"ground_modes": 128,"ground_modes": 128')
    if kind=='nan':text=json.dumps(raw).replace('"ground_modes": 128','"ground_modes": NaN')
    if kind=='missing-top':raw['reference']['top']=None
    if kind=='skin':raw['ground_thickness_m']=1e-8
    with pytest.raises((ValueError,TypeError)):Document.loads(text or json.dumps(raw))


@pytest.mark.parametrize('phase',['parameters','materials','input','extraction','diagnostic'])
def test_failed_rows_keep_original_phase_and_receipt(monkeypatch,phase):
    import sipi.fem_shape_study as loop
    import sipi.two_ground_face_line_study as module
    sampling=dict(kind='sweep',count=3,variables=[dict(name='width',lower=.0003,upper=.0005)])
    doc=document(sampling=sampling);calls=synthetic(monkeypatch,fail_at=2 if phase=='extraction' else None)
    if phase in ('parameters','materials','input'):
        target=module if phase=='input' else loop;name={'parameters':'_parameters','materials':'_sample_material','input':'_line_from_inputs'}[phase];original=getattr(target,name);seen=[]
        def fail_second(*args,**kwargs):
            seen.append(1)
            if len(seen)==2:raise ArithmeticError('original preparation refusal')
            return original(*args,**kwargs)
        monkeypatch.setattr(target,name,fail_second)
    if phase=='diagnostic':
        original=Line.analyze
        def analyze(self):
            line=original(self)
            if len(calls)==2:
                def fail():raise ArithmeticError('original diagnostic refusal')
                line.propagation=fail
            return line
        monkeypatch.setattr(Line,'analyze',analyze)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=3);receipt=request.run();out=receipt['execution']
    assert out['status']=='incomplete' and out['result']['failed']==1 and out['result']['summary'] is None
    rows=out['result']['rows'];assert len(rows)==3 and rows[1]['phase']==phase and rows[1]['value'] is None
    assert rows[0]['phase']==rows[2]['phase']=='complete'
    if phase=='extraction':assert rows[1]['cause_details']['cause_type']=='ArithmeticError'
    if phase=='diagnostic':assert rows[1]['current_solver'] and rows[1]['dielectric_mesh']
    record=SavedExecutionRecord(request,receipt,run_id='line-study:partial',artifacts=ARTIFACTS)
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt


def test_material_leaf_correlation_invalid_rows_and_budget(monkeypatch):
    calls=synthetic(monkeypatch);doc=document('attenuation',material=True);result=doc.analyze(max_evaluations=2)
    assert result.failed==0
    for row,text in zip(result.rows,calls):assert json.loads(text)['materials']['dielectric']['parameters']['tan_delta']==row.sample_values[0]
    sampling=dict(kind='normal',count=8,seed=3,correlation=[[1.]],variables=[dict(name='width',mean=.0002,std=.0003)])
    doc=document(sampling=sampling)
    calls.clear()
    with pytest.raises(ValueError,match='before any solve'):doc.analyze(max_evaluations=7)
    assert not calls
    result=doc.analyze(max_evaluations=8);assert 0<result.failed<8 and result.summary is None
    np.testing.assert_array_equal([r.sample_values for r in result.rows],doc.samples())
    assert len(calls)==8-result.failed


def test_interrupt_propagates(monkeypatch):
    calls=synthetic(monkeypatch,fail_at=2,interrupt=True)
    with pytest.raises(KeyboardInterrupt):document().analyze(max_evaluations=2)
    assert len(calls)==2


def test_actual_scalar_sweep_refinement_and_complex_closed_forms(record_property):
    doc=document(physical=True);result=doc.analyze(max_evaluations=3)
    assert not result.failed and len(result.rows)==3
    records=[]
    for row in result.rows:
        levels=[row.result]
        for count in (128,256):
            raw=json.loads(row.input_json);raw['panel']['panels_per_edge']=count;levels.append(Line.from_dict(raw).analyze())
        records.append(dict(input=json.loads(row.input_json),value=row.value,levels=[dict(panel=dict(x.panel_settings),R=x.R.tolist(),L=x.L.tolist(),C0=x.current_factors.C0.tolist(),current=x.current_record(),mesh=x.mesh_record()) for x in levels]))
        for key in ('R','L','C0'):
            values=[x.current_factors.C0 if key=='C0' else getattr(x,key) for x in levels]
            for a,b in zip(values,values[1:]):np.testing.assert_allclose(a,b,rtol=.01,atol=0)
        for line in levels:
            omega=2*np.pi*line.frequency[0];z=line.R[0,0,0]+1j*omega*line.L[0,0,0];y=line.G[0,0,0]+1j*omega*line.C[0,0,0]
            expected_z=np.sqrt(z/y);expected_gamma=np.sqrt(z*y);actual=line.propagation()
            np.testing.assert_allclose(actual.z_characteristic[0,0],expected_z,rtol=1e-12,atol=0)
            np.testing.assert_allclose(actual.gamma[0,0],expected_gamma,rtol=1e-12,atol=0)
        assert row.value==pytest.approx(levels[0].propagation().z_characteristic[0,0].real,rel=1e-14)
    record_property('two_ground_face_scalar_study',json.dumps(records,sort_keys=True))
