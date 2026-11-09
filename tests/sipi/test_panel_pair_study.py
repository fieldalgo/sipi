# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json,statistics
from dataclasses import FrozenInstanceError
import numpy as np
import pytest
import sipi.panel_pair_study as module
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi import CrossSection
from sipi.study import ImpedanceStudyDocument
from sipi.panel_line import PanelTransmissionLineDocument
from test_pair_line_goal_document import source
from test_panel_pair_goal import synthetic,quantities

Q=('differential_forward_impedance_real','common_forward_impedance_real')


def document(sampling=None):
    raw=source().to_dict()
    if sampling is not None:raw['sampling']=sampling
    return PanelForwardPairStudyDocument(raw,conductor={'kind':'perfect'})


def expected_statistics(values):
    ordered=sorted(values);n=len(values)
    def quantile(p):
        location=(n-1)*p;low=int(np.floor(location));high=int(np.ceil(location))
        return ordered[low]+(ordered[high]-ordered[low])*(location-low)
    return dict(minimum=min(values),maximum=max(values),mean=statistics.mean(values),sample_std=statistics.stdev(values),p05=quantile(.05),p95=quantile(.95))


def test_two_quantities_per_extraction_and_independent_statistics(monkeypatch):
    calls=synthetic(monkeypatch);doc=document();result=doc.analyze(max_evaluations=4)
    assert not result.failed and len(calls)==len(result.rows)==4
    assert result.variable_names==('left_width','gap')
    for i,(row,values) in enumerate(zip(result.rows,doc.samples())):
        assert row.index==i and row.phase=='complete' and row.sample_values==tuple(values)
        np.testing.assert_allclose(row.values,quantities(values[0]/.3e-3,values[1]/.2e-3),rtol=1e-12)
        assert row.input_json==calls[i] and row.result.input_json==calls[i]
    for i,q in enumerate(Q):
        expected=expected_statistics([row.values[i] for row in result.rows])
        for key,value in expected.items():assert result.summary[q][key]==pytest.approx(value,rel=1e-12)
    json.dumps(result.to_dict(),allow_nan=False)
    with pytest.raises(TypeError):result.summary[Q[0]]['mean']=0
    with pytest.raises(FrozenInstanceError):result.rows[0].index=999


def test_field_free_roundtrip_and_copies(monkeypatch):
    def forbidden(*a,**k):pytest.fail('normalization reached field work')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    doc=document();text=doc.dumps();raw=doc.to_dict();raw['panel']['panels_per_edge']=64
    assert PanelForwardPairStudyDocument.loads(text).dumps()==text and doc.dumps()==text


def test_duplicate_representable_samples_are_not_deduplicated(monkeypatch):
    calls=synthetic(monkeypatch);low=.3e-3
    doc=document(dict(kind='sweep',count=4,variables=[dict(name='left_width',lower=low,upper=float(np.nextafter(low,np.inf)))]))
    samples=doc.samples();assert len(np.unique(samples[:,0]))<4
    result=doc.analyze(max_evaluations=4)
    assert len(calls)==len(result.rows)==4 and not result.failed
    assert [r.index for r in result.rows]==list(range(4))
    np.testing.assert_array_equal([r.sample_values for r in result.rows],samples)


def test_correlated_failures_preserve_every_original_row(monkeypatch):
    calls=synthetic(monkeypatch)
    sampling=dict(kind='normal',count=8,seed=3,correlation=[[1.,.5],[.5,1.]],variables=[dict(name='left_width',mean=.2e-3,std=.3e-3),dict(name='gap',mean=.2e-3,std=.3e-3)])
    doc=document(sampling);result=doc.analyze(max_evaluations=8)
    assert 0<result.failed<8 and result.summary is None
    assert len(calls)==8-result.failed
    assert [r.index for r in result.rows]==list(range(8))
    np.testing.assert_array_equal([r.sample_values for r in result.rows],doc.samples())
    for row,(width,gap) in zip(result.rows,doc.samples()):
        assert row.complete==(width>0 and gap>0)
        if row.complete:np.testing.assert_allclose(row.values,quantities(width/.3e-3,gap/.2e-3),rtol=1e-12)
        else:assert row.phase=='input' and row.input_json is None and row.values is None
    assert PanelForwardPairStudyDocument.loads(doc.dumps()).dumps()==doc.dumps()


@pytest.mark.parametrize('phase',['parameters','materials','input','extraction','diagnostic'])
def test_failed_row_never_stops_following_rows(monkeypatch,phase):
    doc=document();calls=synthetic(monkeypatch,fail_at=2 if phase=='extraction' else None)
    if phase in ('parameters','materials','input'):
        name=dict(parameters='_parameters',materials='_sample_material',input='_line_from_inputs')[phase];original=getattr(module,name);seen=[]
        def fail_second(*a,**k):
            seen.append(1)
            if len(seen)==2:raise ArithmeticError('original row failure')
            return original(*a,**k)
        monkeypatch.setattr(module,name,fail_second)
    if phase=='diagnostic':
        original=PanelTransmissionLineDocument.analyze
        def diagnostic(self):
            line=original(self)
            if len(calls)==2:
                def fail():raise ArithmeticError('original row failure')
                line.characteristic=fail
            return line
        monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',diagnostic)
    result=doc.analyze(max_evaluations=4);row=result.rows[1]
    assert result.failed==1 and len(result.rows)==4 and result.summary is None
    assert row.phase==phase and row.error_type=='ArithmeticError' and row.values is None
    assert all(r.complete for i,r in enumerate(result.rows) if i!=1)
    assert (row.parameters_json is not None)==(phase!='parameters')
    assert (row.material_evaluation_json is not None)==(phase not in ('parameters','materials'))
    assert (row.input_json is not None)==(phase in ('extraction','diagnostic'))
    assert (row.result is not None)==(phase=='diagnostic')


@pytest.mark.parametrize('budget',[0,1,True,4.,10001,3])
def test_budget_control_and_count_before_fields(monkeypatch,budget):
    doc=document()
    def forbidden(*a,**k):pytest.fail('refused budget reached fields')
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    with pytest.raises(ValueError):doc.analyze(max_evaluations=budget)


@pytest.mark.parametrize('where',['root','study','panel'])
@pytest.mark.parametrize('kind',['extra','missing'])
def test_strict_keys(where,kind):
    raw=document().to_dict();target=raw if where=='root' else raw[where]
    if kind=='extra':target['unexpected']=1
    else:target.pop(next(iter(target)))
    with pytest.raises(ValueError):PanelForwardPairStudyDocument.from_dict(raw)


def test_duplicate_nonfinite_and_schema_rejection():
    text=document().dumps()
    for bad in [text.replace('"ground_modes": 512','"ground_modes": 512, "ground_modes": 512'),text.replace('"ground_modes": 512','"ground_modes": NaN'),text.replace('sipi.panel-forward-pair-study/1','sipi.panel-forward-pair-study/2')]:
        with pytest.raises(ValueError):PanelForwardPairStudyDocument.loads(bad)


@pytest.mark.parametrize('kind',['exception','basis','names','frequency','mixed_names','mixed_frequency','nan','negative','shape','line_names','line_frequency'])
def test_invalid_diagnostics_fail_the_whole_pair(monkeypatch,kind):
    from test_panel_pair_goal import diagnostic_fixture
    diagnostic_fixture(monkeypatch,kind);original=PanelTransmissionLineDocument.analyze;calls=[]
    def counted(self):calls.append(self.dumps());return original(self)
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',counted)
    result=document().analyze(max_evaluations=4)
    assert result.failed==len(calls)==4 and result.summary is None
    for row in result.rows:
        assert row.values is None and row.phase==('extraction' if kind.startswith('line_') else 'diagnostic')
        assert row.input_json and row.result is not None
        assert row.error_type==('ArithmeticError' if kind=='exception' else 'ValueError')


def test_overflowing_sample_generation_rejects_before_fields(monkeypatch):
    sampling=dict(kind='normal',count=8,seed=3,correlation=[[1.]],variables=[dict(name='left_width',mean=1e308,std=1e308)])
    doc=document(sampling)
    def forbidden(*a,**k):pytest.fail('invalid samples reached fields')
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    with np.errstate(over='ignore',invalid='ignore'):
        with pytest.raises(ValueError):doc.analyze(max_evaluations=8)


def test_empty_error_message_is_still_a_failure(monkeypatch):
    def fail(self):raise ArithmeticError()
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',fail)
    result=document().analyze(max_evaluations=4)
    assert result.failed==4 and result.summary is None
    assert all(row.error=='' and not row.complete and row.values is None for row in result.rows)


def test_fixed_pitch_and_material_values_reach_each_line(monkeypatch):
    from sipi.dielectric import ConstantDielectric,dielectric_to_dict
    calls=synthetic(monkeypatch);raw=source().to_dict();raw['schema']='sipi.impedance-study/4';raw['fixed_pitch_m']=.95e-3
    raw['material_evaluation']['materials']={'substrate':dielectric_to_dict(ConstantDielectric(4.,.02))}
    raw['material_variables']={'dk':dict(region='substrate',path=['eps_r'])}
    raw['sampling']['variables']=[dict(name='left_width',lower=.4e-3,upper=.8e-3),dict(name='dk',lower=3.,upper=5.)]
    doc=PanelForwardPairStudyDocument(raw,conductor={'kind':'perfect'},panels_per_edge=16)
    result=doc.analyze(max_evaluations=4)
    assert not result.failed and len(calls)==4
    for row,(width,eps) in zip(result.rows,doc.samples()):
        data=json.loads(row.input_json);line=data['line'];traces=line['cross_section']['traces']
        assert traces[1]['x']-traces[0]['x']==pytest.approx(.95e-3,rel=1e-12)
        assert line['materials']['substrate']['parameters']['eps_r']==eps
        assert json.loads(row.material_evaluation_json)['materials']['substrate']['parameters']['eps_r']==eps
        assert data['panel']['panels_per_edge']==16
        assert row.sample_values==(width,eps)


def test_sampling_does_not_require_unrequested_refinement_admission(monkeypatch):
    def forbidden(*a,**k):pytest.fail('normalization solved a field')
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    doc=PanelForwardPairStudyDocument(source(),conductor={'kind':'perfect'},panels_per_edge=256)
    assert doc.to_dict()['panel']['panels_per_edge']==256
    assert PanelForwardPairStudyDocument.loads(doc.dumps()).dumps()==doc.dumps()


def test_zero_thickness_nominal_input_is_not_silently_converted():
    raw=source().to_dict();raw['parameters']['left_thickness']=0.
    with pytest.raises(ValueError,match='positive conductor thickness'):
        PanelForwardPairStudyDocument(raw,conductor={'kind':'perfect'})


def test_common_execution_matches_direct_and_keeps_input(monkeypatch):
    from sipi.execution import execute_saved, normalize_saved, saved_schemas
    synthetic(monkeypatch);doc=document();expected=doc.analyze(max_evaluations=4).to_dict()
    output=execute_saved(doc.dumps(),max_evaluations=4)
    assert output['status']=='complete' and output['error'] is None
    assert output['input']==doc.to_dict() and output['result']==expected
    assert normalize_saved(doc.dumps())==doc.dumps()
    assert 'sipi.panel-forward-pair-study/1' in saved_schemas()
    json.dumps(output,allow_nan=False)


@pytest.mark.parametrize('mode',['budget','diagnostics','input_bytes'])
def test_transport_limits_reject_before_extraction(monkeypatch,mode):
    from sipi.execution import execute_saved
    doc=document()
    def forbidden(*a,**k):pytest.fail('refused transport reached fields')
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    options={'max_evaluations':3} if mode=='budget' else ({'diagnostics':['characteristic']} if mode=='diagnostics' else {'max_input_bytes':16})
    with pytest.raises(ValueError):execute_saved(doc.dumps(),**options)


@pytest.mark.parametrize('phase',['parameters','materials','input','extraction','diagnostic'])
def test_transport_keeps_incomplete_rows_and_original_causes(monkeypatch,phase):
    from sipi.execution import execute_saved
    doc=document();calls=synthetic(monkeypatch,fail_at=2 if phase=='extraction' else None)
    if phase in ('parameters','materials','input'):
        name=dict(parameters='_parameters',materials='_sample_material',input='_line_from_inputs')[phase]
        original=getattr(module,name);seen=[]
        def fail_second(*a,**k):
            seen.append(1)
            if len(seen)==2:raise ArithmeticError('retained row cause')
            return original(*a,**k)
        monkeypatch.setattr(module,name,fail_second)
    elif phase=='diagnostic':
        original=PanelTransmissionLineDocument.analyze
        def fail_diagnostic(self):
            line=original(self)
            if len(calls)==2:
                def fail():raise ArithmeticError('retained row cause')
                line.characteristic=fail
            return line
        monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',fail_diagnostic)
    output=execute_saved(doc.dumps(),max_evaluations=4);result=output['result']
    assert output['status']=='incomplete' and output['error'] is None
    assert output['input']==doc.to_dict() and result['summary'] is None and result['failed']==1
    assert result['count']==4 and [row['index'] for row in result['rows']]==list(range(4))
    row=result['rows'][1]
    assert row['phase']==phase and row['error_type']=='ArithmeticError' and row['values_ohm'] is None
    assert row['error']==('retained physical failure' if phase=='extraction' else 'retained row cause')
    assert row['sample_values']==doc.samples()[1].tolist()
    assert (row['parameters'] is not None)==(phase!='parameters')
    assert (row['material_evaluation'] is not None)==(phase not in ('parameters','materials'))
    assert (row['input'] is not None)==(phase in ('extraction','diagnostic'))
    assert all(item['phase']=='complete' for i,item in enumerate(result['rows']) if i!=1)
    json.dumps(output,allow_nan=False)


def test_old_single_quantity_yield_does_not_silently_accept_paired_source():
    from sipi.line_yield import LineQuantityYieldDocument
    with pytest.raises(ValueError):
        LineQuantityYieldDocument(document().to_dict(),minimum=80.,maximum=120.,confidence=.95)
