# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Field-free contracts, ordered failures and explicit FEM study admission."""
import json
from types import SimpleNamespace
import numpy as np
import pytest
from sipi import CrossSection
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import ConstantDielectric
from sipi.execution import normalize_saved,execute_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.fem_shape_study import FEMShapeLineQuantityStudyDocument as Document
import sipi.fem_shape_study as api
from test_fem_shape_line import metal

MESH=dict(edge_size=5e-6,far_size=.0002,grade=.1)


def source(paired=False,factor=1.,material=False,sampling=None):
    parameters=dict(width=.0004,plane_spacing=.002,eps_r=4.,thickness=.00005,box_width=.008)
    if paired:parameters['gap']=.0003
    options={}
    if material:options=dict(material_variables={'loss':dict(region='dielectric',path=['tan_delta'])})
    if sampling is None:
        sampling=dict(kind='sweep',count=2,variables=[dict(name='loss',lower=.01,upper=.03) if material
            else dict(name='width',lower=.00039,upper=.00041)])
    return ImpedanceStudyDocument('coupled_stripline' if paired else 'stripline',parameters,
        quantity='z_diff_forward' if paired else 'z0',frequency=2e9,
        materials={'dielectric':ConstantDielectric(4.,.02)} if material else {},
        mesh={k:v*factor for k,v in MESH.items()},sampling=sampling,**options)


def document(quantity='impedance_real',factor=1.,material=False,sampling=None):
    paired=quantity in api._PAIR
    return Document(source(paired,factor,material,sampling),conductors=(
        {'positive':metal(58e6),'negative':metal(35e6)} if paired else {'signal':metal(58e6)}),
        reference=metal(58e6),ground_thickness=35e-6,quantity=quantity)


def fake(monkeypatch,fail_index=None):
    calls=[]
    def analyze(doc):
        index=len(calls);calls.append(doc.to_dict())
        if index==fail_index:raise ValueError('retained field failure')
        names=tuple(t.name for t in doc.cross_section.section.traces if not t.ground)
        f=np.array(doc.to_dict()['frequency_hz']);value=doc.cross_section.section.traces[0].width*1e5
        return SimpleNamespace(names=names,frequency=f,current_record=lambda:dict(fake=True),
            propagation=lambda:SimpleNamespace(modes=('single',),frequency=f,
                z_characteristic=np.array([[value+1j]]),gamma=np.array([[value+2j]])),
            characteristic=lambda:SimpleNamespace(basis='single-ended',names=names,frequency=f,
                mixed_mode=lambda:SimpleNamespace(z_characteristic=np.array([[[value+1j,2j],[2j,value/4+1j]]]))))
    monkeypatch.setattr(api.FEMShapeTransmissionLineDocument,'analyze',analyze)
    return calls


@pytest.mark.parametrize('quantity',api._QUANTITIES)
def test_field_free_roundtrip_and_source_vectors(monkeypatch,quantity):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    doc=document(quantity);text=doc.dumps();assert text==Document.loads(text).dumps()==normalize_saved(text)
    assert SavedExecutionRequest(text).input_json==text
    np.testing.assert_array_equal(doc.samples(),source(quantity in api._PAIR).samples())
    raw=doc.to_dict();raw['reference']['conductivity']=1;assert doc.dumps()==text


@pytest.mark.parametrize('quantity',api._QUANTITIES)
def test_all_quantities_ordered_and_original_metal_laws(monkeypatch,quantity):
    calls=fake(monkeypatch);doc=document(quantity);result=doc.analyze()
    assert not result.failed and result.summary is not None and len(calls)==2
    assert [row.index for row in result.rows]==[0,1]
    for row,raw in zip(result.rows,calls):
        assert raw['conductors']==doc.to_dict()['conductors'] and raw['reference']==doc.to_dict()['reference']
        assert raw['length_m']==0 and raw['reference_ohms']==50
        assert row.to_dict()['input']==raw and row.to_dict()['current_solver']=={'fake':True}
    assert result.summary['mean']==pytest.approx(np.mean([r.value for r in result.rows]))


@pytest.mark.parametrize('change',['extra','missing','schema','quantity','scalar-pair','metal','reference','dc','duplicate','nonfinite'])
def test_invalid_admission_never_reaches_fields(monkeypatch,change):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid input meshed'))
    raw=document().to_dict()
    if change=='extra':raw['extra']=0
    if change=='missing':raw.pop('reference')
    if change=='schema':raw['schema']='bad'
    if change=='quantity':raw['quantity']='z_diff'
    if change=='scalar-pair':raw['quantity']=api._PAIR[0]
    if change=='metal':raw['conductors']={'wrong':metal(58e6)}
    if change=='reference':raw['reference']={'kind':'perfect'}
    if change=='dc':raw['study']['material_evaluation']['frequency_hz']=0
    if change=='duplicate':
        with pytest.raises(ValueError):Document.loads('{"schema":"x",'+document().dumps()[1:])
        return
    if change=='nonfinite':raw['ground_thickness_m']=float('inf')
    with pytest.raises(ValueError):Document.loads(json.dumps(raw))


def test_all_samples_budgeted_before_fields(monkeypatch):
    raw=document().to_dict();raw['study']['sampling']['count']=3;doc=Document.from_dict(raw)
    calls=fake(monkeypatch)
    for run in (lambda:doc.analyze(max_evaluations=2),lambda:execute_saved(doc.dumps(),max_evaluations=2)):
        with pytest.raises(ValueError,match='max_evaluations'):run()
    assert calls==[]


def test_duplicates_and_later_rows_after_failure_are_preserved(monkeypatch):
    doc=document();monkeypatch.setattr(Document,'samples',lambda self:np.full((3,1),.0004))
    calls=fake(monkeypatch,1);result=doc.analyze()
    assert len(calls)==3 and calls[0]==calls[1]==calls[2]
    assert result.failed==1 and result.summary is None and result.rows[2].complete
    row=result.rows[1];assert row.phase=='extraction' and row.value is None and row.input_json is not None
    assert row.error=='retained field failure' and row.to_dict()['current_solver'] is None


def test_correlated_invalid_rows_keep_order_without_summary(monkeypatch):
    sampling=dict(kind='normal',count=8,seed=3,correlation=[[1.,.5],[.5,1.]],
        variables=[dict(name='width',mean=.0002,std=.0003),dict(name='loss',mean=.02,std=.06)])
    doc=document(material=True,sampling=sampling);calls=fake(monkeypatch);result=doc.analyze()
    assert 0<result.failed<8 and result.summary is None and len(calls)==8-result.failed
    np.testing.assert_array_equal([row.sample_values for row in result.rows],doc.samples())
    assert [row.index for row in result.rows]==list(range(8))


def test_fixed_pitch_is_not_resampled(monkeypatch):
    raw=document(api._PAIR[0]).to_dict()
    # Use the existing constructor to normalize the versioned constraint shape.
    study=ImpedanceStudyDocument('coupled_stripline',source(True).to_dict()['parameters'],
        quantity='z_diff_forward',frequency=2e9,materials={},mesh=MESH,fixed_pitch_m=.0007,
        sampling=source(True).to_dict()['sampling'])
    raw['study']=study.to_dict();calls=fake(monkeypatch);result=Document.from_dict(raw).analyze()
    assert not result.failed
    for row in result.rows:
        p=row.to_dict()['parameters'];assert p['width']+p['gap']==pytest.approx(.0007,rel=1e-15)


def test_interrupt_is_not_a_failed_row(monkeypatch):
    def stop(self):raise KeyboardInterrupt('cancel')
    monkeypatch.setattr(api.FEMShapeTransmissionLineDocument,'analyze',stop)
    with pytest.raises(KeyboardInterrupt):document().analyze()


def test_diagnostics_require_line_document_not_study():
    with pytest.raises(ValueError):SavedExecutionRequest(document().dumps(),diagnostics=('characteristic',))
