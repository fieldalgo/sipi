# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent dispersive-grid identities and identical single-frequency fields."""
import json
import numpy as np
import pytest
from sipi.constants import epsilon_0,mu_0
from sipi.dielectric import DebyeDielectric,dielectric_to_dict
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.shape_sampled_panel_pair_study import ShapeSampledPanelForwardPairStudyDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument,shape_current_record
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from test_execution_record import ARTIFACTS
from test_shape_panel_pair_study_physical import document as single_study
from test_shape_panel_pair_goal_physical import independent,snapshot
from test_layered_metal import transfer

F=[1e9,2e9,4e9]


def document(coated=False):
    raw=single_study(coated).to_dict()['study']
    raw['schema']='sipi.sampled-panel-forward-pair-study/2' if coated else 'sipi.sampled-panel-forward-pair-study/1'
    raw['frequency_hz']=F
    model=dielectric_to_dict(DebyeDielectric(3.,(.7,),(1e9,)))
    raw['study']['material_evaluation']['materials']={name:model for name in ('substrate','air')}
    return ShapeSampledPanelForwardPairStudyDocument(SampledPanelForwardPairStudyDocument.from_dict(raw))


@pytest.fixture(scope='module',params=[False,True],ids=['bulk','coated'])
def actual(request):
    doc=document(request.param)
    return request.param,doc,doc.analyze(max_evaluations=4)


def identities(line,coated):
    f=np.array(F);omega=2*np.pi*f
    eps=3.+.7/(1+1j*f/1e9)
    np.testing.assert_allclose(line.dielectric.C_complex,eps[:,None,None]*line.current_factors.C0,rtol=1e-10,atol=0)
    np.testing.assert_allclose(line.G,-omega[:,None,None]*eps[:,None,None].imag*line.current_factors.C0,rtol=1e-10,atol=0)
    np.testing.assert_allclose(line.dielectric.L@line.current_factors.C0,mu_0*epsilon_0*np.eye(2),rtol=1e-10,atol=1e-28)
    surface=np.array([transfer(value) for value in f]) if coated else np.sqrt(1j*omega*mu_0/58e6)
    np.testing.assert_allclose(line.R+1j*omega[:,None,None]*line.conductor.L_internal,
        surface[:,None,None]*line.current_factors.total,rtol=1e-10,atol=0)
    assert len(line.current_factors.samples)==13
    return independent(line)


def test_actual_geometry_rows_keep_dispersive_grid_and_independent_networks(actual,record_property):
    coated,doc,result=actual
    record_property('shape_grid_actual',json.dumps(result.to_dict(),allow_nan=False))
    assert result.failed==0 and len(result.rows)==4 and result.frequencies==tuple(F)
    record_property('shape_grid_fields',json.dumps([snapshot(row.result) for row in result.rows],allow_nan=False))
    record_property('shape_grid_independent',json.dumps([identities(row.result,coated) for row in result.rows]))
    np.testing.assert_array_equal([r.sample_values for r in result.rows],doc.samples())


def test_selected_row_grid_matches_every_single_frequency(actual,record_property):
    _,_,study=actual;row=study.rows[0];single=[]
    for i,f in enumerate(F):
        data=json.loads(row.input_json);data['line']['line']['frequency_hz']=[f]
        line=ShapePanelTransmissionLineDocument.from_dict(data).analyze();single.append(snapshot(line))
        record_property('shape_grid_single_'+str(i),json.dumps(single[-1],allow_nan=False))
        assert shape_current_record(line.current_factors,line.panel_settings)==row.to_dict()['current_solver']
        for key in ('R','L','C','G'):
            np.testing.assert_allclose(getattr(line,key)[0],getattr(row.result,key)[i],rtol=1e-12,atol=0)
        np.testing.assert_allclose(line.characteristic().mixed_mode().z_characteristic[0].diagonal().real,
            row.values[i],rtol=1e-12,atol=0)


def test_actual_saved_receipt_replays_entire_rows_without_new_fields(actual,monkeypatch):
    _,doc,result=actual;values={r.input_json:r.result for r in result.rows};calls=[]
    def replay(self):calls.append(self.dumps());return values[self.dumps()]
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',replay)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=4);receipt=request.run()
    assert receipt['execution']['status']=='complete' and receipt['execution']['result']==result.to_dict()
    assert calls==[r.input_json for r in result.rows]
    saved=SavedExecutionRecord(request,receipt,run_id='shape-grid:actual',artifacts=ARTIFACTS)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt
