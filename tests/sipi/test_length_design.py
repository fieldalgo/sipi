# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Sampled loss-limited length boundaries, budgets and preserved failed attempts."""
import json
import numpy as np
import pytest
from sipi.band import assess_band
from sipi.length_design import LineLengthDesignDocument, LengthGoalError
from sipi.network import rlgc_network
from sipi.execution import execute_saved, normalize_saved

F=[0.,1e8,2e8]


def source(alpha=(.1,.2,.3), pair=False):
    n=2 if pair else 1;eye=np.eye(n);alpha=np.asarray(alpha)
    return dict(kind='rlgc',frequency_hz=F,R=(alpha[:,None,None]*50*eye).tolist(),
        G=(alpha[:,None,None]/50*eye).tolist(),L=(2.5e-7*eye).tolist(),C=(1e-10*eye).tolist(),
        length_m=0.,reference_ohms=50.,names=['p','n'] if pair else ['s'])


def limits(pair=False):
    near,far=('d_near','d_far') if pair else ('near:s','far:s')
    return [dict(name='insertion',input_port=near,output_port=far,frequency_hz=[0,2e8],minimum=.8,maximum=None),
            dict(name='reflection',input_port=near,output_port=near,frequency_hz=[0,2e8],minimum=None,maximum=1e-10)]


def document(**kwargs):
    args=dict(network=source(),limits=limits(),bounds=[0,2],tolerance=1e-7,max_evaluations=40)
    args.update(kwargs);return LineLengthDesignDocument(**args)


@pytest.mark.parametrize('pair',[False,True])
def test_distortionless_length_boundary_matches_closed_form_and_replays(pair):
    doc=document(network=source(pair=pair),limits=limits(pair),basis='mixed-mode' if pair else 'single-ended')
    restored=LineLengthDesignDocument.loads(doc.dumps())
    assert restored.dumps()==doc.dumps()==normalize_saved(doc.dumps())
    result=restored.solve();expected=-np.log(.8)/.3
    assert result.feasible_length_m<=expected+1e-10
    assert result.infeasible_length_m>=expected-1e-10
    assert 0<result.infeasible_length_m-result.feasible_length_m<=1e-7
    assert abs(result.feasible_length_m-expected)<=1e-7+1e-10
    assert result.feasible.passed and not result.infeasible.passed
    for length,assessment in [(result.feasible_length_m,result.feasible),(result.infeasible_length_m,result.infeasible)]:
        np.testing.assert_allclose(assessment.checks[0].magnitude,np.exp(-np.array([.1,.2,.3])*length),rtol=1e-10)
    assert len(result.history)<=40
    assert result.input_json==doc.dumps()
    output=execute_saved(doc.dumps());assert output['status']=='complete'
    assert output['result']==result.to_dict()
    json.dumps(output,allow_nan=False)


def test_distinct_bands_joint_constraints_determine_the_active_boundary():
    constraints=limits();constraints[0].update(frequency_hz=[0,1e8],minimum=.9)
    constraints.append(dict(name='upper-band',input_port='near:s',output_port='far:s',
                            frequency_hz=[1e8,2e8],minimum=.7,maximum=None))
    result=document(limits=constraints).solve()
    expected=min(-np.log(.9)/.2,-np.log(.7)/.3)
    assert abs(result.feasible_length_m-expected)<=1e-7+1e-10
    assert not result.infeasible.checks[0].passed and result.infeasible.checks[2].passed


def test_skrf_independently_confirms_feasible_and_infeasible_samples():
    from crosscheck import Stopwatch, emit, make_record, observable, require_tool
    import importlib.metadata as metadata
    skrf=require_tool('scikit-rf');clock=Stopwatch();doc=document()
    with clock('openphysics'): result=doc.solve()
    error=0.
    for length,assessment in [(result.feasible_length_m,result.feasible),(result.infeasible_length_m,result.infeasible)]:
        with clock('reference'):
            medium=skrf.media.DefinedGammaZ0(frequency=skrf.Frequency.from_f(F,unit='hz'),
                gamma=np.array([.1,.2,.3])+2j*np.pi*np.array(F)/2e8,z0=50)
            peer=medium.line(length,unit='m')
        error=max(error,float(np.max(abs(assessment.network.s-peer.s))))
        assert bool(np.all(abs(peer.s[:,1,0])>=.8))==assessment.passed
    record=make_record(case='sampled-loss-length-boundary',physics='uniform RLGC length with sampled S limits',
        api='sipi.length_design.LineLengthDesignDocument',discretization='bisection of an explicit feasible/infeasible bracket',
        tool='scikit-rf',tool_discretization='independent DefinedGammaZ0 endpoints',
        matched=['RLGC, attenuation, phase velocity, frequency, reference and endpoint lengths'],
        not_matched=['no continuous-frequency extrema or global maximum for arbitrary mismatched lines'],
        observables=[observable('S','dimensionless','maximum absolute difference',error,1e-10)],
        analytical_acceptance='length=-log(0.8)/0.3; bracket width <=1e-7 m',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<1e-10


@pytest.mark.parametrize('kwargs,match',[
    (dict(bounds=[1,2]),'lower length'),(dict(bounds=[0,.1]),'upper length'),
    (dict(max_evaluations=2),'budget'),
])
def test_unaccepted_bracket_and_budget_preserve_completed_history(kwargs,match):
    doc=document(**kwargs)
    with pytest.raises(LengthGoalError,match=match) as caught:doc.solve()
    assert len(caught.value.history)==2
    out=execute_saved(doc.dumps())
    assert out['status']=='failed' and out['error']['type']=='LengthGoalError'
    assert len(out['error']['history'])==2 and out['error']['failed_length_m'] is None


def test_budget_gate_before_design_evaluation_and_no_hidden_network_evaluations(monkeypatch):
    import sipi.length_design as module
    doc=document();original=module._network_input;calls=[]
    def counted(data):
        calls.append(data['length_m']);return original(data)
    monkeypatch.setattr(module,'_network_input',counted)
    with pytest.raises(ValueError,match='budget'):execute_saved(doc.dumps(),max_evaluations=2)
    assert calls==[]
    result=doc.solve()
    assert calls==[row.length_m for row in result.history]


def test_failed_candidate_has_explicit_length_cause_and_completed_history(monkeypatch):
    import sipi.length_design as module
    doc=document();original=module._network_input
    def fail(data):
        if data['length_m']==1:raise ValueError('synthetic numerical failure')
        return original(data)
    monkeypatch.setattr(module,'_network_input',fail)
    out=execute_saved(doc.dumps())
    assert out['status']=='failed'
    assert out['error']['failed_length_m']==1
    assert out['error']['cause_type']=='ValueError'
    assert len(out['error']['history'])==2
    assert 'synthetic numerical failure' in out['error']['message']


def test_only_endpoint_evaluations_when_initial_interval_is_already_small():
    doc=document(bounds=[.7,.8],tolerance=.11,max_evaluations=2)
    result=doc.solve();assert len(result.history)==2
    assert result.feasible_length_m==.7 and result.infeasible_length_m==.8


@pytest.mark.parametrize('change',[
    lambda d:d.update(schema='sipi.line-length-design/2'),lambda d:d.update(extra=1),
    lambda d:d['network'].update(length_m=.1),lambda d:d['network'].update(kind='expression'),
    lambda d:d.update(bounds_m=[-1,2]),lambda d:d.update(bounds_m=[0,0]),
    lambda d:d.update(bounds_m=[2,0]),lambda d:d.update(bounds_m=[0]),
    lambda d:d.update(bounds_m=[False,2]),lambda d:d.update(bounds_m=[0,float('inf')]),
    lambda d:d.update(tolerance_m=0),lambda d:d.update(tolerance_m=True),
    lambda d:d.update(max_evaluations=1),lambda d:d.update(max_evaluations=2.),
    lambda d:d.update(basis='mixed-mode'),lambda d:d.update(limits=[]),
])
def test_strict_length_document_rejects_malformed_inputs(change):
    data=document().to_dict();change(data)
    with pytest.raises(ValueError):LineLengthDesignDocument.from_dict(data)


def test_saved_inputs_are_snapshots_and_duplicate_keys_rejected():
    values=source();doc=document(network=values);saved=doc.dumps()
    values['R'][0][0][0]=999;out=doc.to_dict();out['limits'][0]['minimum']=99
    assert doc.dumps()==saved
    with pytest.raises(ValueError):LineLengthDesignDocument.loads(saved.replace('"basis":','"basis":"single-ended","basis":',1))


def test_unrepresentable_midpoint_is_rejected_without_extra_evaluations(monkeypatch):
    import sipi.length_design as module
    from sipi.network import LineNetwork
    lower=1.;upper=np.nextafter(lower,np.inf)
    doc=document(bounds=[lower,float(upper)],tolerance=1e-18)
    def network_at_length(data):
        s=np.zeros((3,2,2),complex);s[:,1,0]=.9 if data['length_m']==lower else .7
        return LineNetwork(F,s,[50,50],('near:s','far:s')),data,np.array(F),('near:s','far:s')
    monkeypatch.setattr(module,'_network_input',network_at_length)
    with pytest.raises(LengthGoalError,match='resolution exhausted') as error:doc.solve()
    assert len(error.value.history)==2
