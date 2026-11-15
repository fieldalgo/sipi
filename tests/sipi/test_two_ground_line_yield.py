# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent binomial limits, retained unknowns and actual scalar field rows."""
from dataclasses import replace
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.two_ground_line_study import (TwoGroundLineQuantityStudyDocument as Source,
    TwoGroundLineQuantityStudy as Study,TwoGroundLineQuantityStudyRow as Row)
from sipi.two_ground_line_yield import TwoGroundLineQuantityYieldDocument as Document,assess_two_ground_line_yield as assess
from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument as Line
from sipi.line_yield import assess_line_yield
from sipi.study import ImpedanceStudyDocument
from sipi.execution import execute_saved,normalize_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_two_ground_line_study import document as source_document,synthetic,QUANTITIES
from test_yield_assessment import independent_interval
from test_execution_record import ARTIFACTS


def source(count=4,kind='uniform',quantity='impedance_real',physical=False):
    raw=source_document(quantity,physical=physical).to_dict()
    sample=raw['study']['sampling'];sample['kind']=kind
    if kind=='corners':sample.pop('count',None)
    else:sample['count']=count
    if kind=='uniform':sample['seed']=17
    if kind=='normal':sample.update(seed=3,correlation=[[1.]],variables=[dict(name='width',mean=.0002,std=.0003)])
    return Source.from_dict(raw)


def document():return Document(source(),minimum=57.,maximum=59.,minimum_yield=.8)


def rows(values,quantity='impedance_real',kind='uniform'):
    """Algorithm-only rows, not evidence of physical field computation."""
    doc=source(len(values),kind,quantity);src=ImpedanceStudyDocument.from_dict(doc.to_dict()['study'])
    items=tuple(Row(i,tuple(map(float,sample)),json.dumps(parameters),json.dumps(materials),None,value,
        'diagnostic' if value is None else 'complete','ValueError' if value is None else None,
        'retained refusal' if value is None else None)
        for i,(value,sample,parameters,materials) in enumerate(zip(values,doc.samples(),src.sample_parameters(),src.sample_material_evaluations())))
    return Study(doc.dumps(),quantity,tuple(v['name'] for v in doc.to_dict()['study']['sampling']['variables']),items,None)


@pytest.mark.parametrize('quantity',QUANTITIES)
def test_inclusive_limits_units_and_unknown_envelope(quantity):
    values=[0.,1.,2.,None] if quantity=='attenuation' else [45.,55.,80.,None]
    limits=dict(minimum=0.,maximum=1.) if quantity=='attenuation' else dict(minimum=45.,maximum=55.)
    original=rows(values,quantity);result=assess(original,**limits,minimum_yield=.8)
    assert result.study is original and result.classifications==('pass','pass','fail','unresolved')
    assert result.sample_fraction_bounds==(.5,.75) and result.goal_status=='undetermined'
    out=result.to_dict();assert out['unit']==('Np/m' if quantity=='attenuation' else 'ohm')
    assert out['scope']=='iid-stated-two-ground-line-distribution-not-measured-production-yield'
    assert [r['value'] for r in out['rows']]==values
    for k in (2,3):
        low,high=independent_interval(k,4,.95)
        assert result.confidence_interval[0]<=low+1e-14 and result.confidence_interval[1]>=high-1e-14
    with pytest.raises(ValueError):assess_line_yield(original,**limits)
    json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('count',[2,5,20])
@pytest.mark.parametrize('confidence',[.5,.9,.95,.999])
def test_independent_finite_binomial_tails(count,confidence):
    for k in range(count+1):
        result=assess(rows([50.]*k+[80.]*(count-k)),minimum=45.,maximum=55.,confidence=confidence)
        np.testing.assert_allclose(result.confidence_interval,independent_interval(k,count,confidence),rtol=0,atol=1e-12)


def test_unknown_and_confidence_based_decisions():
    result=assess(rows([None]*5),maximum=55.,minimum_yield=.8)
    assert result.confidence_interval==result.sample_fraction_bounds==(0.,1.) and result.goal_status=='undetermined'
    good=rows([50.]*20)
    assert assess(good,minimum=45.,minimum_yield=.025**(1/20)).goal_status=='pass'
    assert assess(good,maximum=55.,minimum_yield=1.).goal_status=='undetermined'
    assert assess(good,maximum=55.).goal_status=='not-requested'
    assert assess(rows([80.]*20),maximum=55.,minimum_yield=.8).goal_status=='fail'


def test_corrupt_external_rows_reject_without_authenticity_claim():
    original=rows([50.,80.,None]);first=original.rows[0]
    bad=[replace(original,rows=original.rows[:-1]),replace(original,quantity='attenuation'),
         replace(original,variable_names=('other',)),replace(original,rows=original.rows[::-1])]
    for change in (dict(index=True),dict(index=1),dict(sample_values=(999.,)),dict(sample_values=None),
        dict(sample_values=(True,)),dict(value=float('nan')),dict(value=0.),dict(value=-1.),
        dict(phase='input'),dict(error_type='ValueError')):
        bad.append(replace(original,rows=(replace(first,**change),*original.rows[1:])))
    for change in (dict(value=50.),dict(phase='complete'),dict(error_type=None),dict(error=3)):
        bad.append(replace(original,rows=(*original.rows[:2],replace(original.rows[2],**change))))
    for item in bad:
        with pytest.raises(ValueError):assess(item,maximum=55.)


@pytest.mark.parametrize('kind',['sweep','corners'])
def test_non_iid_rejected_without_fields(monkeypatch,kind):
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('non-iid solved'))
    with pytest.raises(ValueError,match='iid'):Document(source(2,kind),minimum=45.)
    with pytest.raises(ValueError,match='iid'):assess(rows([50.,50.],kind=kind),minimum=45.)


@pytest.mark.parametrize('changes',[dict(minimum=None,maximum=None),dict(minimum=60.,maximum=40.),dict(minimum=-1.),
    dict(maximum=True),dict(minimum=float('nan')),dict(maximum=10**400),dict(confidence=0.),dict(confidence=1.),
    dict(confidence=True),dict(confidence=1e-300),dict(confidence=float('inf')),dict(minimum_yield=-.1),
    dict(minimum_yield=1.1),dict(minimum_yield=True)])
def test_invalid_criteria_are_fieldfree(monkeypatch,changes):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('criteria meshed'))
    controls=dict(minimum=45.,maximum=55.);controls.update(changes)
    with pytest.raises(ValueError):Document(source(),**controls)


@pytest.mark.parametrize('case',['schema','missing','extra','legacy','duplicate','nan'])
def test_strict_json(case):
    raw=document().to_dict();text=None
    if case=='schema':raw['schema']+='/future'
    if case=='missing':raw.pop('confidence')
    if case=='extra':raw['extra']=1
    if case=='legacy':raw['study']=raw['study']['study']
    if case=='duplicate':text=json.dumps(raw).replace('"confidence": 0.95','"confidence": 0.95,"confidence": 0.95')
    if case=='nan':text=json.dumps(raw).replace('"confidence": 0.95','"confidence": NaN')
    with pytest.raises(ValueError):Document.loads(text or json.dumps(raw))


def test_snapshot_registry_project_and_budget_before_fields(monkeypatch):
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('preflight solved'))
    doc=document();text=doc.dumps();assert Document.loads(text).dumps()==normalize_saved(text)==text
    raw=doc.to_dict();raw['study']['reference']['top']['conductivity']=1.;assert doc.dumps()==text
    request=SavedExecutionRequest(text,max_evaluations=4)
    project=SavedProject(request,project_id='two-ground-yield',design_id='a',title='Acceptance',label='Source')
    assert SavedProject.loads(project.dumps()).prepare('a').request_id==request.request_id
    with pytest.raises(ValueError,match='before any solve'):doc.analyze(max_evaluations=3)
    with pytest.raises(ValueError,match='before any solve'):execute_saved(text,max_evaluations=3)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(text,diagnostics=['characteristic'])


@pytest.mark.parametrize('quantity',QUANTITIES)
def test_saved_failed_calculation_retains_original_rows_and_evidence(monkeypatch,quantity):
    calls=synthetic(monkeypatch,fail_at=2)
    doc=Document(source(quantity=quantity),minimum=0.,maximum=1000.,minimum_yield=.8)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=4);receipt=request.run();out=receipt['execution']
    assert out['status']=='incomplete' and len(calls)==4
    result=out['result'];assert (result['passed'],result['failed'],result['unresolved'])==(3,0,1)
    assert result['sample_fraction_bounds']==[.75,1.]
    original=result['rows'];assert original[1]['cause_details']['cause_type']=='ArithmeticError'
    assert original[0]['current_solver']['kind']==original[0]['dielectric_mesh']['kind']=='test-only-synthetic'
    for k in (3,4):
        low,high=independent_interval(k,4,.95)
        assert result['confidence_interval'][0]<=low+1e-14 and result['confidence_interval'][1]>=high-1e-14
    record=SavedExecutionRecord(request,receipt,run_id='two-ground-yield:partial',artifacts=ARTIFACTS)
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt


def test_normal_invalid_geometry_never_dropped_or_resampled(monkeypatch):
    calls=synthetic(monkeypatch);doc=Document(source(8,'normal'),minimum=0.,maximum=1000.)
    result=doc.analyze(max_evaluations=8)
    assert 0<result.unresolved<8 and len(calls)==8-result.unresolved
    np.testing.assert_array_equal([r.sample_values for r in result.study.rows],source(8,'normal').samples())
    assert result.sample_fraction_bounds==(result.passed/8,(result.passed+result.unresolved)/8)


def test_interrupt_propagates(monkeypatch):
    calls=synthetic(monkeypatch,fail_at=2,interrupt=True)
    with pytest.raises(KeyboardInterrupt):document().analyze(max_evaluations=4)
    assert len(calls)==2


def test_actual_iid_scalar_acceptance_independent_classification_and_binomial(record_property):
    doc=Document(source(physical=True),minimum=57.,maximum=59.,minimum_yield=.8)
    receipt=SavedExecutionRequest(doc.dumps(),max_evaluations=4).run()
    record_property('two_ground_scalar_yield',json.dumps(receipt,sort_keys=True))
    out=receipt['execution'];assert out['status']=='complete';result=out['result']
    assert result['count']==4 and result['unresolved']==0
    labels=['pass' if 57.<=row['value']<=59. else 'fail' for row in result['rows']]
    assert labels==[row['classification'] for row in result['rows']]
    assert result['passed']==labels.count('pass')
    np.testing.assert_allclose(result['confidence_interval'],independent_interval(labels.count('pass'),4,.95),rtol=0,atol=1e-12)
    for row in result['rows']:
        assert row['current_solver'] and row['dielectric_mesh']
        assert row['phase']=='complete' and row['error'] is None
    json.dumps(receipt,allow_nan=False)
