# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual iid finite-domain rows with independent binomial and network checks."""
import json
import numpy as np
import pytest
from sipi.shape_panel_pair_study import ShapePanelForwardPairStudyDocument
from sipi.shape_panel_pair_yield import ShapePanelForwardPairYieldDocument,assess_shape_panel_pair_yield
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument,ShapePanelLineError
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from test_execution_record import ARTIFACTS
from test_panel_pair_yield import Q
from test_yield_assessment import independent_interval
from test_shape_panel_pair_study_physical import document as corners,identities
from test_shape_panel_pair_goal_physical import snapshot

LIMITS={Q[0]:dict(minimum=124.,maximum=130.),Q[1]:dict(minimum=41.,maximum=43.)}


def document(coated=False):
    raw=corners(coated).to_dict()
    raw['study']['study']['sampling'].update(kind='uniform',count=4,seed=123)
    source=ShapePanelForwardPairStudyDocument.from_dict(raw)
    return ShapePanelForwardPairYieldDocument(source,acceptance=LIMITS,confidence=.95,minimum_yield=.8)


@pytest.mark.parametrize('coated',[False,True],ids=['bulk','coated'])
def test_actual_iid_joint_event_networks_and_complete_partial_receipts(coated,monkeypatch,record_property):
    doc=document(coated);result=doc.analyze(max_evaluations=4);study=result.study
    record_property('shape_yield_actual',json.dumps(result.to_dict(),allow_nan=False))
    assert study.failed==0 and len(study.rows)==4
    record_property('shape_yield_fields',json.dumps([snapshot(r.result) for r in study.rows],allow_nan=False))
    record_property('shape_yield_independent',json.dumps([identities(r.result,coated) for r in study.rows]))
    labels=['pass' if 124.<=r.values[0]<=130. and 41.<=r.values[1]<=43. else 'fail' for r in study.rows]
    assert list(result.classifications)==labels and result.unresolved==0
    low,high=independent_interval(labels.count('pass'),4,.95)
    np.testing.assert_allclose(result.confidence_interval,[low,high],rtol=0,atol=1e-12)
    assert result.goal_status==('pass' if low>=.8 else 'fail' if high<.8 else 'undetermined')
    assert assess_shape_panel_pair_yield(study,acceptance=LIMITS,minimum_yield=.8).to_dict()==result.to_dict()
    values={r.input_json:r.result for r in study.rows}
    for failed_index in (None,1):
        calls=[]
        def replay(self):
            calls.append(self.dumps());line=values[self.dumps()]
            if len(calls)-1==failed_index:
                raise ShapePanelLineError(ArithmeticError('retained actual-row diagnostic failure'),
                    stage='network',input_json=self.dumps(),factors=line.current_factors,settings=line.panel_settings)
            return line
        monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',replay)
        request=SavedExecutionRequest(doc.dumps(),max_evaluations=4);receipt=request.run();out=receipt['execution']
        assert calls==[r.input_json for r in study.rows]
        assert out['status']==('complete' if failed_index is None else 'incomplete')
        if failed_index is None:assert out['result']==result.to_dict()
        else:
            report=out['result'];assert report['unresolved']==1 and report['count']==4
            row=report['rows'][1];assert row['classification']=='unresolved'
            assert row['cause_details']['current_solver']==study.rows[1].to_dict()['current_solver']
            assert row['cause_details']['message']=='retained actual-row diagnostic failure'
            lower=independent_interval(report['passed'],4,.95)[0]
            upper=independent_interval(report['passed']+1,4,.95)[1]
            np.testing.assert_allclose(report['confidence_interval'],[lower,upper],rtol=0,atol=1e-12)
        saved=SavedExecutionRecord(request,receipt,run_id='shape-yield:actual',artifacts=ARTIFACTS)
        monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore solved'))
        assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt
