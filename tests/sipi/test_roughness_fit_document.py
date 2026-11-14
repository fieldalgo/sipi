# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved fixed-radius fits preserve failed sample gates and common budgets."""
import copy
import numpy as np
import pytest
from sipi.execution import execute_saved, normalize_saved
from sipi.roughness_fit_document import HurayFitDocument
from test_roughness_fit import F, RADII, SIGMA, RATIOS, independent, fit


def document(values=None):
    z=independent()[0] if values is None else values
    return HurayFitDocument(F,resistance=z.real,reactance=z.imag,radii_m=RADII,
                           conductivity=SIGMA,max_error_ratio=1e-9)


def test_roundtrip_normalization_never_optimizes(monkeypatch):
    import sipi.roughness_fit as implementation
    monkeypatch.setattr(implementation,'nnls',lambda *a,**k:pytest.fail('Normalization optimized'))
    monkeypatch.setattr(np.linalg,'svd',lambda *a,**k:pytest.fail('Normalization checked rank'))
    raw=document().to_dict()
    doc=HurayFitDocument.from_dict(raw)
    text=doc.dumps()
    assert len(raw)==9 and raw['weights']==[1.]*len(F)
    assert normalize_saved(text)==HurayFitDocument.loads(text).dumps()==text
    raw['radii_m'][0]=1.;raw['resistance_ohms_per_square'][0]=1.
    doc.to_dict()['weights'].clear()
    assert doc.dumps()==text


@pytest.mark.parametrize('compatible',[True,False])
def test_saved_and_common_execution_keep_candidate_and_acceptance(compatible):
    z,smooth,_=independent()
    if not compatible:z=.8*smooth
    doc=document(z)
    direct=fit(z)
    saved=HurayFitDocument.loads(doc.dumps()).analyze()
    assert saved.to_dict()==direct.to_dict()
    output=execute_saved(doc.dumps())
    assert output['status']=='complete' and output['error'] is None
    assert output['input']==doc.to_dict() and output['result']==direct.to_dict()
    assert output['result']['accepted'] is compatible


def test_actual_rank_failure_and_budget_failure_propagate(monkeypatch):
    import sipi.roughness_fit_document as implementation
    data=document().to_dict()
    data['radii_m']=[1e90,1e100]
    doc=HurayFitDocument.from_dict(data)
    with pytest.raises(ValueError,match='rank|condition'):execute_saved(doc.dumps())
    monkeypatch.setattr(implementation,'fit_huray',lambda *a,**k:pytest.fail('Budget allowed fit'))
    with pytest.raises(ValueError,match='max_evaluations'):
        execute_saved(document().dumps(),max_evaluations=len(F)-1)


@pytest.mark.parametrize('change',[dict(schema='sipi.roughness-fit/2'),dict(weights=None),
    dict(weights=[]),dict(extra=1),dict(radii_m=[]),dict(conductivity=True),
    dict(relative_permeability=-1),dict(max_error_ratio=0),dict(frequency_hz=[0,1e9]),
    dict(resistance_ohms_per_square=[1.]),dict(reactance_ohms_per_square=[float('nan')])],
    ids=['version','null-weights','empty-weights','extra','no-radii','bool-sigma','negative-mu',
         'zero-limit','dc','short-r','nan-x'])
def test_invalid_saved_fields_are_not_silently_defaulted(change):
    data=document().to_dict();data.update(change)
    with pytest.raises(ValueError):HurayFitDocument.from_dict(data)


@pytest.mark.parametrize('key',list(document().to_dict()))
def test_each_saved_field_is_required(key):
    data=document().to_dict();data.pop(key)
    with pytest.raises(ValueError):HurayFitDocument.from_dict(data)


def test_json_rejects_duplicate_and_nonfinite_tokens():
    text=document().dumps()
    with pytest.raises(ValueError):HurayFitDocument.loads(text.replace('"conductivity": 58000000.0',
        '"conductivity": 58000000.0, "conductivity": 1.0'))
    with pytest.raises(ValueError):HurayFitDocument.loads(text.replace('58000000.0','NaN'))


def test_fitted_record_replays_existing_transmission_line_material():
    from sipi.line_model import TransmissionLineDocument
    from test_line_model import section_doc, F as line_frequency
    fitted=document().analyze()
    base=dict(kind='surface',conductivity=SIGMA,relative_permeability=1.,ground_thickness=35e-6,
              roughness=fitted.to_dict()['model'])
    line=TransmissionLineDocument(section_doc(),line_frequency,materials={},conductor=base,length=.03,
                                  schema='sipi.transmission-line/2')
    restored=TransmissionLineDocument.loads(line.dumps()).analyze()
    expected_metal=copy.deepcopy(base)
    expected_metal['roughness']['surface_ratios']=RATIOS.tolist()
    original=TransmissionLineDocument(section_doc(),line_frequency,materials={},conductor=expected_metal,length=.03,
                                      schema='sipi.transmission-line/2').analyze()
    for name in ('R','L','C','G'):
        a,b=getattr(restored,name),getattr(original,name)
        assert np.max(abs(a-b))<=1e-8*max(np.max(abs(b)),np.finfo(float).tiny)
    np.testing.assert_allclose(restored.network.s,original.network.s,rtol=1e-8,atol=1e-12)
    assert line.to_dict()['conductor']['roughness']==fitted.to_dict()['model']
