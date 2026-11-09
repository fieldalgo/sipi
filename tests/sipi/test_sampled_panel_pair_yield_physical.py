# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed full-grid joint events checked against independent physical matrices and tails."""
import numpy as np
from sipi.constants import epsilon_0,mu_0
from sipi.dielectric import DebyeDielectric
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument as StudyDocument
from sipi.sampled_panel_pair_yield import SampledPanelForwardPairYieldDocument as Document
from sipi.execution import execute_saved
from test_pair_line_goal_document import source,Q
from test_pair_line_goal import document as original_line
from test_sampled_panel_pair_goal_physical import independent,F,A
from test_yield_assessment import independent_interval


def capture(monkeypatch):
    original=Document.analyze;results=[]
    def recorded(self,**kwargs):
        result=original(self,**kwargs);results.append(result);return result
    monkeypatch.setattr(Document,'analyze',recorded)
    return results


def test_actual_uniform_geometry_joint_labels_and_independent_binomial(monkeypatch):
    captured=capture(monkeypatch);raw=source(physical=True).to_dict();raw['material_evaluation']['frequency_hz']=float(F[0])
    raw['sampling']=dict(kind='uniform',count=4,seed=123,variables=[dict(name='left_width',lower=.60e-3,upper=.62e-3),dict(name='gap',lower=.40e-3,upper=.42e-3)])
    study=StudyDocument(raw,conductor=original_line(.6e-3,.4e-3).to_dict()['conductor'],frequencies=F.tolist())
    limits={q:dict(minimum=[lo]*3,maximum=[hi]*3) for q,lo,hi in zip(Q,[109.5,39.9],[110.5,40.1])}
    doc=Document(study,acceptance=limits,confidence=.95,minimum_yield=.9)
    output=execute_saved(doc.dumps(),max_evaluations=4)
    assert output['status']=='complete' and len(captured)==1
    result=captured[0];assert result.unresolved==0 and len(result.study.rows)==4
    labels=[]
    from scipy import linalg
    for row in result.study.rows:
        physical=row.result;independent(physical);values=[]
        for i,f in enumerate(F):
            z=physical.R[i]+2j*np.pi*f*physical.L[i];y=physical.G[i]+2j*np.pi*f*physical.C[i];scale=np.sqrt(abs(z).max()/abs(y).max())
            roots,vectors=linalg.eig(np.block([[np.zeros_like(z),z/scale],[scale*y,np.zeros_like(y)]]));mask=roots.imag>0
            assert np.count_nonzero(mask)==2 and np.all(roots[mask].real>=0)
            v=vectors[:,mask];reference=scale*v[:2]@np.linalg.inv(v[2:]);values.append(np.diag(A@reference@A.T).real)
        values=np.asarray(values);np.testing.assert_allclose(row.values,values,rtol=1e-10,atol=0)
        accepted=all(limits[q]['minimum'][f]<=values[f,i]<=limits[q]['maximum'][f] for f in range(3) for i,q in enumerate(Q))
        labels.append('pass' if accepted else 'fail')
    assert result.classifications==tuple(labels)==('fail','pass','fail','fail')
    np.testing.assert_allclose(result.confidence_interval,independent_interval(1,4,.95),rtol=0,atol=1e-12)
    assert result.goal_status=='fail' and output['result']==result.to_dict()


def test_actual_correlated_debye_joint_event_and_material_reference(monkeypatch):
    captured=capture(monkeypatch);model=DebyeDielectric(3.,(.7,),(1e9,))
    source_study=ImpedanceStudyDocument('coupled_microstrip',dict(width=.3e-3,gap=.2e-3,substrate_height=.5e-3,
        eps_r=4.,thickness=35e-6,air_height=2e-3,box_width=6e-3),quantity='z_diff_forward',frequency=float(F[0]),
        materials={'substrate':model,'air':model},mesh=dict(edge_size=10e-6,far_size=.2e-3,grade=.1),
        material_variables={'strength_substrate':dict(region='substrate',path=['strengths',0]),'strength_air':dict(region='air',path=['strengths',0])},
        sampling=dict(kind='normal',count=4,seed=3,correlation=[[1.,1.],[1.,1.]],variables=[
            dict(name='strength_substrate',mean=.7,std=.05),dict(name='strength_air',mean=.7,std=.05)]))
    study=StudyDocument(source_study,conductor={'kind':'perfect'},frequencies=F.tolist())
    doc=Document(study,acceptance={q:dict(minimum=[0.]*3,maximum=[1000.]*3) for q in Q},confidence=.95,minimum_yield=.9)
    output=execute_saved(doc.dumps(),max_evaluations=4)
    assert output['status']=='complete' and len(captured)==1
    result=captured[0];assert result.unresolved==0 and len(result.study.rows)==4
    for row in result.study.rows:
        physical=row.result;strength=row.sample_values[0];assert row.sample_values[1]==strength
        eps=3.+strength/(1+1j*F/1e9)
        reference=np.array([np.sqrt(mu_0*epsilon_0/e)*np.linalg.inv(physical.current_factors.C0) for e in eps])
        actual=physical.characteristic().z_characteristic
        assert abs(actual-reference).max()/abs(reference).max()<=1e-10
        values=np.diagonal(A@reference@A.T,axis1=1,axis2=2).real
        np.testing.assert_allclose(row.values,values,rtol=1e-10,atol=0)
        assert np.all(values>=0.) and np.all(values<=1000.)
    assert result.classifications==('pass',)*4
    np.testing.assert_allclose(result.confidence_interval,independent_interval(4,4,.95),rtol=0,atol=1e-12)
    assert result.goal_status=='undetermined' and output['result']==result.to_dict()
