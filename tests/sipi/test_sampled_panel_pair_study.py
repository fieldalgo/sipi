# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import numpy as np
import pytest
from sipi import CrossSection
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.study import ImpedanceStudyDocument
from test_pair_line_goal_document import source,Q
from test_sampled_panel_pair_goal import synthetic,targets,F
from test_panel_pair_study import expected_statistics
import sipi.sampled_panel_pair_study as module
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument as Document


def document(sampling=None,frequencies=F):
    raw=source().to_dict();raw['material_evaluation']['frequency_hz']=float(frequencies[0])
    if sampling is not None:raw['sampling']=sampling
    return Document(raw,conductor={'kind':'perfect'},frequencies=list(frequencies))


@pytest.mark.parametrize('lossless',[False,True])
def test_one_sample_across_entire_frequency_grid_and_independent_statistics(monkeypatch,lossless):
    calls=synthetic(monkeypatch,lossless=lossless);doc=document();result=doc.analyze(max_evaluations=4)
    assert result.failed==0 and len(result.rows)==len(calls)==4 and result.frequencies==tuple(F)
    np.testing.assert_array_equal([r.sample_values for r in result.rows],doc.samples())
    for i,(row,(width,gap)) in enumerate(zip(result.rows,doc.samples())):
        assert row.index==i and row.phase=='complete' and row.input_json==calls[i]
        assert json.loads(row.input_json)['line']['frequency_hz']==list(F)
        expected=targets(width/.3e-3,gap/.2e-3,lossless=lossless)
        np.testing.assert_allclose(row.values,expected,rtol=1e-12,atol=0)
    for f in range(len(F)):
        for i,q in enumerate(Q):
            expected=expected_statistics([row.values[f][i] for row in result.rows])
            for key,value in expected.items():assert result.summary[q][f][key]==pytest.approx(value,rel=1e-12)
    out=result.to_dict();assert out['count']==4 and out['frequencies_hz']==list(F)
    json.dumps(out,allow_nan=False)
    out['rows'][0]['values_ohm'][0][0]=0.;assert result.rows[0].values[0][0]>0
    with pytest.raises(TypeError):result.summary[Q[0]][0]['mean']=0.
    with pytest.raises(TypeError):result.rows[0].values[0][0]=0.
    with pytest.raises(FrozenInstanceError):result.frequencies=()


def test_maximum_frequency_count_still_counts_manufactured_rows(monkeypatch):
    calls=synthetic(monkeypatch);frequencies=np.geomspace(F[0],F[-1],64)
    result=document(frequencies=frequencies).analyze(max_evaluations=4)
    assert len(calls)==len(result.rows)==4 and result.failed==0 and len(result.summary[Q[0]])==64


def test_field_free_strict_roundtrip_and_copy_isolation(monkeypatch):
    def forbidden(*a,**k):pytest.fail('normalization invoked fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    doc=document();text=doc.dumps();raw=doc.to_dict();raw['frequency_hz'][0]=1.
    assert doc.dumps()==text and Document.loads(text).dumps()==text


@pytest.mark.parametrize('where',['root','study','panel'])
@pytest.mark.parametrize('kind',['extra','missing'])
def test_exact_keys(where,kind):
    raw=document().to_dict();target=raw if where=='root' else raw[where]
    if kind=='extra':target['unexpected']=1
    else:target.pop(next(iter(target)))
    with pytest.raises(ValueError):Document.from_dict(raw)


@pytest.mark.parametrize('frequencies',[[1e9],[0.,1e9],[1e9,1e9],[2e9,1e9],[True,1e9],[1e9,2e9],list(range(1,66)),[.2e9,float('inf')]])
def test_grid_shape_limits_and_first_frequency_anchor(frequencies):
    raw=document().to_dict();raw['frequency_hz']=frequencies
    with pytest.raises(ValueError):Document.from_dict(raw)


def test_duplicate_nonfinite_and_schema_rejection():
    text=document().dumps()
    for bad in [text.replace('"ground_modes": 512','"ground_modes": 512, "ground_modes": 512'),text.replace('"ground_modes": 512','"ground_modes": NaN'),text.replace('sipi.sampled-panel-forward-pair-study/1','sipi.sampled-panel-forward-pair-study/2')]:
        with pytest.raises(ValueError):Document.loads(bad)


@pytest.mark.parametrize('budget',[0,1,True,4.,10001,3])
def test_whole_row_budget_before_fields(monkeypatch,budget):
    doc=document()
    def forbidden(*a,**k):pytest.fail('budget check invoked fields')
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    with pytest.raises(ValueError):doc.analyze(max_evaluations=budget)


def test_generation_overflow_before_fields(monkeypatch):
    doc=document(dict(kind='normal',count=8,seed=3,correlation=[[1.]],variables=[dict(name='left_width',mean=1e308,std=1e308)]))
    def forbidden(*a,**k):pytest.fail('invalid generation invoked fields')
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    with np.errstate(over='ignore',invalid='ignore'):
        with pytest.raises(ValueError):doc.analyze(max_evaluations=8)


def test_duplicate_representable_samples_preserve_all_full_frequency_rows(monkeypatch):
    calls=synthetic(monkeypatch);lo=.3e-3
    doc=document(dict(kind='sweep',count=4,variables=[dict(name='left_width',lower=lo,upper=float(np.nextafter(lo,np.inf)))]))
    samples=doc.samples();assert len(np.unique(samples[:,0]))<4
    result=doc.analyze(max_evaluations=4)
    assert result.failed==0 and len(calls)==len(result.rows)==4
    np.testing.assert_array_equal([r.sample_values for r in result.rows],samples)


@pytest.mark.parametrize('phase',['parameters','materials','input','extraction','diagnostic'])
def test_failure_is_atomic_and_later_rows_continue(monkeypatch,phase):
    calls=synthetic(monkeypatch,fail_at=2 if phase=='extraction' else None);doc=document()
    if phase in ('parameters','materials','input'):
        name=dict(parameters='_parameters',materials='_sample_material',input='_line_from_inputs')[phase];original=getattr(module,name);seen=[]
        def broken(*a,**k):
            seen.append(1)
            if len(seen)==2:raise ArithmeticError('original row failure')
            return original(*a,**k)
        monkeypatch.setattr(module,name,broken)
    if phase=='diagnostic':
        original=PanelTransmissionLineDocument.analyze
        def broken(self):
            line=original(self)
            if len(calls)==2:
                def fail():raise ArithmeticError('original row failure')
                line.characteristic=fail
            return line
        monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',broken)
    result=doc.analyze(max_evaluations=4);row=result.rows[1]
    assert result.failed==1 and len(result.rows)==4 and result.summary is None
    assert row.phase==phase and row.values is None and row.error_type=='ArithmeticError'
    assert all(r.complete for i,r in enumerate(result.rows) if i!=1)
    assert (row.parameters_json is not None)==(phase!='parameters')
    assert (row.material_evaluation_json is not None)==(phase not in ('parameters','materials'))
    assert (row.input_json is not None)==(phase in ('extraction','diagnostic'))
    assert (row.result is not None)==(phase=='diagnostic')


@pytest.mark.parametrize('kind',['line_names','line_frequency','basis','names','frequency','mixed_basis','mixed_names','mixed_frequency','shape','nan','negative'])
def test_malformed_middle_frequency_diagnostic_invalidates_entire_row(monkeypatch,kind):
    calls=synthetic(monkeypatch);original=PanelTransmissionLineDocument.analyze
    def broken(self):
        line=original(self)
        if kind=='line_names':line.names=('wrong','names');return line
        if kind=='line_frequency':line.frequency=line.frequency[::-1];return line
        characteristic=line.characteristic();mixed=characteristic.mixed_mode();matrix=mixed.z_characteristic.copy()
        basis='single-ended';names=line.names;frequency=line.frequency;mbasis='mixed-mode';mnames=('differential','common');mf=frequency
        if kind=='basis':basis='wrong'
        elif kind=='names':names=names[::-1]
        elif kind=='frequency':frequency=frequency[::-1]
        elif kind=='mixed_basis':mbasis='wrong'
        elif kind=='mixed_names':mnames=mnames[::-1]
        elif kind=='mixed_frequency':mf=mf[::-1]
        elif kind=='shape':matrix=matrix[:1]
        elif kind=='nan':matrix[1,0,0]=np.nan
        elif kind=='negative':matrix[1,1,1]=-1.
        line.characteristic=lambda:SimpleNamespace(basis=basis,names=names,frequency=frequency,
            mixed_mode=lambda:SimpleNamespace(basis=mbasis,names=mnames,frequency=mf,z_characteristic=matrix))
        return line
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',broken)
    result=document().analyze(max_evaluations=4)
    assert result.failed==len(result.rows)==len(calls)==4 and result.summary is None
    for row in result.rows:
        assert row.values is None and row.result is not None and row.input_json and row.error_type=='ValueError'
        assert row.phase==('extraction' if kind.startswith('line_') else 'diagnostic')


def test_correlated_invalid_geometry_rows_remain_in_original_positions(monkeypatch):
    calls=synthetic(monkeypatch)
    doc=document(dict(kind='normal',count=8,seed=3,correlation=[[1.,.5],[.5,1.]],variables=[dict(name='left_width',mean=.2e-3,std=.3e-3),dict(name='gap',mean=.2e-3,std=.3e-3)]))
    result=doc.analyze(max_evaluations=8)
    assert 0<result.failed<8 and len(calls)==8-result.failed and result.summary is None
    np.testing.assert_array_equal([row.sample_values for row in result.rows],doc.samples())
    for row,(width,gap) in zip(result.rows,doc.samples()):
        assert row.complete==(width>0 and gap>0)
        if row.complete:np.testing.assert_allclose(row.values,targets(width/.3e-3,gap/.2e-3),rtol=1e-12,atol=0)
        else:assert row.phase=='input' and row.values is None and row.input_json is None


def test_empty_exception_is_not_success_and_no_refinement_is_implied(monkeypatch):
    def fail(self):raise ArithmeticError()
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',fail)
    raw=document().to_dict();raw['panel']['panels_per_edge']=256;doc=Document.from_dict(raw)
    result=doc.analyze(max_evaluations=4)
    assert result.failed==4 and result.summary is None and all(r.error=='' and not r.complete for r in result.rows)


def test_live_skrf_reference_for_every_frequency_and_manufactured_row(monkeypatch):
    import skrf
    from test_pair_line_goal import T
    synthetic(monkeypatch);doc=document();result=doc.analyze(max_evaluations=4)
    a=np.array([[1.,-1.],[.5,.5]])
    for row,(width,gap) in zip(result.rows,doc.samples()):
        scale=np.array([width/.3e-3,gap/.2e-3])
        d=dict(R=np.array([300.,2.])*scale,L=np.array([200e-9,400e-9])*scale,
               G=np.array([.005,.003])/scale,C=np.array([100e-12,80e-12])/scale)
        media=[skrf.media.DistributedCircuit(skrf.Frequency.from_f(F,unit='hz'),**{k:v[i] for k,v in d.items()}) for i in range(2)]
        reference=np.array([T@np.diag([m.z0[f] for m in media])@T.T for f in range(len(F))])
        actual=row.result.characteristic().z_characteristic
        assert abs(actual-reference).max()/abs(reference).max()<=1e-10
        np.testing.assert_allclose(row.values,np.diagonal(a@reference@a.T,axis1=1,axis2=2).real,rtol=1e-10,atol=0)


def test_fixed_pitch_debye_leaf_and_full_grid_reach_each_sample(monkeypatch):
    from sipi.dielectric import DebyeDielectric,dielectric_to_dict
    calls=synthetic(monkeypatch);raw=document().to_dict();study=raw['study']
    study['schema']='sipi.impedance-study/4';study['fixed_pitch_m']=.95e-3
    study['material_evaluation']['materials']={'substrate':dielectric_to_dict(DebyeDielectric(3.,(.7,),(1e9,)))}
    study['material_variables']={'strength':dict(region='substrate',path=['strengths',0])}
    study['sampling']['variables']=[dict(name='left_width',lower=.4e-3,upper=.8e-3),dict(name='strength',lower=.5,upper=.9)]
    doc=Document.from_dict(raw);result=doc.analyze(max_evaluations=4)
    assert result.failed==0 and len(calls)==4
    for row,(width,strength) in zip(result.rows,doc.samples()):
        data=json.loads(row.input_json)['line'];traces=data['cross_section']['traces']
        assert traces[1]['x']-traces[0]['x']==pytest.approx(.95e-3,rel=1e-12)
        assert data['frequency_hz']==list(F) and data['materials']['substrate']['parameters']['strengths']==[strength]
        assert json.loads(row.material_evaluation_json)['materials']['substrate']['parameters']['strengths']==[strength]
