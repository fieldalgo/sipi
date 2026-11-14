# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual attenuation-material and common-launch geometric inverse recovery."""
import json
import numpy as np
import pytest
from sipi.fem_shape_goal_document import FEMShapeLineQuantityDesignDocument
from sipi.fem_shape_line import FEMShapeTransmissionLineDocument
import sipi.fem_shape_conductor as current
from test_fem_shape_study import document as study
from test_fem_shape_study_physical import independent


@pytest.mark.parametrize('quantity,target,tolerance',[
    ('attenuation',1.,.01),('common_forward_impedance_real',45.8,.1)])
def test_actual_material_and_common_launch_goals(quantity,target,tolerance,monkeypatch,record_property):
    source=study(quantity,material=quantity=='attenuation')
    goal=FEMShapeLineQuantityDesignDocument(source,target=target,tolerance=tolerance,max_evaluations=16)
    calls=[];matrix_calls=[];analyze=FEMShapeTransmissionLineDocument.analyze;capacitance=current.capacitance_matrix
    def observed(doc):
        result=analyze(doc);calls.append((doc.dumps(),result));return result
    def cap(*args,**kw):
        matrix_calls.append(1);return capacitance(*args,**kw)
    monkeypatch.setattr(FEMShapeTransmissionLineDocument,'analyze',observed)
    monkeypatch.setattr(current,'capacitance_matrix',cap)
    result=goal.solve()
    assert len(calls)==len(result.history)<=16 and len(result.history)>=3
    assert len(matrix_calls)==len(calls)*(16 if quantity=='attenuation' else 24)
    assert abs(result.residual)<=tolerance and abs(result.refined_residual)<=tolerance
    assert abs(result.mesh_change)/result.refined_value<=.005
    rows=[]
    for evaluation,(text,line) in zip(result.history,calls):
        assert evaluation.input_json==text
        reference=independent(line,quantity)
        assert evaluation.value==pytest.approx(reference,rel=1e-10,abs=0)
        raw=json.loads(text)
        if quantity=='attenuation':
            loss=raw['materials']['dielectric']['parameters']['tan_delta']
            assert loss==evaluation.parameter
            np.testing.assert_allclose(line.G,2*np.pi*2e9*loss*line.C,rtol=1e-12,atol=0)
            if evaluation.stage=='search':
                for name in ('R','L','C'):
                    np.testing.assert_array_equal(getattr(line,name),getattr(calls[0][1],name))
                np.testing.assert_array_equal(line.current_factors.parts,calls[0][1].current_factors.parts)
        else:
            assert raw['cross_section']['traces'][0]['width']==evaluation.parameter
            assert raw['cross_section']['traces'][1]['width']==evaluation.parameter
        rows.append(dict(evaluation=evaluation.to_dict(),independent=reference,
            R=line.R.tolist(),L=line.L.tolist(),G=line.G.tolist(),C=line.C.tolist(),current=line.current_record()))
    record_property('fem_actual_launch_goal',json.dumps(dict(input=goal.to_dict(),design=result.to_dict(),
        attempts=len(calls),capacitance_requests=len(matrix_calls),rows=rows),allow_nan=False))
