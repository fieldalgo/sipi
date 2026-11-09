# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual fixed family, independent physical matrices and simultaneous bounds."""
import numpy as np
from scipy import linalg
from sipi.constants import epsilon_0,mu_0
from sipi.dielectric import DebyeDielectric
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument as Study
from sipi.sampled_panel_pair_selection import SampledPanelForwardPairSelectionDocument as Document
from sipi.execution import execute_saved
from test_pair_line_goal_document import source,Q
from test_pair_line_goal import document as original_line
from test_sampled_panel_pair_goal_physical import F,A
from test_yield_assessment import independent_interval


def test_actual_fixed_family_and_independent_reference_selection(monkeypatch):
    raw=source(physical=True).to_dict();raw['material_evaluation']['frequency_hz']=float(F[0])
    raw['sampling']=dict(kind='uniform',count=4,seed=123,variables=[dict(name='left_width',lower=.60e-3,upper=.62e-3),dict(name='gap',lower=.40e-3,upper=.42e-3)])
    geometry=Study(raw,conductor=original_line(.6e-3,.4e-3).to_dict()['conductor'],frequencies=F.tolist())
    material=DebyeDielectric(3.,(.7,),(1e9,))
    material_source=ImpedanceStudyDocument('coupled_microstrip',dict(width=.3e-3,gap=.2e-3,substrate_height=.5e-3,eps_r=4.,thickness=35e-6,air_height=2e-3,box_width=6e-3),
        quantity='z_diff_forward',frequency=float(F[0]),materials=dict(substrate=material,air=material),mesh=dict(edge_size=10e-6,far_size=.2e-3,grade=.1),
        material_variables={'strength_substrate':dict(region='substrate',path=['strengths',0]),'strength_air':dict(region='air',path=['strengths',0])},
        sampling=dict(kind='normal',count=4,seed=3,correlation=[[1.,1.],[1.,1.]],variables=[dict(name='strength_substrate',mean=.7,std=.05),dict(name='strength_air',mean=.7,std=.05)]))
    dielectric=Study(material_source,conductor={'kind':'perfect'},frequencies=F.tolist())
    doc=Document([dict(name='geometry',cost=2.,study=geometry.to_dict()),dict(name='material',cost=1.,study=dielectric.to_dict())],cost_unit='relative-cost',
        acceptance={q:dict(minimum=[0.]*3,maximum=[1000.]*3) for q in Q},minimum_yield=.3,confidence=.95)
    original=Document.analyze;captured=[]
    def recorded(self,**kwargs):
        result=original(self,**kwargs);captured.append(result);return result
    monkeypatch.setattr(Document,'analyze',recorded)
    output=execute_saved(doc.dumps(),max_evaluations=8)
    assert output['status']=='complete' and len(captured)==1
    result=captured[0];assert result.selected_index==1 and result.unresolved==0 and result.candidate_confidence==.975
    assert result.to_dict()['selected']==dict(index=1,name='material',cost=1.)
    assert output['result']==result.to_dict() and output['input']==doc.to_dict()
    for index,candidate in enumerate(result.candidates):
        assessment=candidate.assessment;labels=[]
        for row in assessment.study.rows:
            line=row.result;actual=line.characteristic().z_characteristic
            if index==0:
                refs=[]
                for i,f in enumerate(F):
                    z=line.R[i]+2j*np.pi*f*line.L[i];y=line.G[i]+2j*np.pi*f*line.C[i];scale=np.sqrt(abs(z).max()/abs(y).max())
                    roots,vectors=linalg.eig(np.block([[np.zeros_like(z),z/scale],[scale*y,np.zeros_like(y)]]));mask=roots.imag>0
                    assert np.count_nonzero(mask)==2 and np.all(roots[mask].real>=0)
                    v=vectors[:,mask];refs.append(scale*v[:2]@np.linalg.inv(v[2:]))
                reference=np.asarray(refs)
            else:
                strength=row.sample_values[0];assert row.sample_values[1]==strength
                eps=3.+strength/(1+1j*F/1e9)
                reference=np.array([np.sqrt(mu_0*epsilon_0/e)*np.linalg.inv(line.current_factors.C0) for e in eps])
            assert abs(actual-reference).max()/abs(reference).max()<=1e-10
            values=np.diagonal(A@reference@A.T,axis1=1,axis2=2).real
            np.testing.assert_allclose(row.values,values,rtol=1e-10,atol=0)
            labels.append('pass' if np.all((values>=0)&(values<=1000)) else 'fail')
        assert tuple(labels)==assessment.classifications==('pass',)*4
        expected=independent_interval(4,4,result.candidate_confidence)
        np.testing.assert_allclose(assessment.confidence_interval,expected,rtol=0,atol=1e-12)
        assert expected[0]>=.3 and assessment.goal_status=='pass'
