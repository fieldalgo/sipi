# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual bounded FEM goals, independent characteristic roots and failed evidence."""
import json
import numpy as np
import pytest
from sipi.fem_shape_line import FEMShapeTransmissionLineDocument as Document,FEMShapeLineError
from sipi.fem_shape_conductor import FEMShapeCurrentError
from sipi.fem_shape_goal import seek_fem_shape_line_quantity as seek,FEMShapeLineQuantityGoalError as Error
from test_fem_shape_goal import factory
from test_fem_shape_study_physical import independent


@pytest.fixture(scope='module')
def observed():
    return {q:seek(lambda w:factory(w,q),[.00039,.00041],target,quantity=q,tolerance=.2,max_evaluations=12)
        for q,target in [('impedance_real',70.35),('differential_forward_impedance_real',92.8)]}


def test_real_goals_independent_quantities_and_frozen_refinement(observed,record_property):
    rows={}
    for quantity,result in observed.items():
        assert .00039<=result.parameter<=.00041 and len(result.history)<=12
        assert abs(result.residual)<=.2 and abs(result.refined_residual)<=.2
        assert abs(result.mesh_change)/result.refined_value<=.005
        assert result.history[0].parameter==.00039 and result.history[1].parameter==.00041
        assert result.history[-1].stage=='refinement' and result.history[-1].parameter==result.parameter
        for line,value in ((result.result,result.value),(result.refined_result,result.refined_value)):
            assert value==pytest.approx(independent(line,quantity),rel=1e-10,abs=0)
        chosen=result.document.to_dict();refined=result.refined_document.to_dict()
        settings=result.document.cross_section.section.mesh_settings(**result.document.cross_section.mesh_options)
        for key in ('edge_size','far_size','grade'):settings[key]/=2
        chosen['cross_section']['mesh']=settings;assert chosen==refined
        rows[quantity]=dict(design=result.to_dict(),selected={k:getattr(result.result,k).tolist() for k in ('R','L','G','C')},
            refined={k:getattr(result.refined_result,k).tolist() for k in ('R','L','G','C')})
    record_property('fem_shape_goals',json.dumps(rows,allow_nan=False))


@pytest.mark.parametrize('quantity',['attenuation','common_forward_impedance_real'])
def test_other_goal_quantities_use_actual_extracted_endpoint_and_refined_fields(observed,monkeypatch,quantity):
    parent='impedance_real' if quantity=='attenuation' else 'differential_forward_impedance_real'
    original=observed[parent];value=independent(original.result,quantity);refined_value=independent(original.refined_result,quantity)
    assert abs(refined_value-value)/refined_value<=.005
    # Reuse actual extracted fields only for search transport; this is not a new
    # material/geometry solve or a second physical inverse-recovery study.
    calls=[]
    def analyze(doc):
        calls.append(doc.dumps());line=original.refined_result if len(calls)==3 else original.result
        from dataclasses import replace
        return replace(line,input_json=doc.dumps())
    monkeypatch.setattr(Document,'analyze',analyze)
    result=seek(lambda w:factory(w,quantity),[.00039,.00041],value,quantity=quantity,
        tolerance=max(abs(refined_value-value)*2,1e-10),max_evaluations=3)
    assert len(calls)==len(result.history)==3
    assert result.value==pytest.approx(value,rel=1e-10) and result.refined_value==pytest.approx(refined_value,rel=1e-10)


@pytest.mark.parametrize('partial',[False,True])
def test_later_typed_failure_preserves_history_input_and_partial_current(observed,monkeypatch,partial):
    original=observed['differential_forward_impedance_real'];cur=original.result.current_factors;calls=[]
    def analyze(doc):
        calls.append(doc.dumps())
        if len(calls)==1:
            from dataclasses import replace
            return replace(original.result,input_json=doc.dumps())
        cause=FEMShapeCurrentError('original partial',stage='capacitance-differences',base=cur.base,
            extension_parts=cur.extension_parts,samples=cur.samples[:1],request=(0,0,0,1,cur.step_m)) if partial else ValueError('dielectric failed')
        raise FEMShapeLineError(cause,stage='current' if partial else 'dielectric',input_json=doc.dumps(),
            factors=None if partial else cur,mesh_observation=original.result.mesh_observation)
    monkeypatch.setattr(Document,'analyze',analyze)
    with pytest.raises(Error) as caught:
        seek(lambda w:factory(w,'differential_forward_impedance_real'),[.00039,.00041],92.8,
            quantity='differential_forward_impedance_real',tolerance=.2)
    error=caught.value;assert error.attempts==2 and len(error.history)==1 and error.stage=='search/extraction'
    assert error.failed_parameter==.00041 and error.input_json==calls[-1]
    details=error.cause_details;assert details==error.__cause__.to_dict() and error.current_solver is None
    if partial:
        assert len(details['partial_current']['samples'])==1 and details['partial_current']['finite_difference_factors_per_m'] is None
    else:assert details['current_solver']==original.result.current_record()
    assert json.loads(json.dumps(error.to_dict(),allow_nan=False))==error.to_dict()
